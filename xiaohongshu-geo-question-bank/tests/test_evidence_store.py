import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evidence_store import (  # noqa: E402
    EvidenceStoreError,
    append_batch,
    brand_key,
    list_snapshots,
    load_snapshot,
    save_snapshot,
)


DISCOVERY = {
    "status": "ready",
    "brand_profile": None,
    "evidence": [{"evidence_id": "e1", "status": "usable"}, {"evidence_id": "e2", "status": "candidate"}],
    "coverage_note": "",
    "missing_information": [],
    "usable_user_evidence_count": 1,
}


class EvidenceStoreTests(unittest.TestCase):
    def test_save_then_load_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            summary = save_snapshot(root, " 珀莱雅 ", DISCOVERY, model="m", now=datetime(2026, 9, 26, 11, 0, 5))
            self.assertEqual(summary["snapshot_id"], "珀莱雅/20260926-110005")
            self.assertEqual(summary["evidence_count"], 2)
            self.assertEqual(summary["usable_count"], 1)
            loaded = load_snapshot(root, summary["snapshot_id"])
            self.assertEqual(loaded["discovery"], DISCOVERY)
            self.assertEqual(loaded["brand_name"], "珀莱雅")

    def test_list_is_newest_first_and_filters_by_brand(self):
        with tempfile.TemporaryDirectory() as root:
            save_snapshot(root, "A", DISCOVERY, now=datetime(2026, 1, 1))
            save_snapshot(root, "a", DISCOVERY, now=datetime(2026, 1, 2))
            save_snapshot(root, "B", DISCOVERY, now=datetime(2026, 1, 3))
            self.assertEqual([s["created_at"][:10] for s in list_snapshots(root)], ["2026-01-03", "2026-01-02", "2026-01-01"])
            self.assertEqual(len(list_snapshots(root, "A")), 2)
            self.assertEqual(list_snapshots(Path(root) / "missing"), [])

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            for bad in ("../x/20260101-000000", "a/../../b", "a/b", ""):
                with self.assertRaises(EvidenceStoreError):
                    load_snapshot(root, bad)

    def test_brand_key_sanitizes(self):
        self.assertEqual(brand_key("Olay / 玉兰油"), "olay_玉兰油")
        with self.assertRaises(EvidenceStoreError):
            brand_key("  ")

    def test_later_batch_resolves_ambiguous_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            ambiguous = {
                "status": "ambiguous",
                "brand_profile": None,
                "evidence": [],
                "coverage_note": "未消歧",
                "missing_information": ["品牌主体"],
                "usable_user_evidence_count": 0,
            }
            save_snapshot(root, "Wonder Wander", ambiguous, now=datetime(2026, 9, 27, 22, 10, 9))
            resolved = {
                **DISCOVERY,
                "evidence": [{
                    "evidence_id": "e3",
                    "status": "usable",
                    "author_role": "creator",
                    "usage": ["scene_signal"],
                }],
            }
            summary = append_batch(root, "Wonder Wander", resolved, batch=2)
            self.assertEqual(summary["status"], "ready")
            self.assertEqual(summary["usable_user_evidence_count"], 1)


if __name__ == "__main__":
    unittest.main()
