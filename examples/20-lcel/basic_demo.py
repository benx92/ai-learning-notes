"""第20篇基础入口：一次政策解释，先逐步运行，再使用同一条链。"""

import argparse

from chain_demo import POLICIES, build_basic_chain, make_model, make_prompt


def run_stepwise(model, context, question):
    # 第一步：把已经取得的政策和用户问题放进模板，得到模型输入。
    inputs = {"context": context, "question": question}
    prompt = make_prompt()
    prepared = prompt.invoke(inputs)
    # 第二步：请求模型；默认离线时，这里只取得预设回复。
    reply = model.invoke(prepared)
    # 第三步：本例回复是纯文本消息，直接读取content字段里的回答。
    return reply.content


def answer_question(chain, context, question):
    # 普通Python先检查页面输入，不需要模型判断用户有没有输入文字。
    if not isinstance(question, str):
        raise TypeError("question必须是字符串")
    question = question.strip()
    if not question:
        # 提前返回，没有运行chain.invoke，所以不会请求模型。
        return "请先填写政策问题。"
    # 输入有效才执行政策解释；chain负责内部三步的数据交接。
    return chain.invoke({"context": context, "question": question})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--live", action="store_true", help="使用自己的在线模型，仅运行一次生成")
    options = cli.parse_args()
    model = make_model(options.live)
    context = POLICIES["member"]
    question = "会员订单的申请期限是多少？"

    if not options.live:
        print("离线固定回复只用于观察步骤，不验证模型理解能力。")
        print("逐步调用：", run_stepwise(model, context, question))

    chain = build_basic_chain(model)
    # 在线模式只执行这一条生成路径，避免演示对照造成重复请求。
    print("整链调用：", answer_question(chain, context, question))
    print("空问题：", answer_question(chain, context, "  "))


if __name__ == "__main__":
    main()
