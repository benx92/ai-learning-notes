"""复用第13篇检索与证据组装，只把生成步骤接到第20篇的链。"""

import argparse
import json
import sys
from pathlib import Path

# 保留仓库目录关系；第13篇模块只在创建Pipeline时加载向量库与嵌入依赖。
RAG_DIRECTORY = Path(__file__).resolve().parents[1] / "13-rag"
sys.path.insert(0, str(RAG_DIRECTORY))
from rag import Pipeline, ask

from chain_demo import build_basic_chain, make_model


def ask_with_chain(pipeline, chain, question):
    def generate_from_chain(question, context):
        # context由第13篇的检索与组装程序提供，不再手工指定member条款。
        answer = chain.invoke({"context": context, "question": question})
        return {"answer": answer}

    # 复用已有ask：检索 -> 选择证据 -> 有证据才调用上面的生成步骤。
    # 返回值保留evidence和状态；这个适配器只接回答文字，不传递模型用量。
    return ask(pipeline, question, generator=generate_from_chain)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--db", type=Path, required=True, help="第13篇已经入库的数据库目录")
    cli.add_argument("--question", required=True, help="用户直接输入的自然语言问题")
    cli.add_argument("--live", action="store_true", help="调用自己的在线模型生成回答")
    options = cli.parse_args()
    if not options.db.is_dir():
        cli.error("数据库目录不存在；请先按第13篇完成入库，并核对路径")
    pipeline = Pipeline(options.db)
    chain = build_basic_chain(make_model(options.live))
    result = ask_with_chain(pipeline, chain, options.question)
    if not options.live:
        print("检索使用已有知识库；生成使用固定响应，不验证回答准确性。")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
