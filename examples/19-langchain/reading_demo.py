"""沿正文观察消息准备与手动查询；不请求聊天模型。"""

import json

from langchain_core.prompts import ChatPromptTemplate

from components_demo import get_refund_status


def prepare_messages(policy, question):
    instruction = "解释提供的条款，不推断具体订单的退货资格。"
    plain = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": f"资料：{policy}\n问题：{question}"},
    ]
    prompt = ChatPromptTemplate.from_messages([
        ("system", instruction),
        ("human", "资料：{policy}\n问题：{question}"),
    ])
    prepared = prompt.invoke({"policy": policy, "question": question})
    return plain, prepared.to_messages()


def main():
    plain, messages = prepare_messages(
        "会员订单签收后15日内可以申请退货。",
        "会员订单的申请期限是多少？",
    )
    print("1. 普通Python准备的输入：")
    print(plain[1]["content"])
    print("2. 模板准备的消息（此时尚未请求模型）：")
    for message in messages:
        print(type(message).__name__, message.content)
    print("3. 用户新增订单查询需求，先手动调用工具：")
    result = get_refund_status.invoke({"order_id": "A1001"})
    print(json.dumps(json.loads(result), ensure_ascii=False))
    print("下一步：配置自己的模型后，agent_demo.py演示模型选择工具。")


if __name__ == "__main__":
    main()
