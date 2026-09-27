import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from question_bank import QuestionBankError, validate_question_bank  # noqa: E402


EVIDENCE_ID = "EV-8CDD86913223"


def example_bank():
    return {
        "schema_version": "1.0",
        "target_brand": "示例品牌",
        "coverage_note": "基于公开小红书证据生成，未使用商家 API。",
        "single_turn_questions": [
            {
                "question_id": "GEO-Q-0001",
                "question": "敏感肌通勤用什么防晒不容易搓泥？",
                "question_variants": ["每天化妆的敏感肌适合什么通勤防晒？"],
                "question_type": "brand_recommendation",
                "test_mode": "single_turn",
                "brand_visibility": "unbranded",
                "scene_id": "XHS-SCN-001",
                "scene": "敏感肌上班族带妆通勤防晒",
                "intent_id": "XHS-INT-001",
                "intent": "降低防晒与底妆不兼容造成的试错风险",
                "decision_stage": "solution_exploration",
                "target_brand": "示例品牌",
                "evidence_refs": [EVIDENCE_ID],
            }
        ],
        "multi_turn_chains": [],
    }


class QuestionBankTests(unittest.TestCase):
    def test_valid_bank(self):
        validate_question_bank(example_bank(), [EVIDENCE_ID])

    def test_unknown_evidence_is_rejected(self):
        with self.assertRaises(QuestionBankError):
            validate_question_bank(example_bank(), [])

    def test_duplicate_question_text_is_rejected(self):
        bank = example_bank()
        duplicate = deepcopy(bank["single_turn_questions"][0])
        duplicate["question_id"] = "GEO-Q-0002"
        bank["single_turn_questions"].append(duplicate)
        with self.assertRaises(QuestionBankError):
            validate_question_bank(bank, [EVIDENCE_ID])

    def test_chain_turns_must_be_contiguous(self):
        bank = example_bank()
        bank["single_turn_questions"] = []
        base = {
            "question_variants": [],
            "question_type": "brand_recommendation",
            "brand_visibility": "unbranded",
            "decision_stage": "solution_exploration",
            "evidence_refs": [EVIDENCE_ID],
        }
        bank["multi_turn_chains"] = [{
            "question_chain_id": "GEO-CHAIN-001",
            "test_mode": "multi_turn",
            "scene_id": "XHS-SCN-001",
            "scene": "通勤防晒",
            "intent_id": "XHS-INT-001",
            "intent": "降低试错风险",
            "target_brand": "示例品牌",
            "turns": [
                {**base, "question_id": "GEO-Q-0101", "turn": 1, "question": "通勤用什么防晒？"},
                {**base, "question_id": "GEO-Q-0102", "turn": 3, "question": "哪些不容易搓泥？"},
            ],
        }]
        with self.assertRaises(QuestionBankError):
            validate_question_bank(bank, [EVIDENCE_ID])


if __name__ == "__main__":
    unittest.main()
