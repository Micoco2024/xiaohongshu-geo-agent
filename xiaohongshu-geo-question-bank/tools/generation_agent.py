"""Claude adapter for evidence-grounded GEO question generation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from brand_profile import validate_brand_profile
from claude_client import DEFAULT_MODEL, ClaudeCallError, build_request, call_json
from evidence_registry import validate_evidence_record
from question_bank import validate_question_bank


class AgentRuntimeError(RuntimeError):
    """Raised when generation cannot return a valid question bank."""


def build_generation_request(
    brand_profile: dict[str, Any],
    evidence: list[dict[str, Any]],
    question_bank_schema: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    validate_brand_profile(brand_profile)
    if not evidence:
        raise AgentRuntimeError("at least one evidence record is required")
    for record in evidence:
        validate_evidence_record(record)

    usable = [record for record in evidence if record["status"] == "usable"]
    if not usable:
        raise AgentRuntimeError("at least one usable evidence record is required")

    system_prompt = (
        "你是小红书品牌场景与用户意图洞察 Agent。只依据输入中的品牌资料、小红书公开证据和授权客服问题工作。"
        "先在内部做意义单元编码、场景识别、问题路径与潜在意图分析，再输出 GEO 问题库。"
        "商家或品牌资料只能证明品牌事实，不能证明用户需求。客服问题可以证明真实咨询，但不能证明小红书平台覆盖率。不得声称搜索量、平台覆盖、排序或算法权重。"
        "每个问题必须引用实际支持它的 evidence_id；证据不足时宁可少生成。"
        "多轮链必须表达意图逐步显现，不得把跨用户材料伪装成同一用户的真实连续对话。"
        "不得加入优先级、置信度、证据等级、生成日期或复核日期。严格输出指定 JSON。"
    )
    input_payload = {
        "brand_profile": brand_profile,
        "evidence": usable,
        "task": "生成精简、去重、可追溯的单轮与多轮 GEO 测试问题库。",
    }
    return build_request(
        system=system_prompt,
        user=json.dumps(input_payload, ensure_ascii=False),
        schema=prepare_strict_output_schema(question_bank_schema),
        model=model,
    )


def generate_question_bank(
    *,
    api_key: str,
    brand_profile: dict[str, Any],
    evidence: list[dict[str, Any]],
    question_bank_schema: dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    body = build_generation_request(
        brand_profile,
        evidence,
        question_bank_schema,
        model=model,
    )
    try:
        result = call_json(api_key, body)
    except ClaudeCallError as error:
        raise AgentRuntimeError(str(error)) from error
    validate_question_bank(result, [record["evidence_id"] for record in evidence])
    return result


def load_question_bank_schema(skill_root: str | Path) -> dict[str, Any]:
    path = Path(skill_root) / "schemas" / "question-bank.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert the canonical schema to the subset Claude structured outputs support."""
    root = copy.deepcopy(schema)
    definitions = root.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node and node["$ref"].startswith("#/$defs/"):
            name = node["$ref"].split("/")[-1]
            return resolve(copy.deepcopy(definitions[name]))
        if "allOf" in node:
            merged: dict[str, Any] = {}
            for part in node["allOf"]:
                merged = _deep_merge(merged, resolve(part))
            node = merged
        else:
            node = {key: resolve(value) for key, value in node.items()}

        for unsupported in ("$schema", "$id", "title", "allOf", "not", "if", "then", "else"):
            node.pop(unsupported, None)
        # Claude structured outputs reject these; validate_question_bank still enforces them.
        for unsupported in ("minLength", "maxLength", "minimum", "maximum", "multipleOf", "pattern", "uniqueItems", "maxItems"):
            node.pop(unsupported, None)
        if node.get("minItems", 0) > 1:
            node.pop("minItems")
        if node.get("type") == "object":
            properties = node.get("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(properties.keys())
        return node

    prepared = resolve(root)
    prepared.pop("anyOf", None)
    prepared.pop("$defs", None)
    return prepared


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(left)
    for key, value in right.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key == "required" and key in result:
            result[key] = list(dict.fromkeys([*result[key], *value]))
        elif value != {}:
            result[key] = copy.deepcopy(value)
    return result
