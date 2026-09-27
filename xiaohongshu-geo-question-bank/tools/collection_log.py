"""Per-brand collection log: planned queries, notes already read, rate limits.

Xiaohongshu search slows down or stops after a burst of activity, so
collection for a large brand spans several paced batches and often several
sessions. The log lets the next batch pick up where the last one stopped and
never re-open a note it already read.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from evidence_store import brand_key


PURPOSES = ("seed", "theoretical", "brand_free", "comparison")
# Pages opened per batch before pausing. Chosen from observed slow-downs after
# roughly 15 page loads in a burst; kept below that on purpose.
PAGES_PER_BATCH = 10


class CollectionLogError(ValueError):
    """Raised when a log entry is malformed."""


def _path(root: str | Path, brand: str) -> Path:
    return Path(root) / f"{brand_key(brand)}.json"


def load_log(root: str | Path, brand: str) -> dict[str, Any]:
    path = _path(root, brand)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"brand": brand.strip(), "queries": [], "seen_notes": [], "batches": []}


def _save(root: str | Path, log: dict[str, Any]) -> None:
    path = _path(root, log["brand"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def plan_queries(root: str | Path, brand: str, queries: list[dict[str, Any]]) -> dict[str, Any]:
    """Add queries to try. Each needs `query`, `purpose` and, for theoretical
    sampling, the `reason` (the category gap it is meant to fill)."""
    log = load_log(root, brand)
    known = {q["query"] for q in log["queries"]}
    for item in queries:
        query = str(item.get("query") or "").strip()
        purpose = item.get("purpose")
        if not query:
            raise CollectionLogError("query is required")
        if purpose not in PURPOSES:
            raise CollectionLogError(f"purpose must be one of {', '.join(PURPOSES)}")
        if purpose == "theoretical" and not str(item.get("reason") or "").strip():
            raise CollectionLogError(f"{query}: theoretical sampling needs the category gap it targets")
        if query in known:
            continue
        log["queries"].append({"query": query, "purpose": purpose, "reason": item.get("reason") or "",
                               "status": "planned", "batch": None})
        known.add(query)
    _save(root, log)
    return status(root, brand)


def record_batch(
    root: str | Path,
    brand: str,
    *,
    batch: int,
    queries_done: Iterable[str],
    note_urls: Iterable[str],
    pages_loaded: int,
    rate_limited: bool,
) -> dict[str, Any]:
    log = load_log(root, brand)
    if any(b["batch"] == batch for b in log["batches"]):
        raise CollectionLogError(f"batch {batch} already recorded")
    done = set(q.strip() for q in queries_done if q and q.strip())
    for q in log["queries"]:
        if q["query"] in done and q["status"] != "done":
            q["status"] = "done"
            q["batch"] = batch
    unknown = done - {q["query"] for q in log["queries"]}
    for query in sorted(unknown):
        log["queries"].append({"query": query, "purpose": "seed", "reason": "", "status": "done", "batch": batch})
    seen = set(log["seen_notes"])
    new_notes = []
    for n in (note_id(u) for u in note_urls):
        if n and n not in seen:
            seen.add(n)
            new_notes.append(n)
    log["seen_notes"].extend(new_notes)
    log["batches"].append({
        "batch": batch,
        "pages_loaded": pages_loaded,
        "new_notes": len(new_notes),
        "rate_limited": rate_limited,
        "ended_at": datetime.now().replace(microsecond=0).isoformat(),
    })
    _save(root, log)
    return status(root, brand)


def status(root: str | Path, brand: str) -> dict[str, Any]:
    log = load_log(root, brand)
    batches = log["batches"]
    last_limited = next((b for b in reversed(batches) if b["rate_limited"]), None)
    return {
        "brand": log["brand"],
        "next_batch": (max((b["batch"] for b in batches), default=0) + 1),
        "pages_per_batch": PAGES_PER_BATCH,
        "planned_queries": [q for q in log["queries"] if q["status"] == "planned"],
        "done_queries": sum(1 for q in log["queries"] if q["status"] == "done"),
        "seen_notes": len(log["seen_notes"]),
        "seen_note_ids": log["seen_notes"],
        "batches": batches,
        "last_rate_limited_batch": last_limited["batch"] if last_limited else None,
        "last_rate_limited_at": last_limited["ended_at"] if last_limited else None,
    }


def note_id(url: Any) -> str | None:
    if not isinstance(url, str):
        return None
    match = re.search(r"/(?:explore|discovery/item)/([0-9a-f]{24})", url)
    return match.group(1) if match else None
