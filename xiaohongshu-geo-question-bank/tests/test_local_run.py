import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from local_run import save_bank, save_evidence  # noqa: E402
from test_brand_discovery import raw_result  # noqa: E402
from test_question_bank import example_bank  # noqa: E402


class LocalRunTests(unittest.TestCase):
    def test_evidence_then_bank_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            raw = data / "raw.json"
            raw.write_text(json.dumps(raw_result(), ensure_ascii=False), encoding="utf-8")
            summary = save_evidence("珀莱雅", raw, data)
            self.assertEqual(summary["model"], "claude-code")
            evidence_id = summary["usable_evidence"][0]["evidence_id"]

            bank = example_bank()
            bank["target_brand"] = "珀莱雅"
            bank["single_turn_questions"][0]["target_brand"] = "珀莱雅"
            bank["single_turn_questions"][0]["evidence_refs"] = [evidence_id]
            bank_path = data / "bank.json"
            bank_path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
            result = save_bank(summary["snapshot_id"], bank_path, data)
            self.assertTrue(Path(result["run_file"]).is_file())
            self.assertNotEqual(result["evaluation"]["release_decision"], "fail")

    def test_bank_citing_unknown_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            raw = data / "raw.json"
            raw.write_text(json.dumps(raw_result(), ensure_ascii=False), encoding="utf-8")
            summary = save_evidence("珀莱雅", raw, data)
            bank_path = data / "bank.json"
            bank_path.write_text(json.dumps(example_bank(), ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                save_bank(summary["snapshot_id"], bank_path, data)


if __name__ == "__main__":
    unittest.main()
