import json
import re

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool


DEMO_USER = "demo-user"
DEMO_ORDERS = {
    "A1001": {"owner": "demo-user", "status": "审核中"},
    "A2002": {"owner": "other-user", "status": "已退款"},
}


@tool
def get_refund_status(order_id: str) -> str:
    """查询教学订单的退款状态，不能提交或批准申请。订单号须由用户提供。"""
    if not re.fullmatch(r"A[0-9]{4}", order_id):
        raise ValueError("订单号格式应为A加4位数字")
    order = DEMO_ORDERS.get(order_id)
    if order is None or order["owner"] != DEMO_USER:
        result = {"ok": False, "error": "not_found_or_forbidden"}
    else:
        result = {"ok": True, "order_id": order_id, "status": order["status"]}
    return json.dumps(result, ensure_ascii=False)


def main():
    policy = Document(
        page_content="会员订单签收后15日内可以申请退货。",
        metadata={"source": "refund-policy-demo.md", "section": "会员订单"},
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "解释提供的条款，不推断具体订单的退货资格。"),
        ("human", "资料：{policy}\n问题：{question}"),
    ])
    messages = prompt.invoke({
        "policy": policy.page_content,
        "question": "会员订单的申请期限是多少？",
    }).to_messages()
    for message in messages:
        print(type(message).__name__, message.content)

    print("参数类型：", get_refund_status.args["order_id"]["type"])
    request = AIMessage(content="", tool_calls=[{
        "name": "get_refund_status",
        "args": {"order_id": "A1001"},
        "id": "call_demo_1",
        "type": "tool_call",
    }])
    result = get_refund_status.invoke(request.tool_calls[0])
    print(type(result).__name__, result.tool_call_id, result.content)


if __name__ == "__main__":
    main()
