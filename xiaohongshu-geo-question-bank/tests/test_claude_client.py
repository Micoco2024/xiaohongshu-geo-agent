import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from claude_client import MODELS, ClaudeCallError, build_request, extract_json, web_tools  # noqa: E402


def message(blocks, stop_reason="end_turn"):
    return NS(stop_reason=stop_reason, content=blocks, stop_details=None)


class ClaudeClientTests(unittest.TestCase):
    def test_reads_json_after_last_tool_result(self):
        blocks = [
            NS(type="text", text="我先搜索一下。"),
            NS(type="server_tool_use"),
            NS(type="web_search_tool_result"),
            NS(type="text", text='{"status": '),
            NS(type="text", text='"ready"}'),
        ]
        self.assertEqual(extract_json(message(blocks)), {"status": "ready"})

    def test_refusal_and_truncation_raise(self):
        with self.assertRaises(ClaudeCallError):
            extract_json(message([], "refusal"))
        with self.assertRaises(ClaudeCallError):
            extract_json(message([NS(type="text", text="{")], "max_tokens"))

    def test_non_json_raises(self):
        with self.assertRaises(ClaudeCallError):
            extract_json(message([NS(type="text", text="不是 JSON")]))

    def test_per_model_request_options(self):
        opus = build_request(system="s", user="u", schema={}, model="claude-opus-5")
        self.assertEqual(opus["thinking"], {"type": "adaptive"})
        self.assertEqual(opus["fallbacks"], "default")
        haiku = build_request(system="s", user="u", schema={}, model="claude-haiku-4-5")
        self.assertNotIn("thinking", haiku)
        self.assertNotIn("fallbacks", haiku)
        self.assertEqual(web_tools("claude-haiku-4-5", ["x.com"], max_searches=1, max_fetches=1)[0]["type"], "web_search_20250305")
        self.assertEqual(web_tools("claude-sonnet-5", ["x.com"], max_searches=1, max_fetches=1)[1]["type"], "web_fetch_20260209")
        self.assertIn("claude-opus-5", MODELS)

    def test_unknown_model_rejected(self):
        with self.assertRaises(ClaudeCallError):
            build_request(system="s", user="u", schema={}, model="gpt-4")


if __name__ == "__main__":
    unittest.main()
