"""Brand-name-only discovery using Claude web search and web fetch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from brand_profile import validate_brand_profile
from evidence_registry import build_evidence_record
from claude_client import DEFAULT_MODEL, ClaudeCallError, build_request, call_json, web_tools


class BrandDiscoveryError(RuntimeError):
    """Raised when automatic brand discovery cannot produce a safe result."""


def build_discovery_request(
    brand_name: str,
    discovery_schema: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    if not isinstance(brand_name, str) or not brand_name.strip():
        raise BrandDiscoveryError("brand_name must be a non-empty string")
    requested = brand_name.strip()
    instructions = (
        "你是小红书 GEO 研究的品牌发现器。输入只有品牌名称。必须先用 web_search 搜索，再用 web_fetch 打开值得引用的页面，围绕品牌别名、品类、"
        "产品、使用场景、痛点、比较、购买决策、评论和追问进行多轮发现。只把 xiaohongshu.com 页面写入"
        " source_ref。品牌官方页只能支持品牌事实，不能支持用户需求。text 必须是页面中的短原文摘录，"
        "不得改写。只有用 web_fetch 实际打开页面并看到原文时 verification 才能为 opened_page；仅看到搜索结果标题或"
        "摘要时必须为 search_result_only。无法消歧则 status=ambiguous；缺少足以生成问题库的用户表达则"
        "status=insufficient。不得声称覆盖全部内容、搜索量、热度、排名或算法信息。严格输出指定 JSON。"
    )
    return build_request(
        system=instructions,
        user=f"目标品牌：{requested}",
        schema=discovery_schema,
        model=model,
        tools=web_tools(model, ["xiaohongshu.com"], max_searches=15, max_fetches=20),
    )


def discover_brand(
    *,
    api_key: str,
    brand_name: str,
    discovery_schema: dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    body = build_discovery_request(brand_name, discovery_schema, model=model)
    try:
        raw = call_json(api_key, body)
    except ClaudeCallError as error:
        raise BrandDiscoveryError(str(error)) from error
    return normalize_discovery_result(brand_name, raw)


def normalize_discovery_result(brand_name: str, raw: dict[str, Any]) -> dict[str, Any]:
    requested = brand_name.strip()
    if raw.get("requested_brand_name", "").strip() != requested:
        raise BrandDiscoveryError("discovery result does not match the requested brand")

    records = []
    for item in raw.get("evidence", []):
        if not _is_xiaohongshu_url(item.get("source_ref")):
            continue
        verification = item.get("verification")
        status = "usable" if verification == "opened_page" else "candidate"
        records.append(build_evidence_record(
            provenance="public_page",
            source_type=item["source_type"],
            source_ref=item["source_ref"],
            author_role=item["author_role"],
            text=item["text"],
            context=item["context"],
            usage=item["usage"],
            status=status,
            exclusion_reason=None,
        ))

    usable_user_evidence = [
        record for record in records
        if record["status"] == "usable"
        and record["author_role"] in {"user", "creator", "unknown"}
        and any(value in record["usage"] for value in ("scene_signal", "intent_signal", "question_expression"))
    ]

    result_status = raw.get("status")
    resolved = raw.get("resolved_brand_name")
    category_scope = _unique_strings(raw.get("category_scope", []))
    products = []
    for product in raw.get("products", []):
        refs = _xiaohongshu_refs(product.get("source_refs", []))
        products.append({
            "product_id": None,
            "name": product["name"].strip(),
            "aliases": [],
            "category": product.get("category"),
            "attributes": _unique_strings(product.get("attributes", [])),
            "faq": [],
            "fact_status": product["fact_status"],
            "source_refs": refs,
        })

    profile = None
    if result_status != "ambiguous" and resolved and (category_scope or products):
        profile = {
            "schema_version": "1.0",
            "input_mode": "public_evidence",
            "brand": {
                "brand_id": None,
                "name": resolved.strip(),
                "aliases": _unique_strings(raw.get("aliases", [])),
                "category_scope": category_scope,
                "source_refs": sorted({ref for product in products for ref in product["source_refs"]}),
            },
            "products": products,
            "competitors": [
                {
                    "name": item["name"].strip(),
                    "aliases": _unique_strings(item.get("aliases", [])),
                    "source_refs": _xiaohongshu_refs(item.get("source_refs", [])),
                }
                for item in raw.get("competitors", [])
            ],
            "ambiguous_terms": [],
            "missing_facts": [
                {"field": value, "reason": "自动公开发现未能验证"}
                for value in _unique_strings(raw.get("missing_information", []))
            ],
        }
        validate_brand_profile(profile)

    if result_status == "ready" and not usable_user_evidence:
        result_status = "insufficient"

    return {
        "status": result_status,
        "brand_profile": profile,
        "evidence": records,
        "coverage_note": raw.get("coverage_note", "").strip(),
        "missing_information": _unique_strings(raw.get("missing_information", [])),
        "usable_user_evidence_count": len(usable_user_evidence),
    }


def load_discovery_schema(skill_root: str | Path) -> dict[str, Any]:
    return json.loads((Path(skill_root) / "schemas" / "brand-discovery.schema.json").read_text(encoding="utf-8"))


def _is_xiaohongshu_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    hostname = (urlparse(value).hostname or "").lower()
    return hostname == "xiaohongshu.com" or hostname.endswith(".xiaohongshu.com")


def _xiaohongshu_refs(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({value.strip() for value in values if _is_xiaohongshu_url(value)})


def _unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))
