"""完整抽取路径：准备输入、结构化模型、有限重试、草稿检查。默认离线。"""

import argparse
import json
import os

from langchain_core.prompts import ChatPromptTemplate

from fixtures import DEMO_TEXT, GOOD_ARGS, ScriptedModel, tool_reply
from schemas import Ticket, prepare_draft


def make_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", "从用户原话整理售后工单草稿，只抽取诉求，不核定退款事实。"
         "订单号未提供时使用JSON null，不生成订单号。{validation_hint}"),
        ("human", "用户原话：{text}"),
    ])


def build_chain(model):
    extractor = model.with_structured_output(
        Ticket, method="function_calling", include_raw=True,
    )
    return make_prompt() | extractor


def extract_with_retry(model, text, max_attempts=2):
    if max_attempts < 1:
        raise ValueError("max_attempts必须至少为1")
    chain = build_chain(model)
    hint = ""
    for attempt in range(1, max_attempts + 1):
        result = chain.invoke({"text": text, "validation_hint": hint})
        result = {**result, "attempts": attempt}
        if result["parsing_error"] is None and isinstance(result["parsed"], Ticket):
            return result
        hint = "上次未得到有效工单。检查必填字段、分类取值、摘要长度和订单号格式，再提交Ticket数据。"
    return result


def make_live_model():
    from langchain_deepseek import ChatDeepSeek

    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请设置自己的DEEPSEEK_API_KEY和LC_CHAT_MODEL")
    return ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"],
        temperature=0,
        timeout=45,
        max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    options = parser.parse_args()
    model = make_live_model() if options.live else ScriptedModel(responses=[tool_reply(GOOD_ARGS)])
    if not options.live:
        print("固定响应只验证接口和校验，不代表模型理解了用户原话。")
    result = extract_with_retry(model, DEMO_TEXT)
    print("模型尝试次数：", result["attempts"])
    print("原始消息类型：", type(result["raw"]).__name__)
    print("工具参数：", result["raw"].tool_calls)
    print("解析结果类型：", type(result["parsed"]).__name__)
    print("解析错误：", type(result["parsing_error"]).__name__ if result["parsing_error"] else None)
    print(json.dumps(prepare_draft(result, DEMO_TEXT), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
