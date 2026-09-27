"""Validation for content briefs derived from the shared insight core."""

from __future__ import annotations

from typing import Any


CONTENT_TYPES = {
    "explainer", "comparison", "how_to", "checklist", "risk_clarification",
    "usage_guide", "faq", "experience_story",
}
BRAND_ENTRY = {"direct_fit", "conditional_fit", "education_only", "not_supported"}
DEMAND_USAGES = {"scene_signal", "intent_signal", "question_expression", "contradiction"}


class ContentGuidanceError(ValueError):
    """Raised when content guidance violates its evidence or structure rules."""


def validate_content_guidance(
    guidance: dict[str, Any],
    evidence_records: list[dict[str, Any]],
    known_question_ids: set[str] | None = None,
) -> None:
    if not isinstance(guidance, dict) or guidance.get("schema_version") != "1.0":
        raise ContentGuidanceError("content guidance must be a version 1.0 object")
    _text(guidance.get("target_brand"), "target_brand")
    _text(guidance.get("coverage_note"), "coverage_note")
    briefs = guidance.get("briefs")
    if not isinstance(briefs, list) or not briefs:
        raise ContentGuidanceError("briefs must be a non-empty list")

    evidence = {
        record.get("evidence_id"): record
        for record in evidence_records
        if isinstance(record, dict) and isinstance(record.get("evidence_id"), str)
    }
    brief_ids: set[str] = set()
    for index, brief in enumerate(briefs):
        prefix = f"briefs[{index}]"
        if not isinstance(brief, dict):
            raise ContentGuidanceError(f"{prefix} must be an object")
        brief_id = _text(brief.get("content_brief_id"), f"{prefix}.content_brief_id")
        if brief_id in brief_ids:
            raise ContentGuidanceError(f"duplicate content brief ID: {brief_id}")
        brief_ids.add(brief_id)
        for field in ("scene_id", "scene", "intent_id", "intent", "content_job", "content_angle"):
            _text(brief.get(field), f"{prefix}.{field}")
        _choice(brief.get("content_type"), CONTENT_TYPES, f"{prefix}.content_type")
        _choice(brief.get("brand_entry"), BRAND_ENTRY, f"{prefix}.brand_entry")
        for field in ("user_questions", "must_answer", "user_language", "proof_requirements", "brand_entry_conditions", "claim_boundaries", "evidence_refs", "question_refs"):
            _string_list(brief.get(field), f"{prefix}.{field}", required=field in {"user_questions", "must_answer", "evidence_refs"})

        if brief["brand_entry"] == "conditional_fit" and not brief["brand_entry_conditions"]:
            raise ContentGuidanceError(f"{prefix} conditional_fit requires brand_entry_conditions")
        if known_question_ids is not None:
            missing_questions = sorted(set(brief["question_refs"]) - known_question_ids)
            if missing_questions:
                raise ContentGuidanceError(f"{prefix} references unknown questions: {missing_questions}")

        missing_evidence = sorted(set(brief["evidence_refs"]) - set(evidence))
        if missing_evidence:
            raise ContentGuidanceError(f"{prefix} references unknown evidence: {missing_evidence}")
        supporting_records = [evidence[ref] for ref in brief["evidence_refs"]]
        demand_supported = any(
            record.get("status") == "usable"
            and record.get("author_role") in {"user", "creator", "unknown"}
            and bool(set(record.get("usage", [])) & DEMAND_USAGES)
            for record in supporting_records
        )
        if not demand_supported:
            raise ContentGuidanceError(f"{prefix} requires usable non-brand demand evidence")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentGuidanceError(f"{field} must be a non-empty string")
    return value


def _choice(value: Any, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise ContentGuidanceError(f"{field} must be one of {sorted(allowed)}")


def _string_list(value: Any, field: str, *, required: bool) -> None:
    if not isinstance(value, list) or (required and not value):
        raise ContentGuidanceError(f"{field} must be {'a non-empty' if required else 'an'} array")
    if len(value) != len(set(value)):
        raise ContentGuidanceError(f"{field} must not contain duplicates")
    for index, item in enumerate(value):
        _text(item, f"{field}[{index}]")
