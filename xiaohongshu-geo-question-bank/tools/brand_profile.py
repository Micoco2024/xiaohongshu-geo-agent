"""Shared BrandProfile contract for all Xiaohongshu GEO input modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class BrandProfileError(ValueError):
    """Raised when a normalized brand profile violates the shared contract."""


class BrandFactsProvider(Protocol):
    """Input adapters implement this interface and return one normalized profile."""

    def get_brand_profile(self) -> dict[str, Any]:
        """Return a validated BrandProfile dictionary."""


class JsonBrandFactsProvider:
    """Load an already-normalized BrandProfile from a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def get_brand_profile(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)
        validate_brand_profile(profile)
        return profile


def validate_brand_profile(profile: dict[str, Any]) -> None:
    """Validate invariants needed before downstream evidence analysis.

    This lightweight validator uses only the Python standard library. The JSON
    Schema remains the canonical machine contract and can be enforced by the
    deployed runtime once a JSON Schema validator is installed.
    """

    if not isinstance(profile, dict):
        raise BrandProfileError("BrandProfile must be a JSON object")

    required = {
        "schema_version",
        "input_mode",
        "brand",
        "products",
        "competitors",
        "ambiguous_terms",
        "missing_facts",
    }
    missing = sorted(required.difference(profile))
    if missing:
        raise BrandProfileError(f"Missing top-level fields: {', '.join(missing)}")

    if profile["schema_version"] != "1.0":
        raise BrandProfileError("schema_version must be '1.0'")

    if profile["input_mode"] not in {"merchant_api", "public_evidence"}:
        raise BrandProfileError("input_mode must be merchant_api or public_evidence")

    brand = profile["brand"]
    if not isinstance(brand, dict):
        raise BrandProfileError("brand must be an object")
    _require_non_empty_string(brand.get("name"), "brand.name")
    _require_string_list(brand.get("aliases"), "brand.aliases")
    _require_string_list(brand.get("category_scope"), "brand.category_scope")
    _require_string_list(brand.get("source_refs"), "brand.source_refs")
    _require_nullable_identifier(brand.get("brand_id"), "brand.brand_id")

    products = profile["products"]
    if not isinstance(products, list):
        raise BrandProfileError("products must be an array")
    for index, product in enumerate(products):
        _validate_product(product, index)

    if not brand["category_scope"] and not products:
        raise BrandProfileError(
            "BrandProfile requires at least one category_scope value or one product"
        )

    competitors = profile["competitors"]
    if not isinstance(competitors, list):
        raise BrandProfileError("competitors must be an array")
    for index, competitor in enumerate(competitors):
        if not isinstance(competitor, dict):
            raise BrandProfileError(f"competitors[{index}] must be an object")
        _require_non_empty_string(competitor.get("name"), f"competitors[{index}].name")
        _require_string_list(competitor.get("aliases"), f"competitors[{index}].aliases")
        _require_string_list(
            competitor.get("source_refs"), f"competitors[{index}].source_refs"
        )

    _validate_reason_items(profile["ambiguous_terms"], "ambiguous_terms", "term")
    _validate_reason_items(profile["missing_facts"], "missing_facts", "field")


def _validate_product(product: Any, index: int) -> None:
    prefix = f"products[{index}]"
    if not isinstance(product, dict):
        raise BrandProfileError(f"{prefix} must be an object")
    _require_nullable_identifier(product.get("product_id"), f"{prefix}.product_id")
    _require_non_empty_string(product.get("name"), f"{prefix}.name")
    _require_string_list(product.get("aliases"), f"{prefix}.aliases")
    category = product.get("category")
    if category is not None:
        _require_non_empty_string(category, f"{prefix}.category")
    _require_string_list(product.get("attributes"), f"{prefix}.attributes")
    _require_string_list(product.get("source_refs"), f"{prefix}.source_refs")
    if product.get("fact_status") not in {"confirmed", "candidate"}:
        raise BrandProfileError(
            f"{prefix}.fact_status must be confirmed or candidate"
        )

    faq = product.get("faq")
    if not isinstance(faq, list):
        raise BrandProfileError(f"{prefix}.faq must be an array")
    for faq_index, item in enumerate(faq):
        faq_prefix = f"{prefix}.faq[{faq_index}]"
        if not isinstance(item, dict):
            raise BrandProfileError(f"{faq_prefix} must be an object")
        _require_non_empty_string(item.get("question"), f"{faq_prefix}.question")
        _require_non_empty_string(item.get("answer"), f"{faq_prefix}.answer")
        _require_string_list(item.get("source_refs"), f"{faq_prefix}.source_refs")


def _validate_reason_items(items: Any, field: str, key: str) -> None:
    if not isinstance(items, list):
        raise BrandProfileError(f"{field} must be an array")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise BrandProfileError(f"{field}[{index}] must be an object")
        _require_non_empty_string(item.get(key), f"{field}[{index}].{key}")
        _require_non_empty_string(item.get("reason"), f"{field}[{index}].reason")


def _require_nullable_identifier(value: Any, field: str) -> None:
    if value is not None:
        _require_non_empty_string(value, field)


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise BrandProfileError(f"{field} must be a non-empty string")


def _require_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list):
        raise BrandProfileError(f"{field} must be an array")
    if len(value) != len(set(value)):
        raise BrandProfileError(f"{field} must not contain duplicates")
    for index, item in enumerate(value):
        _require_non_empty_string(item, f"{field}[{index}]")

