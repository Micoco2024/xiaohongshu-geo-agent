"""Deterministic evidence registration for Xiaohongshu GEO research."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


PROVENANCE = {"public_page", "customer_service", "merchant_api", "user_supplied"}
SOURCE_TYPES = {
    "post",
    "comment",
    "reply",
    "official_brand_page",
    "shop_page",
    "product_page",
    "merchant_api_record",
    "user_document",
    "customer_service_message",
    "customer_service_ticket",
}
AUTHOR_ROLES = {"user", "creator", "brand", "merchant", "customer_service_agent", "unknown"}
USAGES = {
    "brand_fact",
    "scene_signal",
    "intent_signal",
    "question_expression",
    "contradiction",
}
STATUSES = {"usable", "candidate", "excluded"}


class EvidenceError(ValueError):
    """Raised when an evidence record violates the shared contract."""


def make_evidence_id(source_ref: str, text: str) -> str:
    """Return a stable ID for the same source reference and exact excerpt."""
    source_ref = _required_text(source_ref, "source_ref")
    text = _required_text(text, "text")
    payload = f"{source_ref.strip()}\n{text.strip()}".encode("utf-8")
    return f"EV-{hashlib.sha256(payload).hexdigest()[:12].upper()}"


def build_evidence_record(
    *,
    provenance: str,
    source_type: str,
    source_ref: str,
    author_role: str,
    text: str,
    usage: Iterable[str],
    context: str = "",
    parent_evidence_id: str | None = None,
    status: str = "usable",
    exclusion_reason: str | None = None,
) -> dict[str, Any]:
    record = {
        "evidence_id": make_evidence_id(source_ref, text),
        "provenance": provenance,
        "source_type": source_type,
        "source_ref": source_ref.strip(),
        "author_role": author_role,
        "text": text.strip(),
        "context": context.strip(),
        "parent_evidence_id": parent_evidence_id,
        "usage": list(usage),
        "status": status,
        "exclusion_reason": exclusion_reason,
    }
    validate_evidence_record(record)
    return record


def validate_evidence_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise EvidenceError("evidence record must be an object")

    expected_id = make_evidence_id(record.get("source_ref", ""), record.get("text", ""))
    if record.get("evidence_id") != expected_id:
        raise EvidenceError(f"evidence_id must equal deterministic ID {expected_id}")

    _choice(record.get("provenance"), PROVENANCE, "provenance")
    _choice(record.get("source_type"), SOURCE_TYPES, "source_type")
    _choice(record.get("author_role"), AUTHOR_ROLES, "author_role")
    _choice(record.get("status"), STATUSES, "status")
    _required_text(record.get("source_ref"), "source_ref")
    _required_text(record.get("text"), "text")

    context = record.get("context")
    if not isinstance(context, str):
        raise EvidenceError("context must be a string")

    parent_id = record.get("parent_evidence_id")
    if parent_id is not None and not _valid_evidence_id(parent_id):
        raise EvidenceError("parent_evidence_id must be null or a valid evidence ID")

    usage = record.get("usage")
    if not isinstance(usage, list) or not usage:
        raise EvidenceError("usage must be a non-empty list")
    if len(usage) != len(set(usage)):
        raise EvidenceError("usage must not contain duplicates")
    invalid_usage = sorted(set(usage) - USAGES)
    if invalid_usage:
        raise EvidenceError(f"usage contains unsupported values: {invalid_usage}")

    reason = record.get("exclusion_reason")
    if reason is not None and not isinstance(reason, str):
        raise EvidenceError("exclusion_reason must be a string or null")
    if record["status"] == "excluded" and not (isinstance(reason, str) and reason.strip()):
        raise EvidenceError("excluded evidence requires exclusion_reason")


class EvidenceRegistry:
    """Collect unique, validated evidence records and export JSON Lines."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def add(self, record: dict[str, Any]) -> str:
        validate_evidence_record(record)
        evidence_id = record["evidence_id"]
        existing = self._records.get(evidence_id)
        if existing is not None and existing != record:
            raise EvidenceError(f"conflicting record for {evidence_id}")
        self._records[evidence_id] = record
        return evidence_id

    def records(self) -> list[dict[str, Any]]:
        return [self._records[key] for key in sorted(self._records)]

    def write_jsonl(self, path: str | Path) -> None:
        lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in self.records()]
        Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{field} must be a non-empty string")
    return value


def _choice(value: Any, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise EvidenceError(f"{field} must be one of {sorted(allowed)}")


def _valid_evidence_id(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("EV-") or len(value) != 15:
        return False
    return all(character in "0123456789ABCDEF" for character in value[3:])
