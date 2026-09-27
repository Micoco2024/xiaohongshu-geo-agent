"""Command-line steps for running the agent inside Claude Code without an API key.

Claude Code does the web discovery and the question writing itself; this script
keeps the deterministic parts (normalization, evidence IDs, validation, gates,
file storage) identical to the API runtime. Files go to the workbench data
folder, so the web workbench can display runs made here.

  python3 tools/local_run.py save-evidence --brand 珀莱雅 --raw raw-discovery.json
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
from evidence_store import brand_key, load_snapshot, save_snapshot  # noqa: E402
from question_bank import validate_question_bank  # noqa: E402

DEFAULT_DATA = SKILL_ROOT.parent / "xiaohongshu-geo-workbench" / "data"
RUNTIME_LABEL = "claude-code"


def save_evidence(brand: str, raw_path: Path, data_root: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    discovery = normalize_discovery_result(brand, raw)
    summary = save_snapshot(data_root / "evidence", brand, discovery, model=RUNTIME_LABEL)
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
        if args.command == "save-evidence":
            result = save_evidence(args.brand, args.raw, args.data)
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
