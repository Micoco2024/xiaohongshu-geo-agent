import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
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
            ended = datetime(2026, 9, 27, 12, 0, 0)
            s = record_batch(root, "星巴克", batch=1, queries_done=[], queries_limited=["星巴克 自习"],
                             note_urls=[URL, URL + "?x=1"], pages_loaded=3, rate_limited=True, now=ended)
            self.assertEqual(s["next_batch"], 2)
            self.assertEqual(s["seen_notes"], 1)
            self.assertEqual([q["query"] for q in s["planned_queries"]], ["星巴克 自习", "星巴克 星星 兑换"])
            self.assertEqual(s["planned_queries"][0]["attempt_count"], 1)
            self.assertEqual(s["planned_queries"][0]["last_attempt"]["outcome"], "rate_limited")
            self.assertEqual(s["last_rate_limited_batch"], 1)
            self.assertFalse(s["collection_allowed"])
            self.assertEqual(s["pages_per_batch"], 3)
            self.assertEqual(s["recommended_discovery_mode"], "external_index_first")
            resumed = status(root, "星巴克", now=ended + timedelta(minutes=31))
            self.assertTrue(resumed["collection_allowed"])
            with self.assertRaises(CollectionLogError):
                record_batch(root, "星巴克", batch=1, queries_done=[], note_urls=[], pages_loaded=0, rate_limited=False)
            with self.assertRaises(CollectionLogError):
                record_batch(root, "星巴克", batch=2, queries_done=[], queries_limited=["星巴克 自习"],
                             note_urls=[], pages_loaded=1, rate_limited=False)
            with self.assertRaises(CollectionLogError):
                record_batch(root, "星巴克", batch=2, queries_done=["星巴克 自习"], queries_limited=["星巴克 自习"],
                             note_urls=[], pages_loaded=1, rate_limited=True)
            with self.assertRaises(CollectionLogError):
                record_batch(root, "星巴克", batch=2, queries_done=[], note_urls=[], pages_loaded=-1, rate_limited=False)

    def test_over_budget_batch_is_kept_with_small_penalty(self):
        with tempfile.TemporaryDirectory() as root:
            ended = datetime(2026, 9, 27, 12, 0, 0)
            s = record_batch(root, "星巴克", batch=1, queries_done=["星巴克 自习"], note_urls=[URL],
                             pages_loaded=7, rate_limited=False, now=ended)
            self.assertTrue(s["batches"][-1]["over_budget"])
            self.assertEqual(s["cooldown_minutes"], 30)  # 20 + 2 extra pages x 5
            self.assertEqual(s["pages_per_batch"], 5)  # not a platform limit: budget unchanged
            self.assertTrue(status(root, "星巴克", now=ended + timedelta(minutes=31))["collection_allowed"])

    def test_consecutive_rate_limits_double_the_cooldown_and_history_is_kept(self):
        with tempfile.TemporaryDirectory() as root:
            t = datetime(2026, 9, 27, 12, 0, 0)
            kw = dict(queries_done=[], note_urls=[], pages_loaded=1)
            self.assertEqual(record_batch(root, "星巴克", batch=1, rate_limited=True, now=t, **kw)["cooldown_minutes"], 30)
            t += timedelta(minutes=35)
            self.assertEqual(record_batch(root, "星巴克", batch=2, rate_limited=True, now=t, **kw)["cooldown_minutes"], 60)
            t += timedelta(minutes=65)
            self.assertEqual(record_batch(root, "星巴克", batch=3, rate_limited=True, now=t, **kw)["cooldown_minutes"], 120)
            t += timedelta(minutes=125)
            s = record_batch(root, "星巴克", batch=4, rate_limited=False, now=t, **kw)
            self.assertEqual(s["cooldown_minutes"], 20)
            self.assertEqual(s["consecutive_rate_limits"], 0)
            self.assertEqual([h["waited_minutes"] for h in s["recovery_history"]], [35, 65, 125])
            self.assertEqual([h["recovered"] for h in s["recovery_history"]], [False, False, True])
            for i in range(5, 9):
                t += timedelta(minutes=300)
                s = record_batch(root, "星巴克", batch=i, rate_limited=True, now=t, **kw)
            self.assertEqual(s["cooldown_minutes"], 240)  # capped

    def test_successful_batch_has_short_cooldown_and_marks_query_done(self):
        with tempfile.TemporaryDirectory() as root:
            plan_queries(root, "星巴克", [{"query": "星巴克 自习", "purpose": "seed"}])
            ended = datetime(2026, 9, 27, 12, 0, 0)
            record_batch(root, "星巴克", batch=1, queries_done=["星巴克 自习"], note_urls=[URL],
                         pages_loaded=2, rate_limited=False, now=ended)
            cooling = status(root, "星巴克", now=ended + timedelta(minutes=10))
            self.assertFalse(cooling["collection_allowed"])
            self.assertEqual(cooling["wait_seconds"], 600)
            ready = status(root, "星巴克", now=ended + timedelta(minutes=21))
            self.assertTrue(ready["collection_allowed"])
            self.assertEqual(ready["pages_per_batch"], 5)
            self.assertEqual(ready["done_queries"], 1)

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

            before = (data / "evidence").joinpath(f"{first['snapshot_id']}.json").read_text(encoding="utf-8")
            log_before = (data / "collection" / "珀莱雅.json").read_text(encoding="utf-8")
            for bad in ({"batch": 2}, {"batch": 3, "queries_done": ["a"], "queries_limited": ["a"], "rate_limited": True}):
                with self.assertRaises(CollectionLogError):
                    save_evidence("珀莱雅", raw, data, pages=1, **bad)
            self.assertEqual((data / "evidence").joinpath(f"{first['snapshot_id']}.json").read_text(encoding="utf-8"), before)
            self.assertEqual((data / "collection" / "珀莱雅.json").read_text(encoding="utf-8"), log_before)

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
