"""观察LCEL数据交接；默认固定响应离线运行，可选接入在线模型。"""

import argparse
import os
from collections.abc import Iterator
from operator import itemgetter

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnableBranch,
    RunnableGenerator,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)


POLICIES = {
    "member": "教学政策：会员订单签收后15日内可以申请退货，商品例外需另行核对。来源：demo-policy/member。",
    "general": "教学政策：普通订单签收后7日内可以申请退货，商品例外需另行核对。来源：demo-policy/general。",
}
DEMO_INPUT = {"tier": "member", "question": "会员订单的申请期限是多少？"}
FIXED_REPLY = "教学固定响应：会员订单的申请期限为签收后15日，商品例外仍需核对。"


def make_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", "只解释提供的教学政策，不判断具体订单资格，不查询或提交申请。"),
        ("human", "资料：{context}\n问题：{question}"),
    ])


def build_basic_chain(model):
    prompt = make_prompt()
    parser = StrOutputParser()
    return prompt | model | parser


def normalize(data):
    if not isinstance(data, dict):
        raise TypeError("输入必须是字典")
    tier = data.get("tier")
    question = data.get("question")
    if tier not in POLICIES:
        raise ValueError("tier必须是member或general")
    if not isinstance(question, str):
        raise TypeError("question必须是字符串")
    return {"tier": tier, "question": question.strip()}


def select_policy(data):
    return POLICIES[data["tier"]]


def build_inputs():
    return RunnableParallel(
        context=RunnableLambda(select_policy),
        question=RunnableLambda(itemgetter("question")),
    )


def build_preserved_inputs():
    return RunnablePassthrough.assign(context=RunnableLambda(select_policy))


def build_pipeline(model):
    answer = build_inputs() | build_basic_chain(model)
    route = RunnableBranch(
        (lambda data: not data["question"],
         RunnableLambda(lambda data: "请先填写政策问题。")),
        answer,
    )
    return RunnableLambda(normalize) | route


def uppercase_chunks(chunks: Iterator[str]) -> Iterator[str]:
    for chunk in chunks:
        yield chunk.upper()


def stream_observation():
    # 字符响应只用于确定性观察分片，不代表真实服务的Token边界或延迟。
    model = FakeListChatModel(responses=["a b"])
    chain = build_basic_chain(model)
    inputs = {"context": POLICIES["member"], "question": "观察流式交接"}
    direct = list(chain.stream(inputs))
    buffered = list((chain | RunnableLambda(str.upper)).stream(inputs))
    incremental = list((chain | RunnableGenerator(uppercase_chunks)).stream(inputs))
    return {"direct": direct, "buffered": buffered, "incremental": incremental}


def make_model(live=False):
    if not live:
        return FakeListChatModel(responses=[FIXED_REPLY])
    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请先设置自己的DEEPSEEK_API_KEY和可用的LC_CHAT_MODEL")
    from langchain_deepseek import ChatDeepSeek

    return ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"],
        timeout=45,
        max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--live", action="store_true", help="使用自己的在线模型，产生对应服务费用")
    args = cli.parse_args()
    model = make_model(args.live)
    pipeline = build_pipeline(model)
    if args.live:
        print(pipeline.invoke(DEMO_INPUT, config={"run_name": "policy-explanation"}))
        return

    print("固定响应只用于观察接口与数据流，不理解问题，也不验证政策答案。")
    normalized = normalize(DEMO_INPUT)
    inputs = build_inputs().invoke(normalized)
    prepared = make_prompt().invoke(inputs)
    reply = model.invoke(prepared)
    text = StrOutputParser().invoke(reply)
    print("1. 原始输入：", DEMO_INPUT)
    print("2. 模板变量：", inputs)
    print("3. 模板输出类型：", type(prepared).__name__)
    print("   消息类型：", [type(m).__name__ for m in prepared.to_messages()])
    print("4. 模型输出类型：", type(reply).__name__)
    print("5. 解析结果是否为字符串：", isinstance(text, str), text)
    print("6. 同一输入运行整条链：", pipeline.invoke(DEMO_INPUT))
    print("7. 保留字段后追加context：", build_preserved_inputs().invoke(normalized))
    print("8. 空问题分支：", pipeline.invoke({"tier": "member", "question": "  "}))
    print("9. 流式观察：", stream_observation())


if __name__ == "__main__":
    main()
