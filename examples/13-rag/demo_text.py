"""第13章：从纯文本加载到检索证据；--generate 才调用真实生成服务。"""

import argparse
import json
from pathlib import Path

from loader import DocumentLoader
from rag import Pipeline, ask, generate, pack_context


QUESTION = "会员买的非定制商品，签收10天后还能申请退货吗？"
HERE = Path(__file__).resolve().parent


def run_demo(path, database, *, loader=None, embedder=None, extract_only=False,
             generate_answer=False, question=QUESTION, generator=generate):
    loader = loader or DocumentLoader()
    units = loader.load(path)
    report = {
        "file": str(Path(path).resolve()),
        "parsed": [{"text": unit.text, "metadata": unit.metadata} for unit in units],
        "question": question,
        "generation_called": False,
    }
    if extract_only:
        report["stage"] = "extracted"
        return report

    pipeline = Pipeline(database, embedder=embedder)
    # 第14章可以提供改进加载器，其余入库与问答逻辑继续复用。
    pipeline.loader = loader
    report["ingest"] = pipeline.ingest(path)
    hits = pipeline.retrieve(question)
    context, evidence = pack_context(hits)
    report.update(stage="retrieved", embedding_backend=type(pipeline.embedder).__name__,
                  hits=hits, context=context, evidence=evidence)
    if generate_answer:
        # ask 内含检索与预算检查；证据不足时不会调用生成服务。
        result = ask(pipeline, question, generator=generator)
        report["result"] = result
        report["generation_called"] = result["status"] == "generated_pending_verification"
        report["stage"] = result["status"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=HERE / "refund-policy.md")
    parser.add_argument("--db", type=Path, default=HERE / "text_demo")
    parser.add_argument("--question", default=QUESTION)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--extract-only", action="store_true", help="只读文本，不加载嵌入模型")
    mode.add_argument("--generate", action="store_true", help="使用已配置凭证调用真实生成接口")
    parser.add_argument("--output", type=Path, help="另存完整阶段结果；默认只打印")
    args = parser.parse_args()
    report = run_demo(args.path, args.db, extract_only=args.extract_only,
                      generate_answer=args.generate, question=args.question)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
