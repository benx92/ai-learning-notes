"""第13章演示流程检查；真实存储，测试向量，不请求生成服务。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from demo_text import HERE, run_demo
from test_rag import TestEmbedder


class TextDemoChecks(unittest.TestCase):
    def test_extract_only_needs_no_model_or_database(self):
        with patch("demo_text.Pipeline", side_effect=AssertionError("不应初始化模型")):
            report = run_demo(HERE / "refund-policy.md", "unused", extract_only=True)
        self.assertEqual(report["stage"], "extracted")
        self.assertFalse(report["generation_called"])
        self.assertEqual(len(report["parsed"]), 1)
        self.assertEqual(report["parsed"][0]["metadata"]["location"], "全文")
        self.assertNotIn("page", report["parsed"][0]["metadata"])

    def test_saved_evidence_and_explicit_generation(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            database = Path(directory) / "db"
            sample = HERE / "refund-policy.md"
            def forbidden(*args):
                raise AssertionError("默认不应生成")
            report = run_demo(sample, database, embedder=TestEmbedder(), generator=forbidden)
            self.assertFalse(report["generation_called"])
            self.assertTrue(report["evidence"])
            for item in report["evidence"]:
                self.assertEqual(Path(item["source"]).name, sample.name)
                self.assertIn(item["text"], report["context"])
                self.assertIn(item["label"], report["context"])
            generated = run_demo(sample, database, embedder=TestEmbedder(),
                                 generate_answer=True, generator=lambda q, c: {
                                     "answer": "仅供流程测试[资料1]", "model": "test-only"})
            self.assertTrue(generated["generation_called"])
            self.assertEqual(generated["result"]["evidence"], generated["evidence"])
            self.assertEqual(generated["ingest"]["total"], report["ingest"]["total"])


if __name__ == "__main__":
    unittest.main()
