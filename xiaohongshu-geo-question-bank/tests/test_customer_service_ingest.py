import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from customer_service_ingest import parse_customer_service_document  # noqa: E402


class CustomerServiceIngestTests(unittest.TestCase):
    def test_csv_preserves_conversation_sequence(self):
        content = "conversation_id,turn,speaker,text\nc-1,1,customer,敏感肌能用吗\nc-1,2,agent,建议先局部测试"
        records = parse_customer_service_document("service.csv", content)
        self.assertEqual(records[0]["provenance"], "customer_service")
        self.assertEqual(records[0]["author_role"], "user")
        self.assertEqual(records[1]["author_role"], "customer_service_agent")
        self.assertEqual(records[1]["parent_evidence_id"], records[0]["evidence_id"])

    def test_txt_treats_each_line_as_customer_question(self):
        records = parse_customer_service_document("questions.txt", "怎么使用？\n可以退货吗？")
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["author_role"] == "user" for record in records))

    def test_common_identifiers_are_redacted(self):
        records = parse_customer_service_document("questions.txt", "手机号13800138000，邮箱a@example.com")
        self.assertNotIn("13800138000", records[0]["text"])
        self.assertNotIn("a@example.com", records[0]["text"])


if __name__ == "__main__":
    unittest.main()
