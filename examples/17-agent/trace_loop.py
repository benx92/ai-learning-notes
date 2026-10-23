"""Observe the chapter-15 execution loop with fixed offline responses; no model API."""

import argparse
import copy
import json
from pathlib import Path
import sys

EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_ROOT / "15-tool-calling"))
from tool_demo import offline_model, run


def observe(question):
    trace = []

    def traced_model(messages, tool_choice):
        reply = offline_model(messages, tool_choice)
        trace.append({
            "model_call": len(trace) + 1,
            "tool_choice": tool_choice,
            "input_messages": copy.deepcopy(messages),
            "output_message": copy.deepcopy(reply),
        })
        return reply

    answer, messages = run(question, traced_model)
    return {
        "mode": "fixed_offline_responses",
        "question": question,
        "model_calls": len(trace),
        "tool_executions": sum(message["role"] == "tool" for message in messages),
        "trace": trace,
        "answer": answer,
        "messages": messages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default="查一下订单A1001的退款状态")
    parser.add_argument("--json", action="store_true", help="print complete input/output snapshots")
    options = parser.parse_args()
    report = observe(options.question)
    if options.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print("模式：固定离线响应，未调用在线模型")
    for step in report["trace"]:
        roles = ", ".join(message["role"] for message in step["input_messages"])
        print(f"模型调用{step['model_call']}的输入角色：{roles}")
        calls = step["output_message"].get("tool_calls") or []
        if calls:
            for call in calls:
                function = call["function"]
                print(f"提出工具请求：{function['name']} {function['arguments']}")
        else:
            print("本轮没有工具请求，返回文字回复")
    print(f"模型调用：{report['model_calls']}；工具执行：{report['tool_executions']}")
    print("回复：", report["answer"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
