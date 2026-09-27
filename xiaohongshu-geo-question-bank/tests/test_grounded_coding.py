import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from grounded_coding import CodingError, check_bank_against_coding, saturation, validate_coding  # noqa: E402


EV = ["EV-000000000001", "EV-000000000002", "EV-000000000003"]


def coding():
    return {
        "open_codes": [
            {"code_id": "OC-001", "label": "上课前找个能坐下的地方", "in_vivo": False, "evidence_refs": [EV[0]], "batch": 1},
            {"code_id": "OC-002", "label": "想用星星兑换但不知道规则", "in_vivo": False, "evidence_refs": [EV[1]], "batch": 1},
            {"code_id": "OC-003", "label": "“续杯到底能不能续”", "in_vivo": True, "evidence_refs": [EV[2]], "batch": 2},
        ],
        "focused_codes": [
            {"code_id": "FC-001", "label": "把门店当临时落脚点", "open_codes": ["OC-001"], "batch": 1},
            {"code_id": "FC-002", "label": "弄清会员权益怎么用才划算", "open_codes": ["OC-002", "OC-003"], "batch": 1},
        ],
        "categories": [{
            "category_id": "CAT-001", "label": "在固定预算里把会员权益用足",
            "properties": [{"name": "规则清晰度", "dimension": "从完全不懂到熟练", "batch": 1}],
            "paradigm": {"conditions": ["FC-002"], "context": ["FC-001"], "actions": ["FC-002"], "consequences": []},
            "negative_cases": [EV[0]],
        }],
        "core_category": {"label": "低成本获得确定的小体验", "category_ids": ["CAT-001"]},
        "memos": [{"memo_id": "M-001", "batch": 1, "about": ["FC-002"], "text": "兑换规则的困惑集中在…"}],
        "sampling": [],
    }


class GroundedCodingTests(unittest.TestCase):
    def test_valid_record_returns_gap_warnings(self):
        warnings = validate_coding(coding(), EV)
        self.assertTrue(any("consequences" in w for w in warnings))
        self.assertTrue(any("FC-001" in w for w in warnings))

    def test_untraceable_or_broken_links_are_rejected(self):
        bad = coding(); bad["open_codes"][0]["evidence_refs"] = ["EV-FFFFFFFFFFFF"]
        with self.assertRaises(CodingError):
            validate_coding(bad, EV)
        bad = coding(); bad["focused_codes"][0]["open_codes"] = ["OC-999"]
        with self.assertRaises(CodingError):
            validate_coding(bad, EV)
        bad = coding(); bad["categories"][0]["paradigm"]["actions"] = ["FC-999"]
        with self.assertRaises(CodingError):
            validate_coding(bad, EV)
        bad = coding(); bad["open_codes"][1]["code_id"] = "OC-001"
        with self.assertRaises(CodingError):
            validate_coding(bad, EV)

    def test_saturation_needs_two_quiet_batches(self):
        c = coding()  # batches 1 and 2; batch 2 adds only an open code
        self.assertFalse(saturation(c)["saturated"])  # too few batches
        c["open_codes"].append({"code_id": "OC-004", "label": "新出现的另一种困惑", "evidence_refs": [EV[2]], "batch": 3})
        c["focused_codes"].append({"code_id": "FC-003", "label": "新聚焦编码", "open_codes": ["OC-004"], "batch": 3})
        self.assertFalse(saturation(c)["saturated"])  # batch 3 added a focused code
        for batch, cid in ((4, "OC-005"), (5, "OC-006")):
            c["open_codes"].append({"code_id": cid, "label": "同样的困惑再次出现", "evidence_refs": [EV[2]], "batch": batch})
        result = saturation(c)
        self.assertEqual([b["new_focused_codes"] for b in result["batches"]], [2, 0, 1, 0, 0])
        self.assertTrue(result["saturated"])

    def test_bank_scenes_must_be_categories(self):
        bank = {"single_turn_questions": [{"scene_id": "CAT-001"}], "multi_turn_chains": [{"scene_id": "XHS-SCN-001"}]}
        with self.assertRaises(CodingError):
            check_bank_against_coding(bank, coding())
        bank["multi_turn_chains"][0]["scene_id"] = "CAT-001"
        check_bank_against_coding(bank, coding())


if __name__ == "__main__":
    unittest.main()
