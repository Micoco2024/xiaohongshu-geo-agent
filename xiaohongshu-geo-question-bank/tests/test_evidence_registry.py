import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evidence_registry import (  # noqa: E402
    EvidenceError,
    EvidenceRegistry,
    build_evidence_record,
    make_evidence_id,
)


class EvidenceRegistryTests(unittest.TestCase):
    def make_record(self, **overrides):
        values = {
            "provenance": "public_page",
            "source_type": "comment",
            "source_ref": "https://www.xiaohongshu.com/example#comment-1",
            "author_role": "user",
            "text": "油皮通勤用什么防晒不搓泥？",
            "usage": ["scene_signal", "question_expression"],
        }
        values.update(overrides)
        return build_evidence_record(**values)

    def test_id_is_deterministic(self):
        first = make_evidence_id("source", "excerpt")
        second = make_evidence_id(" source ", " excerpt ")
        self.assertEqual(first, second)

    def test_duplicate_record_is_idempotent(self):
        registry = EvidenceRegistry()
        record = self.make_record()
        registry.add(record)
        registry.add(record)
        self.assertEqual(len(registry.records()), 1)

    def test_excluded_record_requires_reason(self):
        with self.assertRaises(EvidenceError):
            self.make_record(status="excluded")

    def test_invalid_usage_is_rejected(self):
        with self.assertRaises(EvidenceError):
            self.make_record(usage=["ranking_signal"])

    def test_jsonl_export(self):
        registry = EvidenceRegistry()
        record = self.make_record()
        registry.add(record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.jsonl"
            registry.write_jsonl(path)
            exported = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(exported["evidence_id"], record["evidence_id"])


if __name__ == "__main__":
    unittest.main()
