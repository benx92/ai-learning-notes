"""使用真实嵌入模型检查 PDF 检索；不会调用生成接口。"""

import argparse
import hashlib
import json
import os
import tempfile
from importlib.metadata import version
from pathlib import Path

from loader import DocumentLoader
from rag import Pipeline, pack_context


def verify(output):
    sample = Path(__file__).with_name("refund-policy.pdf")
    units = DocumentLoader().load(sample)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as database:
        pipeline = Pipeline(database)
        ingest = pipeline.ingest(sample)
        questions = ["会员买的普通商品，签收10天后还能退吗？",
                     "普通订单签收10天后还能退吗？",
                     "定制商品签收3天后能无理由退货吗？",
                     "退货运费由谁承担？"]
        cases = []
        for question in questions:
            hits = pipeline.retrieve(question)
            # 发布记录只保留文件名，去除机器上的绝对路径。
            for hit in hits:
                hit["source"] = sample.name
                hit["metadata"]["source"] = sample.name
                hit.pop("chunk_id")
            context, evidence = pack_context(hits)
            cases.append({"question": question, "hits": hits,
                          "context": context, "evidence": evidence})
        assert ingest["units"] == 2
        assert {hit["metadata"]["page"] for hit in cases[0]["hits"]} == {1, 2}
        report = {
            "embedding": "real SentenceTransformer; normalized vectors",
            "generation_called": False,
            "model": os.getenv("RAG_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            "model_max_seq_length": pipeline.embedder.limit,
            "versions": {name: version(name) for name in ["sentence-transformers",
                "transformers", "torch", "chromadb", "langchain-text-splitters", "pymupdf"]},
            "pdf_sha256": hashlib.sha256(sample.read_bytes()).hexdigest(),
            "parsed": [{"text": unit.text, "metadata": {**unit.metadata, "source": sample.name}}
                       for unit in units],
            "ingest": {**ingest, "file": sample.name}, "cases": cases,
            "limitations": "两块小语料，默认 top_k=5 会返回全部块；不是检索质量基准，也没有验证生成答案。",
        }
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "chunks": ingest["chunks"],
        "scores": [[round(hit["score"], 4) for hit in case["hits"]] for case in cases]},
        ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="verification-retrieval.json")
    verify(parser.parse_args().output)
