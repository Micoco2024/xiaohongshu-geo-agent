import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from brand_discovery import (  # noqa: E402
    build_discovery_request,
    load_discovery_schema,
    normalize_discovery_result,
)


def raw_result(verification="opened_page"):
    return {
        "status": "ready",
        "requested_brand_name": "珀莱雅",
        "resolved_brand_name": "珀莱雅",
        "aliases": ["PROYA"],
        "category_scope": ["护肤"],
        "products": [{
            "name": "双抗精华",
            "category": "精华",
            "attributes": [],
            "source_refs": ["https://www.xiaohongshu.com/explore/example"],
            "fact_status": "candidate",
        }],
        "competitors": [],
        "evidence": [{
            "source_type": "comment",
            "source_ref": "https://www.xiaohongshu.com/explore/example#comment-1",
            "author_role": "user",
            "text": "油皮白天用会不会搓泥？",
            "context": "精华使用体验讨论",
            "usage": ["scene_signal", "question_expression"],
            "verification": verification,
        }],
        "coverage_note": "仅覆盖可公开访问页面。",
        "missing_information": [],
    }


class BrandDiscoveryTests(unittest.TestCase):
    def test_request_requires_search_and_limits_domain(self):
        request = build_discovery_request("珀莱雅", load_discovery_schema(ROOT))
        self.assertEqual([tool["name"] for tool in request["tools"]], ["web_search", "web_fetch"])
        for tool in request["tools"]:
            self.assertEqual(tool["allowed_domains"], ["xiaohongshu.com"])

    def test_opened_page_becomes_usable(self):
        result = normalize_discovery_result("珀莱雅", raw_result())
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["usable_user_evidence_count"], 1)
        self.assertEqual(result["evidence"][0]["status"], "usable")

    def test_search_snippet_is_candidate_and_downgrades_run(self):
        result = normalize_discovery_result("珀莱雅", raw_result("search_result_only"))
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["evidence"][0]["status"], "candidate")

    def test_non_xiaohongshu_source_is_dropped(self):
        raw = raw_result()
        raw["evidence"][0]["source_ref"] = "https://example.com/article"
        result = normalize_discovery_result("珀莱雅", raw)
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["status"], "insufficient")


if __name__ == "__main__":
    unittest.main()
