"""End-to-end brand-name-only orchestration for the GEO question-bank agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from brand_discovery import discover_brand, load_discovery_schema
from brand_profile import validate_brand_profile
from evidence_registry import validate_evidence_record
from generation_agent import generate_question_bank, load_question_bank_schema


DiscoveryFunction = Callable[..., dict[str, Any]]
GenerationFunction = Callable[..., dict[str, Any]]
MerchantEnricher = Callable[[dict[str, Any]], dict[str, Any]]


def run_brand_agent(
    *,
    brand_name: str,
    api_key: str,
    skill_root: str | Path,
    merchant_enricher: MerchantEnricher | None = None,
    customer_service_evidence: list[dict[str, Any]] | None = None,
    model: str | None = None,
    discovery_function: DiscoveryFunction = discover_brand,
    generation_function: GenerationFunction = generate_question_bank,
) -> dict[str, Any]:
    """Run discovery and generation from one brand name.

    An injected merchant_enricher may confirm or add brand facts. It must return
    the same BrandProfile contract and must not alter public evidence records.
    """
    root = Path(skill_root)
    discovery_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "brand_name": brand_name,
        "discovery_schema": load_discovery_schema(root),
    }
    if model:
        discovery_kwargs["model"] = model
    discovery = discovery_function(**discovery_kwargs)

    external_evidence = customer_service_evidence or []
    for record in external_evidence:
        validate_evidence_record(record)
        if record["provenance"] != "customer_service":
            raise ValueError("customer_service_evidence must use customer_service provenance")

    external_user_evidence = [
        record for record in external_evidence
        if record["status"] == "usable"
        and record["author_role"] == "user"
        and any(value in record["usage"] for value in ("scene_signal", "intent_signal", "question_expression"))
    ]

    if discovery["status"] == "ambiguous" or (
        discovery["status"] != "ready" and not external_user_evidence
    ):
        return {
            "status": discovery["status"],
            "brand_name": brand_name.strip(),
            "coverage_note": discovery["coverage_note"],
            "missing_information": discovery["missing_information"],
            "evidence_count": len(discovery["evidence"]) + len(external_evidence),
            "question_bank": None,
        }

    profile = discovery["brand_profile"]
    if profile is None:
        return {
            "status": "insufficient",
            "brand_name": brand_name.strip(),
            "coverage_note": "已发现用户表达，但无法确认品牌品类或产品范围。",
            "missing_information": ["brand_profile"],
            "evidence_count": len(discovery["evidence"]),
            "question_bank": None,
        }

    if merchant_enricher is not None:
        profile = merchant_enricher(profile)
        validate_brand_profile(profile)

    merged_evidence: dict[str, dict[str, Any]] = {
        record["evidence_id"]: record
        for record in [*discovery["evidence"], *external_evidence]
    }
    generation_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "brand_profile": profile,
        "evidence": list(merged_evidence.values()),
        "question_bank_schema": load_question_bank_schema(root),
    }
    if model:
        generation_kwargs["model"] = model
    question_bank = generation_function(**generation_kwargs)
    return {
        "status": "completed",
        "brand_name": profile["brand"]["name"],
        "coverage_note": discovery["coverage_note"],
        "missing_information": discovery["missing_information"],
        "evidence_count": len(merged_evidence),
        "question_bank": question_bank,
    }
