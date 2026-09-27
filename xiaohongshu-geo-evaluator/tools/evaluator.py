"""Independent deterministic gates for Xiaohongshu GEO question banks."""

from __future__ import annotations

from typing import Any


FORBIDDEN_FIELDS = {
    "priority",
    "priority_score",
    "evidence_grade",
    "confidence",
    "generation_date",
    "review_date",
    "expected_recommendation_outcome",
    "target_brand_role",
    "scene_type",
}


def run_deterministic_evaluation(
    question_bank: dict[str, Any],
    evidence_records: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    target_brand = question_bank.get("target_brand", "")
    evidence_ids = {
        item.get("evidence_id")
        for item in evidence_records
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }

    _check(checks, "top_level_contract", _valid_top_level(question_bank), "问题库顶层字段完整", [])

    question_ids: list[str] = []
    chain_ids: list[str] = []
    unresolved: set[str] = set()
    unordered_chains: list[str] = []
    brand_leaks: list[str] = []
    texts: list[tuple[str, str]] = []

    for question in question_bank.get("single_turn_questions", []):
        if not isinstance(question, dict):
            continue
        question_id = question.get("question_id", "")
        question_ids.append(question_id)
        texts.append((question_id, _normalize_text(question.get("question", ""))))
        unresolved.update(set(question.get("evidence_refs", [])) - evidence_ids)
        if _brand_leaks(question, target_brand):
            brand_leaks.append(question_id)

    for chain in question_bank.get("multi_turn_chains", []):
        if not isinstance(chain, dict):
            continue
        chain_id = chain.get("question_chain_id", "")
        chain_ids.append(chain_id)
        turns = chain.get("turns", [])
        if not isinstance(turns, list) or len(turns) < 2 or [t.get("turn") for t in turns if isinstance(t, dict)] != list(range(1, len(turns) + 1)):
            unordered_chains.append(chain_id)
        for turn in turns if isinstance(turns, list) else []:
            if not isinstance(turn, dict):
                continue
            question_id = turn.get("question_id", "")
            question_ids.append(question_id)
            texts.append((question_id, _normalize_text(turn.get("question", ""))))
            unresolved.update(set(turn.get("evidence_refs", [])) - evidence_ids)
            if _brand_leaks(turn, target_brand):
                brand_leaks.append(question_id)

    duplicate_ids = _duplicates(question_ids)
    duplicate_chain_ids = _duplicates(chain_ids)
    duplicate_text_refs = _duplicate_text_refs(texts)
    forbidden = _find_forbidden_fields(question_bank)

    _check(checks, "question_ids_unique", not duplicate_ids, "问题 ID 唯一", duplicate_ids)
    _check(checks, "chain_ids_unique", not duplicate_chain_ids, "问题链 ID 唯一", duplicate_chain_ids)
    _check(checks, "evidence_refs_resolve", not unresolved, "所有证据引用均可解析", sorted(unresolved))
    _check(checks, "multi_turn_order", not unordered_chains, "多轮问题按连续轮次排列且至少两轮", unordered_chains)
    _check(checks, "unbranded_no_brand_leak", not brand_leaks, "无品牌问题未泄漏目标品牌", brand_leaks)
    _check(checks, "exact_text_unique", not duplicate_text_refs, "问题正文不存在精确重复", duplicate_text_refs)
    _check(checks, "forbidden_fields_absent", not forbidden, "最终问题库未包含已排除字段", forbidden)

    failed = [check for check in checks if check["status"] == "fail"]
    return {
        "schema_version": "1.0",
        "target_brand": target_brand,
        "release_decision": "fail" if failed else "review_required",
        "deterministic_checks": checks,
        "findings": [],
        "live_test_status": "not_run",
        "live_observations": [],
        "required_fixes": [check["details"] for check in failed],
    }


def _valid_top_level(bank: Any) -> bool:
    return (
        isinstance(bank, dict)
        and bank.get("schema_version") == "1.0"
        and isinstance(bank.get("target_brand"), str)
        and bool(bank.get("target_brand", "").strip())
        and isinstance(bank.get("coverage_note"), str)
        and isinstance(bank.get("single_turn_questions"), list)
        and isinstance(bank.get("multi_turn_chains"), list)
        and bool(bank.get("single_turn_questions") or bank.get("multi_turn_chains"))
    )


def _brand_leaks(question: dict[str, Any], target_brand: str) -> bool:
    return (
        question.get("brand_visibility") == "unbranded"
        and bool(target_brand)
        and target_brand.casefold() in str(question.get("question", "")).casefold()
    )


def _normalize_text(value: Any) -> str:
    return "".join(str(value).split()).casefold()


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _duplicate_text_refs(values: list[tuple[str, str]]) -> list[str]:
    by_text: dict[str, list[str]] = {}
    for ref, text in values:
        if text:
            by_text.setdefault(text, []).append(ref)
    return sorted(ref for refs in by_text.values() if len(refs) > 1 for ref in refs)


def _find_forbidden_fields(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_FIELDS:
                found.append(child_path)
            found.extend(_find_forbidden_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_fields(child, f"{path}[{index}]"))
    return found


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: str, refs: list[str]) -> None:
    checks.append({
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "details": details,
        "object_refs": refs,
    })
