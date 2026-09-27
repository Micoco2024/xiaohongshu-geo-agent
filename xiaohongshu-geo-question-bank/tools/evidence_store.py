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
    }
