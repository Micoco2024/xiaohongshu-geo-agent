import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from generation_agent import (  # noqa: E402
    AgentRuntimeError,
    build_generation_request,
    load_question_bank_schema,
    prepare_strict_output_schema,
)


def load_json(name):
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


class GenerationAgentTests(unittest.TestCase):
    def test_request_uses_structured_outputs_and_excludes_candidate_evidence(self):
        profile = load_json("brand-profile.example.json")
        record = load_json("evidence-record.example.json")
        candidate = {**record, "evidence_id": "EV-5C35D0CB7A5B", "source_ref": "candidate"}
        # Fix the candidate ID using the production function.
        from evidence_registry import make_evidence_id
        candidate["evidence_id"] = make_evidence_id(candidate["source_ref"], candidate["text"])
        candidate["status"] = "candidate"
        request = build_generation_request(profile, [record, candidate], load_question_bank_schema(ROOT))
        self.assertEqual(request["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(request["model"], "claude-opus-5")
        user_input = json.loads(request["messages"][0]["content"])
        self.assertEqual(len(user_input["evidence"]), 1)
        self.assertEqual(user_input["evidence"][0]["status"], "usable")

    def test_strict_schema_contains_no_unsupported_composition(self):
        schema = prepare_strict_output_schema(load_question_bank_schema(ROOT))
        serialized = json.dumps(schema)
        for keyword in ('"allOf"', '"if"', '"then"', '"else"', '"minLength"', '"minimum"', '"pattern"', '"uniqueItems"'):
            self.assertNotIn(keyword, serialized)
        self.assertNotIn("anyOf", schema)

    def test_missing_evidence_is_rejected(self):
        profile = load_json("brand-profile.example.json")
        with self.assertRaises(AgentRuntimeError):
            build_generation_request(profile, [], load_question_bank_schema(ROOT))


if __name__ == "__main__":
    unittest.main()
