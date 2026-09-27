import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from collection_log import CollectionLogError, plan_queries, record_batch, status  # noqa: E402
from evidence_store import append_batch, list_snapshots, load_snapshot  # noqa: E402
from local_run import save_coding, save_evidence  # noqa: E402
from test_brand_discovery import raw_result  # noqa: E402


URL = "https://www.xiaohongshu.com/explore/6a439a1f0000000006036191"


class CollectionLogTests(unittest.TestCase):
    def test_plan_record_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            plan_queries(root, "星巴克", [{"query": "星巴克 自习", "purpose": "seed"},
                                          {"query": "星巴克 星星 兑换", "purpose": "theoretical", "reason": "CAT-001 缺结果"}])
            with self.assertRaises(CollectionLogError):
                plan_queries(root, "星巴克", [{"query": "x", "purpose": "theoretical"}])
            s = record_batch(root, "星巴克", batch=1, queries_done=["星巴克 自习"], note_urls=[URL, URL + "?x=1"],
                             pages_loaded=8, rate_limited=True)
            self.assertEqual(s["next_batch"], 2)
            self.assertEqual(s["seen_notes"], 1)
            self.assertEqual([q["query"] for q in s["planned_queries"]], ["星巴克 星星 兑换"])
            self.assertEqual(s["last_rate_limited_batch"], 1)
            with self.assertRaises(CollectionLogError):
                record_batch(root, "星巴克", batch=1, queries_done=[], note_urls=[], pages_loaded=0, rate_limited=False)

    def test_batches_merge_into_one_snapshot_and_coding_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            raw = data / "raw.json"
            raw.write_text(json.dumps(raw_result(), ensure_ascii=False), encoding="utf-8")
            first = save_evidence("珀莱雅", raw, data, batch=1, pages=5, queries_done=["珀莱雅 搓泥"])
            again = save_evidence("珀莱雅", raw, data, batch=2, pages=3)
            self.assertEqual(first["snapshot_id"], again["snapshot_id"])
            self.assertEqual(again["duplicates"], 1)
            snap = load_snapshot(data / "evidence", again["snapshot_id"])
            self.assertEqual([b["batch"] for b in snap["batches"]], [1, 2])
            self.assertEqual(len(list_snapshots(data / "evidence", "珀莱雅")), 1)
            self.assertEqual(status(data / "collection", "珀莱雅")["next_batch"], 3)

            ev = first["usable_evidence"][0]["evidence_id"]
            coding = {"open_codes": [{"code_id": "OC-001", "label": "白天用会不会搓泥", "in_vivo": True,
                                      "evidence_refs": [ev], "batch": 1}],
                      "focused_codes": [], "categories": [], "memos": []}
            path = data / "coding.json"
            path.write_text(json.dumps(coding, ensure_ascii=False), encoding="utf-8")
            result = save_coding("珀莱雅", path, data)
            self.assertEqual(result["uncoded_evidence"], [])
            coding["open_codes"][0]["evidence_refs"] = ["EV-FFFFFFFFFFFF"]
            path.write_text(json.dumps(coding, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                save_coding("珀莱雅", path, data)


if __name__ == "__main__":
    unittest.main()
