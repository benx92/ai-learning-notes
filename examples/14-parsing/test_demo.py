"""第14章检查：改进解析接入真实入库，来源传到最终上下文。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_loader import KnowledgeLoader
from build_sample import build_sample
from demo_text import run_demo
from loader import DocumentUnit
from test_rag import TestEmbedder


class FormatDemoChecks(unittest.TestCase):
    def test_word_heading_reaches_stored_evidence(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            sample = build_sample(Path(directory) / "policy.docx")
            loader = KnowledgeLoader()
            units = loader.load(sample)
            self.assertTrue(all(isinstance(unit, DocumentUnit) for unit in units))
            rule = next(unit for unit in units if "签收后15日" in unit.text)
            self.assertIn("会员订单", rule.text)
            self.assertEqual(rule.metadata["title_path"], "会员订单")
            self.assertIn("Word 块", rule.metadata["location"])
            self.assertNotIn("page", rule.metadata)
            def forbidden(*args):
                raise AssertionError("不应请求生成服务")
            report = run_demo(sample, Path(directory) / "db", loader=loader,
                              embedder=TestEmbedder(), question=rule.text, generator=forbidden)
            self.assertFalse(report["generation_called"])
            evidence = report["evidence"][0]
            self.assertIn("会员订单", evidence["text"])
            self.assertEqual(evidence["source"], str(sample.resolve()))
            self.assertEqual(evidence["location"], rule.metadata["location"])
            self.assertIn(evidence["text"], report["context"])
            with self.assertRaises(FileExistsError):
                build_sample(sample)

    def test_csv_and_extract_only_preserve_source(self):
        sample = Path(__file__).with_name("policy.csv")
        with patch("demo_text.Pipeline", side_effect=AssertionError("不应加载模型")):
            report = run_demo(sample, "unused", loader=KnowledgeLoader(), extract_only=True)
        self.assertTrue(any("15日" in unit["text"] for unit in report["parsed"]))
        self.assertTrue(all(unit["metadata"]["file_type"] == ".csv"
                            for unit in report["parsed"]))


if __name__ == "__main__":
    unittest.main()
