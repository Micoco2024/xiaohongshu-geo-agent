import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from agent_runner import run_brand_agent  # noqa: E402


class AgentRunnerTests(unittest.TestCase):
    def test_insufficient_discovery_stops_before_generation(self):
        called = False

        def discover(**kwargs):
            return {
                "status": "insufficient",
                "brand_profile": None,
                "evidence": [],
                "coverage_note": "没有可用公开用户表达。",
                "missing_information": ["user_expression"],
            }

        def generate(**kwargs):
            nonlocal called
            called = True

        result = run_brand_agent(
            brand_name="珀莱雅",
            api_key="test-key",
            skill_root=ROOT,
            discovery_function=discover,
            generation_function=generate,
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertIsNone(result["question_bank"])
        self.assertFalse(called)

    def test_ready_discovery_reaches_generation(self):
        profile = {
            "schema_version": "1.0",
            "input_mode": "public_evidence",
            "brand": {"brand_id": None, "name": "珀莱雅", "aliases": [], "category_scope": ["护肤"], "source_refs": []},
            "products": [],
            "competitors": [],
            "ambiguous_terms": [],
            "missing_facts": [],
        }
        evidence = [{"evidence_id": "EV-000000000001"}]

        def discover(**kwargs):
            return {
                "status": "ready",
                "brand_profile": profile,
                "evidence": evidence,
                "coverage_note": "公开页面样本。",
                "missing_information": [],
            }

        def generate(**kwargs):
            self.assertEqual(kwargs["brand_profile"], profile)
            self.assertEqual(kwargs["evidence"], evidence)
            return {"schema_version": "1.0", "target_brand": "珀莱雅"}

        result = run_brand_agent(
            brand_name="珀莱雅",
            api_key="test-key",
            skill_root=ROOT,
            discovery_function=discover,
            generation_function=generate,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["brand_name"], "珀莱雅")
        self.assertIsNotNone(result["question_bank"])


if __name__ == "__main__":
    unittest.main()
