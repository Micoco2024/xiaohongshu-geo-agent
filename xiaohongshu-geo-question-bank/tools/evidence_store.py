"""File-based snapshots of brand discovery results.

Brand discovery is the only step that runs hosted web search, so its result is
saved once and reused by later question-bank generations for the same brand.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SNAPSHOT_ID_PATTERN = re.compile(r"^[^/\\.][^/\\]*/\d{8}-\d{6}$")


class EvidenceStoreError(ValueError):
    """Raised when a snapshot id or file is invalid."""


def brand_key(brand_name: str) -> str:
    """Folder name for a brand: stripped, lowercase, path-safe."""
    if not isinstance(brand_name, str) or not brand_name.strip():
        raise EvidenceStoreError("brand_name must be a non-empty string")
    key = re.sub(r"[\\/:*?\"<>|\s]+", "_", brand_name.strip().casefold()).strip("._")
    if not key:
        raise EvidenceStoreError("brand_name has no usable characters")
    return key


def save_snapshot(
    store_root: str | Path,
    brand_name: str,
    discovery: dict[str, Any],
    *,
    model: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = (now or datetime.now()).replace(microsecond=0)
    key = brand_key(brand_name)
    folder = Path(store_root) / key
    folder.mkdir(parents=True, exist_ok=True)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    snapshot = {
        "snapshot_id": f"{key}/{stamp}",
        "brand_name": brand_name.strip(),
        "created_at": created.isoformat(),
        "model": model,
        "discovery": discovery,
    }
    (folder / f"{stamp}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summarize(snapshot)


def append_batch(
    store_root: str | Path,
    brand_name: str,
    discovery: dict[str, Any],
    *,
    batch: int,
    model: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Merge one collection batch into the brand's working snapshot.

    Collection for large brands runs in several paced batches (search slows
    down after a burst). All batches share one snapshot id so coding records
    and question banks keep resolving the same evidence ids.
    """
    existing = list_snapshots(store_root, brand_name)
    if not existing:
        summary = save_snapshot(store_root, brand_name, discovery, model=model, now=now)
        snapshot = load_snapshot(store_root, summary["snapshot_id"])
        snapshot["batches"] = [_batch_entry(batch, discovery["evidence"], now)]
        _write(store_root, snapshot)
        return summarize(snapshot)

    snapshot = load_snapshot(store_root, existing[0]["snapshot_id"])
    old = snapshot["discovery"]
    known = {record["evidence_id"] for record in old["evidence"]}
    added = [record for record in discovery["evidence"] if record["evidence_id"] not in known]
    old["evidence"].extend(added)
    if old.get("brand_profile") is None and discovery.get("brand_profile") is not None:
        old["brand_profile"] = discovery["brand_profile"]
    old["usable_user_evidence_count"] = old.get("usable_user_evidence_count", 0) + sum(
        1 for r in added
        if r["status"] == "usable" and r["author_role"] in {"user", "creator", "unknown"}
        and any(u in r["usage"] for u in ("scene_signal", "intent_signal", "question_expression"))
    )
    if old["usable_user_evidence_count"] and old.get("status") == "insufficient":
        old["status"] = "ready"
    if discovery.get("coverage_note"):
        old["coverage_note"] = discovery["coverage_note"]
    old["missing_information"] = sorted(set(discovery.get("missing_information", [])))
    snapshot.setdefault("batches", []).append(_batch_entry(batch, added, now))
    _write(store_root, snapshot)
    return {**summarize(snapshot), "added": len(added), "duplicates": len(discovery["evidence"]) - len(added)}


def _batch_entry(batch: int, records: list[dict[str, Any]], now: datetime | None) -> dict[str, Any]:
    return {
        "batch": batch,
        "added_evidence_ids": [r["evidence_id"] for r in records],
        "saved_at": (now or datetime.now()).replace(microsecond=0).isoformat(),
    }


def _write(store_root: str | Path, snapshot: dict[str, Any]) -> None:
    path = Path(store_root) / f"{snapshot['snapshot_id']}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def load_snapshot(store_root: str | Path, snapshot_id: str) -> dict[str, Any]:
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_PATTERN.match(snapshot_id):
        raise EvidenceStoreError("invalid snapshot_id")
    path = Path(store_root) / f"{snapshot_id}.json"
    if not path.is_file():
        raise EvidenceStoreError("snapshot not found")
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(store_root: str | Path, brand_name: str | None = None) -> list[dict[str, Any]]:
    """Snapshot summaries, newest first."""
    root = Path(store_root)
    if not root.is_dir():
        return []
    folders = [root / brand_key(brand_name)] if brand_name else sorted(p for p in root.iterdir() if p.is_dir())
    summaries = []
    for folder in folders:
        for path in folder.glob("*.json"):
            try:
                summaries.append(summarize(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return sorted(summaries, key=lambda item: item["created_at"], reverse=True)


def summarize(snapshot: dict[str, Any]) -> dict[str, Any]:
    discovery = snapshot["discovery"]
    evidence = discovery.get("evidence", [])
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "brand_name": snapshot["brand_name"],
        "created_at": snapshot["created_at"],
        "model": snapshot.get("model"),
        "status": discovery.get("status"),
        "evidence_count": len(evidence),
        "usable_count": sum(1 for item in evidence if item.get("status") == "usable"),
        "usable_user_evidence_count": discovery.get("usable_user_evidence_count", 0),
        "batches": len(snapshot.get("batches", [])),
    }
