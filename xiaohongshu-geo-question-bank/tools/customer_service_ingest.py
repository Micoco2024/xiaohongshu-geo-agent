"""Parse authorized customer-service exports into shared evidence records."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from evidence_registry import build_evidence_record, make_evidence_id


class CustomerServiceInputError(ValueError):
    """Raised when a customer-service document cannot be safely normalized."""


def parse_customer_service_document(filename: str, content: str) -> list[dict[str, Any]]:
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if not isinstance(content, str) or not content.strip():
        raise CustomerServiceInputError("customer-service document is empty")
    if suffix == ".csv":
        rows = list(csv.DictReader(io.StringIO(content)))
    elif suffix == ".json":
        value = json.loads(content)
        rows = value.get("records", []) if isinstance(value, dict) else value
        if not isinstance(rows, list):
            raise CustomerServiceInputError("JSON must be an array or contain a records array")
    elif suffix == ".txt":
        rows = [
            {"text": line, "speaker": "customer", "turn": index, "conversation_id": f"{name}-text"}
            for index, line in enumerate(content.splitlines(), start=1)
            if line.strip()
        ]
    else:
        raise CustomerServiceInputError("first real-data test supports CSV, JSON, and TXT")
    return _normalize_rows(name, rows)


def _normalize_rows(filename: str, rows: list[Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            raise CustomerServiceInputError(f"row {index} must be an object")
        text = redact_text(str(raw.get("text") or raw.get("question") or "").strip())
        if not text:
            continue
        speaker_value = str(raw.get("speaker") or "customer").strip().casefold()
        is_customer = speaker_value in {"customer", "user", "客户", "用户", "消费者"}
        author_role = "user" if is_customer else "customer_service_agent"
        conversation = str(raw.get("conversation_id") or raw.get("conversation_ref") or f"{filename}-row-{index}").strip()
        try:
            turn = int(raw.get("turn") or index)
        except (TypeError, ValueError) as error:
            raise CustomerServiceInputError(f"row {index} turn must be an integer") from error
        source_ref = f"customer-service://{filename}#{index}"
        prepared.append({
            "index": index,
            "conversation": conversation,
            "turn": turn,
            "source_ref": source_ref,
            "text": text,
            "author_role": author_role,
            "context": redact_text(str(raw.get("context") or "").strip()),
        })

    prepared.sort(key=lambda item: (item["conversation"], item["turn"], item["index"]))
    previous_by_conversation: dict[str, str] = {}
    records = []
    for item in prepared:
        parent_id = previous_by_conversation.get(item["conversation"])
        usage = ["brand_fact"] if item["author_role"] == "customer_service_agent" else [
            "question_expression", "scene_signal", "intent_signal"
        ]
        record = build_evidence_record(
            provenance="customer_service",
            source_type="customer_service_message",
            source_ref=item["source_ref"],
            author_role=item["author_role"],
            text=item["text"],
            context=f"conversation={item['conversation']}; turn={item['turn']}; {item['context']}",
            parent_evidence_id=parent_id,
            usage=usage,
        )
        previous_by_conversation[item["conversation"]] = make_evidence_id(item["source_ref"], item["text"])
        records.append(record)
    return records


def redact_text(text: str) -> str:
    """Remove common direct identifiers before model processing."""
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已脱敏]", text)
    text = re.sub(r"(?<!\d)\d{12,}(?!\d)", "[编号已脱敏]", text)
    return text
