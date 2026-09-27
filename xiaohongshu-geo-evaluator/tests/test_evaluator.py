import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evaluator import run_deterministic_evaluation  # noqa: E402


EVIDENCE_ID = "EV-ABCDEF123456"


def valid_bank():
    return {
        "schema_version": "1.0",
        "target_brand": "珀莱雅",
        "coverage_note": "公开样本。",
        "single_turn_questions": [{
            "question_id": "GEO-Q-0001",
            "question": "油皮白天用什么精华不容易搓泥？",
            "question_variants": [],
            "question_type": "brand_recommendation",
            "test_mode": "single_turn",
            "brand_visibility": "unbranded",
            "scene_id": "XHS-SCN-001",
            "scene": "油皮日间护肤",
            "intent_id": "XHS-INT-001",
            "intent": "降低护肤叠加造成的搓泥风险",
            "decision_stage": "solution_exploration",
            "target_brand": "珀莱雅",
            "evidence_refs": [EVIDENCE_ID],
        }],
        "multi_turn_chains": [],
    }


class EvaluatorTests(unittest.TestCase):
    def test_valid_bank_advances_to_semantic_review(self):
        report = run_deterministic_evaluation(valid_bank(), [{"evidence_id": EVIDENCE_ID}])
        self.assertEqual(report["release_decision"], "review_required")
        self.assertTrue(all(item["status"] == "pass" for item in report["deterministic_checks"]))

    def test_unknown_evidence_fails_release(self):
        report = run_deterministic_evaluation(valid_bank(), [])
        self.assertEqual(report["release_decision"], "fail")
        failed = {item["check_id"] for item in report["deterministic_checks"] if item["status"] == "fail"}
        self.assertIn("evidence_refs_resolve", failed)

    def test_brand_leak_fails_unbranded_question(self):
        bank = valid_bank()
        bank["single_turn_questions"][0]["question"] = "珀莱雅适合油皮白天用吗？"
        report = run_deterministic_evaluation(bank, [{"evidence_id": EVIDENCE_ID}])
        failed = {item["check_id"] for item in report["deterministic_checks"] if item["status"] == "fail"}
        self.assertIn("unbranded_no_brand_leak", failed)

    def test_forbidden_field_fails_release(self):
        bank = valid_bank()
        bank["single_turn_questions"][0]["priority_score"] = 88
        report = run_deterministic_evaluation(bank, [{"evidence_id": EVIDENCE_ID}])
        failed = {item["check_id"] for item in report["deterministic_checks"] if item["status"] == "fail"}
        self.assertIn("forbidden_fields_absent", failed)

    def test_duplicate_question_text_fails_release(self):
        bank = valid_bank()
        duplicate = deepcopy(bank["single_turn_questions"][0])
        duplicate["question_id"] = "GEO-Q-0002"
        bank["single_turn_questions"].append(duplicate)
        report = run_deterministic_evaluation(bank, [{"evidence_id": EVIDENCE_ID}])
        failed = {item["check_id"] for item in report["deterministic_checks"] if item["status"] == "fail"}
        self.assertIn("exact_text_unique", failed)


if __name__ == "__main__":
    unittest.main()
