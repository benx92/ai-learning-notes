"""存储与控制流回归检查：真实 Chroma/切分器，替身编码器和生成器。"""

import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rag


class TestEmbedder:
    """只为稳定测试存储行为，不具有语义检索能力。"""

    def token_count(self, text):
        return len(text)

    def encode(self, texts):
        return [[(b + 1) / 256 for b in hashlib.sha256(t.encode()).digest()[:8]]
                for t in texts]


class RagChecks(unittest.TestCase):
    def test_document_lifecycle_and_persistence(self):
        # Windows 下 Chroma 进程仍持有数据库句柄时，临时目录清理可能受阻。
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            first, second = root / "first.md", root / "second.txt"
            first.write_text("旧版本规则。" * 30, encoding="utf-8")
            second.write_text("第二份文档保留。", encoding="utf-8")
            pipeline = rag.Pipeline(root / "db", TestEmbedder())
            pipeline.ingest(first)
            pipeline.ingest(second)
            initial_count = pipeline.collection.count()
            pipeline.ingest(first)
            self.assertEqual(pipeline.collection.count(), initial_count)
            first.write_text("新版本：提前三天申请。", encoding="utf-8")
            pipeline.ingest(first)
            records = pipeline.collection.get(include=["documents"])
            self.assertEqual(set(records["documents"]),
                             {"新版本：提前三天申请。", "第二份文档保留。"})
            first.write_text(" ", encoding="utf-8")
            with self.assertRaises(ValueError):
                pipeline.ingest(first)
            self.assertEqual(pipeline.collection.count(), 2)
            reopened = rag.Pipeline(root / "db", TestEmbedder())
            hits = reopened.retrieve("新版本：提前三天申请。", top_k=50)
            self.assertEqual(len(hits), 2)
            self.assertEqual(hits[0]["text"], "新版本：提前三天申请。")
            self.assertAlmostEqual(hits[0]["score"], 1.0, places=5)
            with self.assertRaises(ValueError):
                reopened.retrieve(" ")
            with self.assertRaises(ValueError):
                reopened.retrieve("问题", top_k=0)
            with self.assertRaises(ValueError):
                reopened.retrieve("问题", threshold=2)

    def test_context_and_generation_gate(self):
        hit = {"source": "a.md", "chunk_index": 0, "text": "正文",
               "chunk_id": "a", "score": 0.9}
        too_long = {**hit, "text": "长文" * 100, "chunk_id": "long"}
        context, evidence = rag.pack_context([too_long, hit], 100)
        self.assertLessEqual(len(context), 100)
        self.assertEqual([e["chunk_id"] for e in evidence], ["a"])
        self.assertEqual(evidence[0]["label"], "资料1")
        self.assertIn("[资料1]", context)

        class Retriever:
            def retrieve(self, *args):
                return [hit]

        def forbidden(*args):
            raise AssertionError("不应调用生成服务")

        result = rag.ask(Retriever(), "问题", budget=1, generator=forbidden)
        self.assertIsNone(result["model"])
        self.assertEqual(result["evidence"], [])
        result = rag.ask(Retriever(), "问题", generator=lambda q, c: {
            "answer": "示例回答[资料1]", "model": "test-only"})
        self.assertEqual(result["status"], "generated_pending_verification")
        self.assertEqual(result["evidence"][0]["chunk_id"], "a")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            empty = rag.Pipeline(directory, TestEmbedder())
            result = rag.ask(empty, "问题", generator=forbidden)
            self.assertEqual(result["status"], "insufficient_evidence")

    def test_http_payload_and_incomplete_answer(self):
        raw = {"choices": [{"finish_reason": "stop", "message": {"content": "答案"}}],
               "model": "test-model", "usage": {"prompt_tokens": 10}}
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only", "RAG_CHAT_MODEL": "test-model"}):
            with patch("rag.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())) as send:
                result = rag.generate("问题", "参考资料")
                request = send.call_args.args[0]
                payload = json.loads(request.data)
                self.assertEqual(payload["messages"][0]["role"], "system")
                self.assertEqual(json.loads(payload["messages"][1]["content"])["question"], "问题")
                self.assertEqual(result["usage"]["prompt_tokens"], 10)
            raw["choices"][0]["finish_reason"] = "length"
            with patch("rag.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())):
                with self.assertRaises(RuntimeError):
                    rag.generate("问题", "参考资料")


if __name__ == "__main__":
    unittest.main()
