"""Grounded-theory coding records: validation and saturation.

The model does the interpretive work (coding, comparing, memo writing). This
module keeps it traceable and decides the mechanical parts: every code cites
real evidence, every level builds on the level below, and saturation is
computed from the batches rather than claimed.

Record shape (one JSON file per brand, rewritten after every batch):

{
  "brand": "...",
  "open_codes":    [{"code_id": "OC-001", "label": "赶早八前找地方坐一会儿",
                     "in_vivo": false, "evidence_refs": ["EV-..."], "batch": 1}],
  "focused_codes": [{"code_id": "FC-001", "label": "...", "open_codes": ["OC-001", ...],
                     "batch": 1}],
  "categories":    [{"category_id": "CAT-001", "label": "...",
                     "properties": [{"name": "...", "dimension": "从...到...",
                                     "batch": 1}],
                     "paradigm": {"conditions": ["FC-..."], "context": ["FC-..."],
                                  "actions": ["FC-..."], "consequences": ["FC-..."]},
                     "negative_cases": ["EV-..."]}],
  "core_category": {"label": "...", "category_ids": ["CAT-001", ...]} | null,
  "memos":         [{"memo_id": "M-001", "batch": 1, "about": ["FC-001"], "text": "..."}],
  "sampling":      [{"after_batch": 1, "gap": "...", "next_queries": ["..."]}]
}
"""

from __future__ import annotations

import re
from typing import Any, Iterable


PARADIGM_PARTS = ("conditions", "context", "actions", "consequences")
ID_PATTERNS = {
    "open": re.compile(r"^OC-\d{3,}$"),
    "focused": re.compile(r"^FC-\d{3,}$"),
    "category": re.compile(r"^CAT-\d{3,}$"),
    "memo": re.compile(r"^M-\d{3,}$"),
}
# Two consecutive batches with nothing new at the focused-code or property
# level is the stopping signal for theoretical sampling.
SATURATION_WINDOW = 2


class CodingError(ValueError):
    """Raised when a coding record is not traceable or not well formed."""


def validate_coding(coding: dict[str, Any], usable_evidence_ids: Iterable[str]) -> list[str]:
    """Raise on structural errors; return warnings that need analyst attention."""
    evidence = set(usable_evidence_ids)
    warnings: list[str] = []

    open_codes = _items(coding, "open_codes")
    open_ids = _unique_ids(open_codes, "code_id", "open")
    for code in open_codes:
        _text(code, "label")
        _batch(code)
        refs = code.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise CodingError(f"{code['code_id']}: open code must cite evidence")
        unknown = [r for r in refs if r not in evidence]
        if unknown:
            raise CodingError(f"{code['code_id']}: cites unknown or unusable evidence {unknown}")
        if len(code["label"]) <= 4:
            warnings.append(f"{code['code_id']}: 标签「{code['label']}」过短，开放编码应写成动作或过程，而非名词")

    focused = _items(coding, "focused_codes")
    focused_ids = _unique_ids(focused, "code_id", "focused")
    used_open: set[str] = set()
    for code in focused:
        _text(code, "label")
        _batch(code)
        members = code.get("open_codes")
        if not isinstance(members, list) or not members:
            raise CodingError(f"{code['code_id']}: focused code must group open codes")
        missing = [m for m in members if m not in open_ids]
        if missing:
            raise CodingError(f"{code['code_id']}: unknown open codes {missing}")
        used_open.update(members)
        if len(_evidence_of(code, open_codes)) < 2:
            warnings.append(f"{code['code_id']}: 只有 1 条证据支撑，需在后续批次持续比较")

    unplaced = sorted(open_ids - used_open)
    if unplaced:
        warnings.append(f"{len(unplaced)} 个开放编码尚未归入聚焦编码：{', '.join(unplaced[:8])}")

    categories = _items(coding, "categories")
    category_ids = _unique_ids(categories, "category_id", "category")
    for cat in categories:
        _text(cat, "label")
        paradigm = cat.get("paradigm")
        if not isinstance(paradigm, dict):
            raise CodingError(f"{cat['category_id']}: paradigm is required")
        for part in PARADIGM_PARTS:
            refs = paradigm.get(part, [])
            if not isinstance(refs, list):
                raise CodingError(f"{cat['category_id']}: paradigm.{part} must be a list")
            missing = [r for r in refs if r not in focused_ids]
            if missing:
                raise CodingError(f"{cat['category_id']}: paradigm.{part} has unknown focused codes {missing}")
        empty = [part for part in PARADIGM_PARTS if not paradigm.get(part)]
        if empty:
            warnings.append(f"{cat['category_id']}: 范式缺少 {', '.join(empty)}，这是下一轮理论抽样的方向")
        props = cat.get("properties", [])
        if not isinstance(props, list) or not props:
            warnings.append(f"{cat['category_id']}: 还没有属性与维度")
        for prop in props if isinstance(props, list) else []:
            _text(prop, "name")
            _batch(prop)
        bad_neg = [e for e in cat.get("negative_cases", []) if e not in evidence]
        if bad_neg:
            raise CodingError(f"{cat['category_id']}: negative cases cite unknown evidence {bad_neg}")

    core = coding.get("core_category")
    if core is not None:
        if not isinstance(core, dict):
            raise CodingError("core_category must be an object or null")
        _text(core, "label")
        missing = [c for c in core.get("category_ids", []) if c not in category_ids]
        if missing:
            raise CodingError(f"core_category links unknown categories {missing}")

    memo_ids = _unique_ids(_items(coding, "memos"), "memo_id", "memo")
    known = open_ids | focused_ids | category_ids
    for memo in _items(coding, "memos"):
        _text(memo, "text")
        _batch(memo)
        missing = [a for a in memo.get("about", []) if a not in known]
        if missing:
            raise CodingError(f"{memo['memo_id']}: about unknown ids {missing}")
    if categories and not memo_ids:
        warnings.append("没有备忘录：每批次至少写一条，记录比较与类属形成的理由")

    return warnings


def saturation(coding: dict[str, Any]) -> dict[str, Any]:
    """New focused codes and new category properties per batch.

    Saturated when the last SATURATION_WINDOW batches added neither, and at
    least SATURATION_WINDOW + 1 batches exist.
    """
    batches = sorted({
        item["batch"]
        for key in ("open_codes", "focused_codes")
        for item in coding.get(key, [])
        if isinstance(item.get("batch"), int)
    })
    per_batch = []
    for batch in batches:
        new_focused = sum(1 for c in coding.get("focused_codes", []) if c.get("batch") == batch)
        new_props = sum(
            1 for cat in coding.get("categories", [])
            for p in cat.get("properties", []) if p.get("batch") == batch
        )
        new_open = sum(1 for c in coding.get("open_codes", []) if c.get("batch") == batch)
        per_batch.append({"batch": batch, "new_open_codes": new_open,
                          "new_focused_codes": new_focused, "new_properties": new_props})
    tail = per_batch[-SATURATION_WINDOW:]
    saturated = (
        len(per_batch) > SATURATION_WINDOW
        and all(b["new_focused_codes"] == 0 and b["new_properties"] == 0 for b in tail)
    )
    return {"batches": per_batch, "saturated": saturated,
            "rule": f"最近 {SATURATION_WINDOW} 批没有新的聚焦编码和属性，且至少 {SATURATION_WINDOW + 1} 批"}


def check_bank_against_coding(bank: dict[str, Any], coding: dict[str, Any]) -> None:
    """Every question's scene must be a category of the coding record."""
    categories = {c["category_id"] for c in coding.get("categories", [])}
    scene_ids = {q.get("scene_id") for q in bank.get("single_turn_questions", [])}
    scene_ids |= {c.get("scene_id") for c in bank.get("multi_turn_chains", [])}
    missing = sorted(s for s in scene_ids if s not in categories)
    if missing:
        raise CodingError(f"question scene_id must be a category_id from the coding record: {missing}")


def _items(coding: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = coding.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise CodingError(f"{key} must be a list of objects")
    return value


def _unique_ids(items: list[dict[str, Any]], field: str, kind: str) -> set[str]:
    seen: set[str] = set()
    for item in items:
        value = item.get(field)
        if not isinstance(value, str) or not ID_PATTERNS[kind].match(value):
            raise CodingError(f"invalid {field}: {value!r}")
        if value in seen:
            raise CodingError(f"duplicate {field}: {value}")
        seen.add(value)
    return seen


def _text(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CodingError(f"{field} is required")
    return value


def _batch(item: dict[str, Any]) -> None:
    if not isinstance(item.get("batch"), int) or item["batch"] < 1:
        raise CodingError(f"{item.get('code_id') or item.get('memo_id') or item.get('name')}: batch must be a positive integer")


def _evidence_of(focused_code: dict[str, Any], open_codes: list[dict[str, Any]]) -> set[str]:
    members = set(focused_code["open_codes"])
    return {ref for code in open_codes if code["code_id"] in members for ref in code["evidence_refs"]}
