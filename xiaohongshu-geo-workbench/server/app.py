"""Local backend for the Xiaohongshu GEO web workbench.

Step 1 (brand discovery, the only step with web search) is saved as an
evidence snapshot under data/evidence and reused by later generations.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WORKBENCH_ROOT.parent
SKILL_ROOT = PROJECT_ROOT / "xiaohongshu-geo-question-bank"
EVALUATOR_ROOT = PROJECT_ROOT / "xiaohongshu-geo-evaluator"
WEB_ROOT = WORKBENCH_ROOT / "web"
DATA_ROOT = WORKBENCH_ROOT / "data"
EVIDENCE_ROOT = DATA_ROOT / "evidence"
RUNS_ROOT = WORKBENCH_ROOT / "data" / "runs"
sys.path.insert(0, str(SKILL_ROOT / "tools"))
sys.path.insert(0, str(EVALUATOR_ROOT / "tools"))

from agent_runner import run_brand_agent  # noqa: E402
from brand_discovery import discover_brand, load_discovery_schema  # noqa: E402
from customer_service_ingest import (  # noqa: E402
    CustomerServiceInputError,
    parse_customer_service_document,
)
from evaluator import run_deterministic_evaluation  # noqa: E402
from live_test import LiveTestError, load_session, record_runs  # noqa: E402
from local_run import live_plan  # noqa: E402
from evidence_store import (  # noqa: E402
    EvidenceStoreError,
    brand_key,
    list_snapshots,
    load_snapshot,
    save_snapshot,
)
from claude_client import DEFAULT_MODEL, MODELS  # noqa: E402


JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
MAX_BODY_BYTES = 6 * 1024 * 1024


def _default_model() -> str:
    model = os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL
    return model if model in MODELS else DEFAULT_MODEL


def _model(payload: dict[str, Any]) -> str:
    model = str(payload.get("model") or _default_model())
    if model not in MODELS:
        raise ValueError(f"不支持的模型：{model}")
    return model


def _api_key(payload: dict[str, Any]) -> str:
    """Key typed on the page wins; the server's ANTHROPIC_API_KEY is the fallback."""
    api_key = str(payload.get("_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("没有可用的 Claude API Key：请在页面左栏填写，或在启动后端前设置 ANTHROPIC_API_KEY")
    return api_key


def _set_job(job_id: str, **changes: Any) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(changes)


def _start_job(target: Any, payload: dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {"job_id": job_id, "status": "running", "progress": 5, "stage": "任务已创建"}

    def run() -> None:
        try:
            _set_job(job_id, status="completed", progress=100, stage="完成", result=target(job_id, payload))
        except (CustomerServiceInputError, EvidenceStoreError, ValueError, RuntimeError) as error:
            _set_job(job_id, status="failed", progress=100, stage="运行失败", error=str(error))
        except Exception as error:  # keep stack details out of the page
            _set_job(job_id, status="failed", progress=100, stage="运行失败", error=f"后端运行失败：{type(error).__name__}")

    threading.Thread(target=run, daemon=True).start()
    return job_id


def _discover_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Step 1: web search discovery, saved as a new evidence snapshot."""
    brand_name = str(payload.get("brand_name") or "").strip()
    if not brand_name:
        raise ValueError("品牌名称不能为空")
    model = _model(payload)
    _set_job(job_id, progress=20, stage=f"正在用 {MODELS[model]['label']} 搜索小红书公开表达（消耗 token）")
    discovery = discover_brand(
        api_key=_api_key(payload),
        brand_name=brand_name,
        discovery_schema=load_discovery_schema(SKILL_ROOT),
        model=model,
    )
    _set_job(job_id, progress=90, stage="正在保存证据快照")
    return save_snapshot(EVIDENCE_ROOT, brand_name, discovery, model=model)


def _generate_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Step 2: generate a question bank from a saved snapshot, then gate it."""
    snapshot = load_snapshot(EVIDENCE_ROOT, str(payload.get("snapshot_id") or ""))
    model = _model(payload)

    _set_job(job_id, progress=15, stage="正在读取并脱敏客服资料")
    customer_evidence = []
    for item in payload.get("customer_service_files") or []:
        if isinstance(item, dict):
            customer_evidence.extend(parse_customer_service_document(
                str(item.get("name") or "customer-service.txt"),
                str(item.get("content") or ""),
            ))

    _set_job(job_id, progress=35, stage=f"正在用 {MODELS[model]['label']} 生成问题库（消耗 token）")
    result = run_brand_agent(
        brand_name=snapshot["brand_name"],
        api_key=_api_key(payload),
        skill_root=SKILL_ROOT,
        customer_service_evidence=customer_evidence,
        model=model,
        discovery_function=lambda **_: snapshot["discovery"],
    )
    if result["status"] != "completed":
        raise RuntimeError(result.get("coverage_note") or "可用用户表达不足，未生成问题库")

    _set_job(job_id, progress=90, stage="正在运行确定性检查")
    evidence = [*snapshot["discovery"]["evidence"], *customer_evidence]
    run = {
        "run_id": f"{brand_key(snapshot['brand_name'])}/{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "snapshot_id": snapshot["snapshot_id"],
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "model": model,
        "result": result,
        "evaluation": run_deterministic_evaluation(result["question_bank"], evidence),
    }
    path = RUNS_ROOT / f"{run['run_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def live_record_inline(run_id: str, records: list[dict[str, Any]]) -> None:
    if not records:
        raise ValueError("没有要保存的实测记录")
    record_runs(DATA_ROOT, run_id, records)


def _list_runs(snapshot_id: str | None) -> list[dict[str, Any]]:
    runs = []
    for path in RUNS_ROOT.glob("*/*.json") if RUNS_ROOT.is_dir() else []:
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if snapshot_id and run.get("snapshot_id") != snapshot_id:
            continue
        runs.append(run)
    return sorted(runs, key=lambda item: item["created_at"], reverse=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "XHSGEOWorkbench/1.0"

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path = unquote(url.path)
        query = parse_qs(url.query)
        if path in ("/", "/index.html"):
            self._file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
        elif path == "/api/health":
            self._json(200, {"ok": True, "server_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")), "default_model": _default_model(),
                        "models": [{"id": key, **value} for key, value in MODELS.items()]})
        elif path == "/api/snapshots":
            self._json(200, list_snapshots(EVIDENCE_ROOT))
        elif path.startswith("/api/snapshots/"):
            try:
                self._json(200, load_snapshot(EVIDENCE_ROOT, path.removeprefix("/api/snapshots/")))
            except EvidenceStoreError as error:
                self._json(404, {"error": str(error)})
        elif path == "/api/runs":
            self._json(200, _list_runs((query.get("snapshot_id") or [None])[0]))
        elif path == "/api/live":
            try:
                self._json(200, load_session(DATA_ROOT, (query.get("run_id") or [""])[0]))
            except LiveTestError as error:
                self._json(400, {"error": str(error)})
        elif path.startswith("/api/jobs/"):
            with JOBS_LOCK:
                job = JOBS.get(path.rsplit("/", 1)[-1])
                response = dict(job) if job else None
            self._json(200 if response else 404, response or {"error": "任务不存在"})
        else:
            self._json(404, {"error": "接口不存在"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path in ("/api/live/plan", "/api/live/record"):
            self._live_post(urlparse(self.path).path)
            return
        targets = {"/api/discover": _discover_job, "/api/generate": _generate_job}
        target = targets.get(urlparse(self.path).path)
        if target is None:
            self._json(404, {"error": "接口不存在"})
            return
        try:
            payload = self._read_json()
        except ValueError as error:
            self._json(400, {"error": str(error)})
            return
        # The page sends its key in a header; it is used for this job only and never saved or logged.
        header_key = (self.headers.get("X-Anthropic-Key") or "").strip()
        if header_key:
            payload["_api_key"] = header_key
        self._json(202, {"job_id": _start_job(target, payload), "status": "running"})

    def _live_post(self, path: str) -> None:
        """Live-test planning and recording are quick file writes, so they run inline."""
        try:
            payload = self._read_json()
            run_id = str(payload.get("run_id") or "")
            if path == "/api/live/plan":
                live_plan(run_id, list(payload.get("products") or []), int(payload.get("repeats") or 1), DATA_ROOT)
            else:
                records = payload.get("records")
                live_record_inline(run_id, records if isinstance(records, list) else [])
            self._json(200, load_session(DATA_ROOT, run_id))
        except (ValueError, KeyError, OSError) as error:
            self._json(400, {"error": str(error)})

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError as error:
            raise ValueError("Content-Length 无效") from error
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("请求为空或超过 6MB")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("请求不是有效 JSON") from error
        if not isinstance(value, dict):
            raise ValueError("请求必须是 JSON 对象")
        return value

    def _file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[server] {self.address_string()} {format % args}")


if __name__ == "__main__":
    host = os.environ.get("GEO_HOST", "127.0.0.1")
    port = int(os.environ.get("GEO_PORT", "8788"))
    print(f"小红书 GEO 工作台：http://{host}:{port}")
    print(f"ANTHROPIC_API_KEY：{'已配置' if os.environ.get('ANTHROPIC_API_KEY') else '未配置'}；默认模型：{_default_model()}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
