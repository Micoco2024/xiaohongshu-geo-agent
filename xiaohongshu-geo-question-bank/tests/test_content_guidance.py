import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from content_guidance import ContentGuidanceError, validate_content_guidance  # noqa: E402


EVIDENCE_ID = "EV-ABCDEF123456"


def usable_user_evidence():
    return [{
        "evidence_id": EVIDENCE_ID,
        "status": "usable",
        "author_role": "user",
        "usage": ["scene_signal", "question_expression"],
    }]


def valid_guidance():
    return {
        "schema_version": "1.0",
        "target_brand": "珀莱雅",
        "coverage_note": "基于公开小红书用户表达。",
        "briefs": [{
            "content_brief_id": "XHS-CB-001",
            "scene_id": "XHS-SCN-001",
            "scene": "油皮用户日间叠加精华和防晒",
            "intent_id": "XHS-INT-001",
            "intent": "降低护肤叠加造成的搓泥风险",
            "user_questions": ["油皮白天用会不会搓泥？"],
            "question_refs": ["GEO-Q-0001"],
            "content_job": "帮助用户判断日间叠加步骤与适用条件",
            "content_angle": "按肤质、用量和叠加顺序拆解搓泥原因",
            "content_type": "risk_clarification",
            "must_answer": ["哪些条件容易导致搓泥"],
            "user_language": ["白天用", "搓泥"],
            "proof_requirements": ["展示不同用量和叠加顺序"],
            "brand_entry": "conditional_fit",
            "brand_entry_conditions": ["明确适用肤质与叠加方式"],
            "claim_boundaries": ["不宣称所有油皮都不会搓泥"],
            "evidence_refs": [EVIDENCE_ID],
        }],
    }


class ContentGuidanceTests(unittest.TestCase):
    def test_valid_guidance(self):
        validate_content_guidance(valid_guidance(), usable_user_evidence(), {"GEO-Q-0001"})

    def test_brand_only_evidence_is_rejected(self):
        evidence = usable_user_evidence()
        evidence[0]["author_role"] = "brand"
        with self.assertRaises(ContentGuidanceError):
            validate_content_guidance(valid_guidance(), evidence, {"GEO-Q-0001"})

    def test_conditional_fit_requires_condition(self):
        guidance = valid_guidance()
        guidance["briefs"][0]["brand_entry_conditions"] = []
        with self.assertRaises(ContentGuidanceError):
            validate_content_guidance(guidance, usable_user_evidence(), {"GEO-Q-0001"})

    def test_unknown_question_reference_is_rejected(self):
        guidance = deepcopy(valid_guidance())
        guidance["briefs"][0]["question_refs"] = ["GEO-Q-9999"]
        with self.assertRaises(ContentGuidanceError):
            validate_content_guidance(guidance, usable_user_evidence(), {"GEO-Q-0001"})


if __name__ == "__main__":
    unittest.main()
