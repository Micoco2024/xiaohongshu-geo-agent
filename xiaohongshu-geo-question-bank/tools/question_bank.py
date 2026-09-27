"""Semantic validation for the final Xiaohongshu GEO question bank."""

from __future__ import annotations

from typing import Any, Iterable


QUESTION_TYPES = {
    "need_recognition", "how_to", "category_choice", "brand_recommendation",
    "competitor_comparison", "brand_validation", "risk_validation",
    "usage_optimization", "after_sales", "purchase_decision",
}
BRAND_VISIBILITY = {"unbranded", "branded", "context_dependent"}
DECISION_STAGES = {
    "need_recognition", "solution_exploration", "category_choice",
    "criteria_narrowing", "brand_comparison", "risk_validation",
    "purchase_decision", "usage_optimization", "after_sales",
}


class QuestionBankError(ValueError):
    """Raised when a question bank violates the delivery contract."""


def validate_question_bank(bank: dict[str, Any], known_evidence_ids: Iterable[str] | None = None) -> None:
    if not isinstance(bank, dict):
        raise QuestionBankError("question bank must be an object")
    if bank.get("schema_version") != "1.0":
        raise QuestionBankError("schema_version must be 1.0")
    target_brand = _text(bank.get("target_brand"), "target_brand")
    _text(bank.get("coverage_note"), "coverage_note")

    singles = bank.get("single_turn_questions")
    chains = bank.get("multi_turn_chains")
    if not isinstance(singles, list) or not isinstance(chains, list):
        raise QuestionBankError("single_turn_questions and multi_turn_chains must be lists")
    if not singles and not chains:
        raise QuestionBankError("question bank must contain at least one question or chain")

    known = set(known_evidence_ids) if known_evidence_ids is not None else None
    question_ids: set[str] = set()
    chain_ids: set[str] = set()
    normalized_questions: set[str] = set()

    for record in singles:
        _validate_question(record, target_brand, known, question_ids, normalized_questions)
        if record.get("test_mode") != "single_turn":
            raise QuestionBankError("single-turn question test_mode must be single_turn")
        for field in ("scene_id", "scene", "intent_id", "intent"):
            _text(record.get(field), field)

    for chain in chains:
        chain_id = _text(chain.get("question_chain_id"), "question_chain_id")
        if chain_id in chain_ids:
            raise QuestionBankError(f"duplicate chain ID: {chain_id}")
        chain_ids.add(chain_id)
        if chain.get("test_mode") != "multi_turn":
            raise QuestionBankError("multi-turn chain test_mode must be multi_turn")
        for field in ("scene_id", "scene", "intent_id", "intent"):
            _text(chain.get(field), field)
        if chain.get("target_brand") != target_brand:
            raise QuestionBankError(f"chain {chain_id} target_brand differs from question bank")
        turns = chain.get("turns")
        if not isinstance(turns, list) or len(turns) < 2:
            raise QuestionBankError(f"chain {chain_id} must contain at least two turns")
        for position, turn in enumerate(turns, start=1):
            if turn.get("turn") != position:
                raise QuestionBankError(f"chain {chain_id} turns must be contiguous from 1")
            _validate_question(turn, target_brand, known, question_ids, normalized_questions, is_turn=True)


def _validate_question(
    record: dict[str, Any],
    target_brand: str,
    known: set[str] | None,
    question_ids: set[str],
    normalized_questions: set[str],
    *,
    is_turn: bool = False,
) -> None:
    if not isinstance(record, dict):
        raise QuestionBankError("question record must be an object")
    question_id = _text(record.get("question_id"), "question_id")
    if question_id in question_ids:
        raise QuestionBankError(f"duplicate question ID: {question_id}")
    question_ids.add(question_id)

    question = _text(record.get("question"), "question")
    normalized = "".join(question.split()).casefold()
    if normalized in normalized_questions:
        raise QuestionBankError(f"duplicate question text: {question}")
    normalized_questions.add(normalized)

    _choice(record.get("question_type"), QUESTION_TYPES, "question_type")
    _choice(record.get("brand_visibility"), BRAND_VISIBILITY, "brand_visibility")
    _choice(record.get("decision_stage"), DECISION_STAGES, "decision_stage")
    if not is_turn and record.get("target_brand") != target_brand:
        raise QuestionBankError(f"question {question_id} target_brand differs from question bank")

    variants = record.get("question_variants")
    if not isinstance(variants, list) or any(not isinstance(v, str) or not v.strip() for v in variants):
        raise QuestionBankError(f"question {question_id} variants must be non-empty strings")
    if len(variants) != len(set(variants)) or question in variants:
        raise QuestionBankError(f"question {question_id} contains duplicate variants")

    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)):
        raise QuestionBankError(f"question {question_id} requires unique evidence references")
    if known is not None:
        missing = sorted(set(refs) - known)
        if missing:
            raise QuestionBankError(f"question {question_id} references unknown evidence: {missing}")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuestionBankError(f"{field} must be a non-empty string")
    return value


def _choice(value: Any, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise QuestionBankError(f"{field} must be one of {sorted(allowed)}")
