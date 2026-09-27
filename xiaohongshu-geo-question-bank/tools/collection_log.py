"""Per-brand collection log: planned queries, notes already read, rate limits.

Xiaohongshu search slows down or stops after a burst of activity, so
collection for a large brand spans several paced batches and often several
sessions. The log lets the next batch pick up where the last one stopped and
never re-open a note it already read.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from evidence_store import brand_key


PURPOSES = ("seed", "theoretical", "brand_free", "comparison")
PAGES_PER_BATCH = 5
RECOVERY_PAGES_PER_BATCH = 3
NORMAL_COOLDOWN_MINUTES = 20
RATE_LIMIT_COOLDOWN_MINUTES = 90


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
        log["queries"].append({
            "query": query,
            "purpose": purpose,
            "reason": item.get("reason") or "",
            "status": "planned",
            "batch": None,
            "attempt_count": 0,
            "last_attempt": None,
        })
        known.add(query)
    _save(root, log)
    return status(root, brand)


def _clean(queries: Iterable[str]) -> set[str]:
    return {q.strip() for q in queries if q and q.strip()}


def _strict(batch: dict[str, Any]) -> bool:
    """A batch that hit a rate limit or went over its page budget earns the
    long cooldown and a recovery-sized next batch."""
    return bool(batch.get("rate_limited") or batch.get("over_budget"))


def check_batch(
    root: str | Path,
    brand: str,
    *,
    batch: int,
    queries_done: Iterable[str],
    pages_loaded: int,
    rate_limited: bool,
    queries_limited: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate a batch before anything is written.

    Raises on inputs that cannot be recorded truthfully. Going over the page
    budget is not an error: the pages were already loaded, so the batch is
    kept and flagged, and the next cooldown is lengthened.
    """
    if not isinstance(batch, int) or batch < 1:
        raise CollectionLogError("batch must be a positive integer")
    log = load_log(root, brand)
    if any(b["batch"] == batch for b in log["batches"]):
        raise CollectionLogError(f"batch {batch} already recorded")
    if not isinstance(pages_loaded, int) or pages_loaded < 0:
        raise CollectionLogError("pages_loaded must be a non-negative integer")
    done, limited = _clean(queries_done), _clean(queries_limited)
    if done & limited:
        raise CollectionLogError("a query cannot be both done and rate-limited")
    if limited and not rate_limited:
        raise CollectionLogError("queries_limited requires rate_limited=True")
    recovery = bool(log["batches"] and _strict(log["batches"][-1]))
    page_budget = RECOVERY_PAGES_PER_BATCH if recovery else PAGES_PER_BATCH
    return {"page_budget": page_budget, "over_budget": pages_loaded > page_budget}


def record_batch(
    root: str | Path,
    brand: str,
    *,
    batch: int,
    queries_done: Iterable[str],
    note_urls: Iterable[str],
    pages_loaded: int,
    rate_limited: bool,
    queries_limited: Iterable[str] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    budget = check_batch(root, brand, batch=batch, queries_done=queries_done, pages_loaded=pages_loaded,
                         rate_limited=rate_limited, queries_limited=queries_limited)
    log = load_log(root, brand)
    ended = (now or datetime.now()).replace(microsecond=0)
    done, limited = _clean(queries_done), _clean(queries_limited)
    attempted = done | limited
    for q in log["queries"]:
        q.setdefault("attempt_count", 0)
        q.setdefault("last_attempt", None)
        if q["query"] in attempted:
            q["attempt_count"] += 1
            q["last_attempt"] = {
                "batch": batch,
                "outcome": "done" if q["query"] in done else "rate_limited",
                "at": ended.isoformat(),
            }
        if q["query"] in done and q["status"] != "done":
            q["status"] = "done"
            q["batch"] = batch
    unknown = attempted - {q["query"] for q in log["queries"]}
    for query in sorted(unknown):
        is_done = query in done
        log["queries"].append({
            "query": query,
            "purpose": "seed",
            "reason": "",
            "status": "done" if is_done else "planned",
            "batch": batch if is_done else None,
            "attempt_count": 1,
            "last_attempt": {
                "batch": batch,
                "outcome": "done" if is_done else "rate_limited",
                "at": ended.isoformat(),
            },
        })
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
        "page_budget": budget["page_budget"],
        "over_budget": budget["over_budget"],
        "new_notes": len(new_notes),
        "rate_limited": rate_limited,
        "ended_at": ended.isoformat(),
    })
    _save(root, log)
    return status(root, brand, now=ended)


def status(root: str | Path, brand: str, *, now: datetime | None = None) -> dict[str, Any]:
    log = load_log(root, brand)
    batches = log["batches"]
    current = (now or datetime.now()).replace(microsecond=0)
    last_batch = batches[-1] if batches else None
    last_limited = next((b for b in reversed(batches) if b["rate_limited"]), None)
    cooldown_minutes = RATE_LIMIT_COOLDOWN_MINUTES if last_batch and _strict(last_batch) else NORMAL_COOLDOWN_MINUTES
    resume_after = None
    collection_allowed = True
    wait_seconds = 0
    if last_batch:
        ended = datetime.fromisoformat(last_batch["ended_at"])
        resume = ended + timedelta(minutes=cooldown_minutes)
        resume_after = resume.isoformat()
        wait_seconds = max(0, int((resume - current).total_seconds()))
        collection_allowed = wait_seconds == 0
    recovery = bool(last_batch and _strict(last_batch))
    page_budget = RECOVERY_PAGES_PER_BATCH if recovery else PAGES_PER_BATCH
    mode = "external_index_first"
    planned = []
    for query in log["queries"]:
        query.setdefault("attempt_count", 0)
        query.setdefault("last_attempt", None)
        if query["status"] == "planned":
            planned.append(query)
    return {
        "brand": log["brand"],
        "next_batch": (max((b["batch"] for b in batches), default=0) + 1),
        "collection_allowed": collection_allowed,
        "resume_after": resume_after,
        "wait_seconds": wait_seconds,
        "pages_per_batch": page_budget,
        "recommended_discovery_mode": mode,
        "planned_queries": planned,
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
