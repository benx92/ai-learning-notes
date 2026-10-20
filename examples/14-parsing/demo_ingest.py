"""第14章：文件转换成知识单元，再复用第13章的入库、检索和问答。"""

import argparse
import json
from pathlib import Path

from knowledge_loader import KnowledgeLoader
from demo_text import QUESTION, run_demo


HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=HERE / "policy.csv")
    parser.add_argument("--db", type=Path, default=HERE / "format_demo")
    parser.add_argument("--question", default=QUESTION)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--extract-only", action="store_true", help="仅核对统一知识单元")
    mode.add_argument("--generate", action="store_true", help="调用真实生成接口")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_demo(args.path, args.db, loader=KnowledgeLoader(),
                      extract_only=args.extract_only, generate_answer=args.generate,
                      question=args.question)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
