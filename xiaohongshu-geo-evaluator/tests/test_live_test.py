import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from live_test import (  # noqa: E402
    LiveTestError,
    analyze_sources,
    note_id,
    parse_count,
    brand_terms,
    build_observation,
    build_test_plan,
    live_status,
    load_session,
    record_runs,
    start_session,
    merge_observations,
    report_observation,
    summarize,
)


BANK = {
    "single_turn_questions": [
        {"question_id": "GEO-Q-0001", "question": "大理有什么好喝的咖啡店？", "brand_visibility": "unbranded", "scene": "s", "intent": "i"},
    ],
    "multi_turn_chains": [
        {"question_chain_id": "GEO-CHAIN-001", "scene": "s", "intent": "i", "turns": [
            {"turn": 2, "question": "第二问"}, {"turn": 1, "question": "第一问"}]},
    ],
}
TERMS = brand_terms("Wonder Wander", ["玩豆咖啡"])


def record(response, **extra):
    return {"product": "点点", "question_ref": "GEO-Q-0001", "repeat_index": 1,
            "turns": [{"question": "大理有什么好喝的咖啡店？", "response": response}], **extra}


class LiveTestTests(unittest.TestCase):
    def test_plan_covers_products_repeats_and_orders_turns(self):
        plan = build_test_plan(BANK, ["点点", "豆包"], repeats=2)
        self.assertEqual(len(plan), 2 * 2 * 2)
        chain = next(p for p in plan if p["mode"] == "multi_turn")
        self.assertEqual(chain["turns"], ["第一问", "第二问"])
        with self.assertRaises(LiveTestError):
            build_test_plan(BANK, [" "])

    def test_brand_detection_ignores_case_and_spacing(self):
        obs = build_observation(record("推荐 wonderwander 和另一家"), TERMS)
        self.assertEqual(obs["brand_position"], "mentioned")
        self.assertEqual(obs["factual_accuracy"], "review")
        self.assertEqual(build_observation(record("可以去玩豆咖啡坐坐"), TERMS)["brand_position"], "mentioned")
        absent = build_observation(record("推荐秋山咖啡"), TERMS)
        self.assertEqual(absent["brand_position"], "absent")
        self.assertEqual(absent["factual_accuracy"], "not_assessed")

    def test_reviewer_cannot_mark_unnamed_brand_as_recommended(self):
        with self.assertRaises(LiveTestError):
            build_observation(record("推荐秋山咖啡", brand_position="recommended"), TERMS)
        upgraded = build_observation(record("首推 Wonder Wander", brand_position="recommended"), TERMS)
        self.assertEqual(upgraded["brand_position"], "recommended")

    def test_blocked_run_is_not_applicable(self):
        obs = build_observation(record("", run_status="blocked"), TERMS)
        self.assertEqual(obs["brand_position"], "not_applicable")

    def test_merge_status_summary_and_report_shape(self):
        first = build_observation(record("没有提到"), TERMS)
        second = build_observation(record("Wonder Wander 不错"), TERMS)
        merged = merge_observations([first], [second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["brand_position"], "mentioned")
        self.assertEqual(live_status(2, merged), "partial")
        self.assertEqual(live_status(1, merged), "complete")
        self.assertEqual(live_status(1, []), "not_run")
        self.assertEqual(summarize(merged)[0]["mentioned"], 1)
        self.assertNotIn("turns", report_observation(merged[0]))

    def test_session_storage_mirrors_into_run_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_id = "wonder_wander/20260926-165854"
            run_path = Path(tmp) / "runs" / f"{run_id}.json"
            run_path.parent.mkdir(parents=True)
            bank = {**BANK, "target_brand": "Wonder Wander"}
            evaluation = {"release_decision": "review_required", "live_test_status": "not_run", "live_observations": []}
            run_path.write_text(json.dumps({"result": {"question_bank": bank}, "evaluation": evaluation}), encoding="utf-8")
            with self.assertRaises(LiveTestError):
                record_runs(tmp, run_id, [record("x")])
            session = start_session(tmp, run_id, ["点点"], aliases=["玩豆咖啡"])
            self.assertEqual(len(session["plan"]), 2)
            record_runs(tmp, run_id, [record("去玩豆咖啡")])
            self.assertEqual(load_session(tmp, run_id)["summary"][0]["mentioned"], 1)
            saved = json.loads(run_path.read_text(encoding="utf-8"))["evaluation"]
            self.assertEqual(saved["live_test_status"], "partial")
            self.assertEqual(saved["release_decision"], "review_required")
            self.assertEqual(len(start_session(tmp, run_id, ["点点", "豆包"])["observations"]), 1)
            with self.assertRaises(LiveTestError):
                load_session(tmp, "../../etc/20260101-000000")

    def test_count_and_note_id_parsing(self):
        self.assertEqual(parse_count("1.2万"), 12000)
        self.assertEqual(parse_count("3k"), 3000)
        self.assertEqual(parse_count("赞"), None)
        self.assertEqual(note_id("https://www.xiaohongshu.com/explore/6a439a1f0000000006036191?x=1"), "6a439a1f0000000006036191")

    def test_source_analysis_splits_by_brand_presence(self):
        ours = "https://www.xiaohongshu.com/explore/6a439a1f0000000006036191"
        shared = {"title": "大理咖啡合集", "url": "https://www.xiaohongshu.com/explore/aaaaaaaaaaaaaaaaaaaaaaaa", "likes": "2万", "note_type": "图文"}
        named = build_observation(record("推荐 Wonder Wander", sources=[
            {"title": "No.90 Wonder Wander Coffee", "url": ours, "likes": 4, "author_type": "user", "note_type": "图文"}, shared]), TERMS)
        absent = build_observation({**record("推荐秋山"), "question_ref": "GEO-Q-0002", "sources": [shared]}, TERMS)
        self.assertTrue(named["sources"][0]["mentions_brand"])
        result = analyze_sources([named, absent], [ours])
        self.assertEqual(result["brand_named"]["share_in_our_evidence"], 0.5)
        self.assertEqual(result["brand_named"]["share_mentions_brand"], 0.5)
        self.assertEqual(result["brand_absent"]["likes_median"], 20000)
        self.assertEqual(result["cited_by_multiple_questions"][0]["questions"], ["GEO-Q-0001", "GEO-Q-0002"])


if __name__ == "__main__":
    unittest.main()
