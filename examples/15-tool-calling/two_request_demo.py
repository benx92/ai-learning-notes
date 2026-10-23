"""两次请求教学示例：先取得工具请求，执行查询，再主动请求模型解释结果。"""

import argparse
import json
import sys

from tool_demo import execute_tool, live_model, offline_model


def _single_call(message):
    calls = message.get("tool_calls") or []
    if not calls:
        return None
    if not isinstance(calls, list) or len(calls) != 1:
        raise RuntimeError("本例只演示一次工具调用；多项请求请使用tool_demo.py")
    call = calls[0]
    if (not isinstance(call, dict) or call.get("type") != "function"
            or not isinstance(call.get("id"), str) or not call["id"]
            or not isinstance(call.get("function"), dict)):
        raise RuntimeError("工具调用结构或ID异常，本次未执行")
    return call


def _answer(message):
    if message.get("tool_calls"):
        raise RuntimeError("第二次响应仍有工具请求，本例停止，不再执行")
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("模型没有给出可读回复，本次停止")
    return text


def run_two_requests(question, model_call, current_user="demo-user"):
    messages = [
        {"role": "system", "content": (
            "查询退款状态时使用工具，缺订单号先询问。"
            "只根据实际工具结果回答，注明虚构教学数据；失败时不编造状态。"
        )},
        {"role": "user", "content": question},
    ]

    # 1. 第一次请求结束，返回值保存在first，Python继续执行下一行。
    first = model_call(messages, "auto")
    call = _single_call(first)
    if call is None:
        answer = _answer(first)
        messages.append({"role": "assistant", "content": answer})
        return {"first_response": first, "tool_result": None,
                "second_response": None, "answer": answer, "messages": messages}

    # 2. 保存原请求。模型返回了函数名，仍要由下面的Python代码实际调用。
    messages.append({"role": "assistant", "content": first.get("content"),
                     "tool_calls": [call]})
    result = execute_tool(call, current_user)

    # 3. 将执行结果加入消息。此处只改变本地列表，尚未发给模型。
    messages.append({"role": "tool", "tool_call_id": call["id"],
                     "content": json.dumps(result, ensure_ascii=False)})

    # 4. 应用主动发起第二次请求，这次输入已经带着工具结果。
    second = model_call(messages, "none")
    answer = _answer(second)
    messages.append({"role": "assistant", "content": answer})
    return {"first_response": first, "tool_result": result,
            "second_response": second, "answer": answer, "messages": messages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default="查一下订单A1001的退款状态")
    parser.add_argument("--live", action="store_true", help="请求真实模型，会产生API费用")
    options = parser.parse_args()
    model_call = live_model if options.live else offline_model
    try:
        report = run_two_requests(options.question, model_call)
    except (RuntimeError, KeyError, ValueError) as error:
        parser.exit(1, f"运行停止：{error}\n")
    print("第一次模型返回：", json.dumps(report["first_response"], ensure_ascii=False, indent=2))
    print("查询函数结果：", json.dumps(report["tool_result"], ensure_ascii=False))
    print("第二次模型返回：", json.dumps(report["second_response"], ensure_ascii=False, indent=2))
    print("最终回复：", report["answer"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
