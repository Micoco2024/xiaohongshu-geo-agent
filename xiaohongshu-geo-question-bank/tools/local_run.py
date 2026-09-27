"""Command-line steps for running the agent inside Claude Code or Codex without an API key.

The client does the web discovery and the question writing itself; this script
keeps the deterministic parts (normalization, evidence IDs, validation, gates,
file storage) identical to the API runtime. Files go to the workbench data
folder, so the web workbench can display runs made here.

  python3 tools/local_run.py collect-status --brand 珀莱雅
  python3 tools/local_run.py collect-plan --brand 珀莱雅 --queries queries.json
  python3 tools/local_run.py save-evidence --brand 珀莱雅 --raw batch1.json --batch 1 --pages 5 --queries-done "珀莱雅 早C晚A"
  python3 tools/local_run.py save-evidence --brand 珀莱雅 --raw limited.json --batch 2 --pages 1 --queries-limited "珀莱雅 敏感肌" --rate-limited
  python3 tools/local_run.py save-coding --brand 珀莱雅 --coding coding.json
  python3 tools/local_run.py save-bank --snapshot 珀莱雅/20260926-110005 --bank bank.json
  python3 tools/local_run.py live-plan --run 珀莱雅/20260926-111200 --products 点点,豆包 --repeats 1
  python3 tools/local_run.py live-record --run 珀莱雅/20260926-111200 --records runs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "tools"))
sys.path.insert(0, str(SKILL_ROOT.parent / "xiaohongshu-geo-evaluator" / "tools"))

from brand_discovery import normalize_discovery_result  # noqa: E402
from evaluator import run_deterministic_evaluation  # noqa: E402
from live_test import record_runs, start_session  # noqa: E402
from collection_log import check_batch, plan_queries, record_batch, status as collection_status  # noqa: E402
from evidence_store import append_batch, brand_key, list_snapshots, load_snapshot, save_snapshot  # noqa: E402
from grounded_coding import check_bank_against_coding, saturation, validate_coding  # noqa: E402
from question_bank import validate_question_bank  # noqa: E402

DEFAULT_DATA = SKILL_ROOT.parent / "xiaohongshu-geo-workbench" / "data"
RUNTIME_LABEL = "claude-code"


def save_evidence(
    brand: str,
    raw_path: Path,
    data_root: Path,
    *,
    batch: int | None = None,
    pages: int = 0,
    queries_done: list[str] | None = None,
    queries_limited: list[str] | None = None,
    rate_limited: bool = False,
) -> dict[str, Any]:
    """Without --batch: a new snapshot. With --batch: merge into the brand's
    working snapshot and record the batch in the collection log."""
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    discovery = normalize_discovery_result(brand, raw)
    if batch is not None:
        # Validate the batch before writing anything, so a rejected batch
        # leaves both the snapshot and the collection log untouched.
        check_batch(data_root / "collection", brand, batch=batch, queries_done=queries_done or [],
                    pages_loaded=pages, rate_limited=rate_limited, queries_limited=queries_limited or [])
    if batch is None:
        summary = save_snapshot(data_root / "evidence", brand, discovery, model=RUNTIME_LABEL)
    else:
        summary = append_batch(data_root / "evidence", brand, discovery, batch=batch, model=RUNTIME_LABEL)
        log = record_batch(
            data_root / "collection", brand, batch=batch, queries_done=queries_done or [],
            queries_limited=queries_limited or [],
            note_urls=[r["source_ref"] for r in discovery["evidence"]],
            pages_loaded=pages, rate_limited=rate_limited,
        )
        summary["collection"] = {k: log[k] for k in ("next_batch", "seen_notes", "planned_queries",
                                                      "collection_allowed", "resume_after", "pages_per_batch")}
        summary["collection"]["this_batch"] = log["batches"][-1]
    return {
        **summary,
        "coverage_note": discovery["coverage_note"],
        # Only usable records may be cited by questions.
        "usable_evidence": [
            {"evidence_id": r["evidence_id"], "author_role": r["author_role"], "text": r["text"], "usage": r["usage"]}
            for r in discovery["evidence"] if r["status"] == "usable"
        ],
        "candidate_count": sum(1 for r in discovery["evidence"] if r["status"] == "candidate"),
    }


def save_bank(snapshot_id: str, bank_path: Path, data_root: Path) -> dict[str, Any]:
    snapshot = load_snapshot(data_root / "evidence", snapshot_id)
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    evidence = snapshot["discovery"]["evidence"]
    usable_ids = [r["evidence_id"] for r in evidence if r["status"] == "usable"]
    validate_question_bank(bank, usable_ids)
    coding = _load_coding(data_root, snapshot["brand_name"])
    if coding is not None:
        check_bank_against_coding(bank, coding)
    now = datetime.now().replace(microsecond=0)
    run = {
        "run_id": f"{brand_key(snapshot['brand_name'])}/{now.strftime('%Y%m%d-%H%M%S')}",
        "snapshot_id": snapshot_id,
        "created_at": now.isoformat(),
        "model": RUNTIME_LABEL,
        "result": {
            "status": "completed",
            "brand_name": snapshot["brand_name"],
            "coverage_note": snapshot["discovery"]["coverage_note"],
            "missing_information": snapshot["discovery"]["missing_information"],
            "evidence_count": len(evidence),
            "question_bank": bank,
        },
        "evaluation": run_deterministic_evaluation(bank, evidence),
    }
    path = data_root / "runs" / f"{run['run_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"run_file": str(path), "evaluation": run["evaluation"]}


def _coding_path(data_root: Path, brand: str) -> Path:
    return data_root / "coding" / f"{brand_key(brand)}.json"


def _load_coding(data_root: Path, brand: str) -> dict[str, Any] | None:
    path = _coding_path(data_root, brand)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def save_coding(brand: str, coding_path: Path, data_root: Path) -> dict[str, Any]:
    """Validate a grounded-theory coding record against the brand's evidence and store it."""
    snapshots = list_snapshots(data_root / "evidence", brand)
    if not snapshots:
        raise ValueError("no evidence snapshot for this brand yet")
    snapshot = load_snapshot(data_root / "evidence", snapshots[0]["snapshot_id"])
    usable = [r["evidence_id"] for r in snapshot["discovery"]["evidence"] if r["status"] == "usable"]
    coding = json.loads(coding_path.read_text(encoding="utf-8"))
    warnings = validate_coding(coding, usable)
    cited = {ref for code in coding.get("open_codes", []) for ref in code["evidence_refs"]}
    uncoded = [e for e in usable if e not in cited]
    path = _coding_path(data_root, brand)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**coding, "snapshot_id": snapshot["snapshot_id"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "coding_file": str(path),
        "snapshot_id": snapshot["snapshot_id"],
        "counts": {k: len(coding.get(k, [])) for k in ("open_codes", "focused_codes", "categories", "memos")},
        "uncoded_evidence": uncoded,
        "saturation": saturation(coding),
        "warnings": warnings,
    }


def live_plan(run_id: str, products: list[str], repeats: int, data_root: Path) -> dict[str, Any]:
    run = json.loads((data_root / "runs" / f"{run_id}.json").read_text(encoding="utf-8"))
    snapshot = load_snapshot(data_root / "evidence", run["snapshot_id"])
    profile = snapshot["discovery"].get("brand_profile") or {}
    aliases = (profile.get("brand") or {}).get("aliases", [])
    evidence_urls = [r["source_ref"].split("#")[0] for r in snapshot["discovery"]["evidence"]]
    session = start_session(data_root, run_id, products, repeats=repeats, aliases=aliases, evidence_urls=evidence_urls)
    return {"brand_terms": session["brand_terms"], "plan": session["plan"], "live_test_status": session["live_test_status"]}


def live_record(run_id: str, records_path: Path, data_root: Path) -> dict[str, Any]:
    records = json.loads(records_path.read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = [records]
    session = record_runs(data_root, run_id, records)
    return {"live_test_status": session["live_test_status"], "summary": session["summary"],
            "source_profile": session["source_profile"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="workbench data folder")
    commands = parser.add_subparsers(dest="command", required=True)
    evidence = commands.add_parser("save-evidence", help="normalize raw discovery JSON and save a snapshot")
    evidence.add_argument("--brand", required=True)
    evidence.add_argument("--raw", type=Path, required=True, help="JSON matching schemas/brand-discovery.schema.json")
    bank = commands.add_parser("save-bank", help="validate a question bank against a snapshot and save the run")
    bank.add_argument("--snapshot", required=True)
    bank.add_argument("--bank", type=Path, required=True, help="JSON matching schemas/question-bank.schema.json")
    cstatus = commands.add_parser("collect-status", help="what has been searched and read for a brand")
    cstatus.add_argument("--brand", required=True)
    cplan = commands.add_parser("collect-plan", help="add queries to the brand's collection plan")
    cplan.add_argument("--brand", required=True)
    cplan.add_argument("--queries", type=Path, required=True, help='JSON list of {"query", "purpose", "reason"}')
    evidence.add_argument("--batch", type=int, help="merge into the working snapshot as this batch number")
    evidence.add_argument("--pages", type=int, default=0, help="pages opened in this batch")
    evidence.add_argument("--queries-done", default="", help="comma-separated queries that returned a usable result page")
    evidence.add_argument("--queries-limited", default="", help="comma-separated queries stopped by a blank, stale, or verification page")
    evidence.add_argument("--rate-limited", action="store_true", help="search or pages stopped responding")
    coding = commands.add_parser("save-coding", help="validate and store the grounded-theory coding record")
    coding.add_argument("--brand", required=True)
    coding.add_argument("--coding", type=Path, required=True)
    plan = commands.add_parser("live-plan", help="plan AI-product runs for a saved question bank")
    plan.add_argument("--run", required=True)
    plan.add_argument("--products", required=True, help="comma-separated, e.g. 点点,豆包,DeepSeek")
    plan.add_argument("--repeats", type=int, default=1)
    live = commands.add_parser("live-record", help="record captured AI-product answers")
    live.add_argument("--run", required=True)
    live.add_argument("--records", type=Path, required=True,
                      help="JSON list of {product, question_ref, repeat_index, turns:[{question, response}], citations, "
                           "sources:[{title, url, author, author_type, note_type, published, likes, collects, comments, excerpt}], ...}")
    args = parser.parse_args()
    try:
        if args.command == "collect-status":
            result = {k: v for k, v in collection_status(args.data / "collection", args.brand).items() if k != "seen_note_ids"}
        elif args.command == "collect-plan":
            result = plan_queries(args.data / "collection", args.brand, json.loads(args.queries.read_text(encoding="utf-8")))
            result.pop("seen_note_ids", None)
        elif args.command == "save-coding":
            result = save_coding(args.brand, args.coding, args.data)
        elif args.command == "save-evidence":
            result = save_evidence(
                args.brand, args.raw, args.data, batch=args.batch, pages=args.pages,
                queries_done=[q for q in args.queries_done.replace("，", ",").split(",") if q.strip()],
                queries_limited=[q for q in args.queries_limited.replace("，", ",").split(",") if q.strip()],
                rate_limited=args.rate_limited,
            )
        elif args.command == "save-bank":
            result = save_bank(args.snapshot, args.bank, args.data)
        elif args.command == "live-plan":
            result = live_plan(args.run, args.products.replace("，", ",").split(","), args.repeats, args.data)
        else:
            result = live_record(args.run, args.records, args.data)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
