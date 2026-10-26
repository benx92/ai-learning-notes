"""新增物流查询：保留退款工具，对照两种执行方式。固定响应不验证模型理解。"""

import re

from comparison_demo import (
    ORDERS, TOOL_SPECS as REFUND_TOOL_SPECS,
    get_refund_status, make_scripted_model,
)

QUESTION = "查一下A1001的物流状态。"
INSTRUCTION = "查询退款或物流状态必须使用对应工具，不能猜测。"
SHIPPING = {"A1001": "运输中，已到达杭州转运中心"}


def get_shipping_status(order_id: str) -> str:
    """查询当前用户订单的物流状态。"""
    # 【两版都要新增】框架不替我们实现物流查询及订单归属检查。
    if not isinstance(order_id, str) or not re.fullmatch(r"A[0-9]{4}", order_id):
        raise ValueError("订单号格式应为A加4位数字")
    order = ORDERS.get(order_id)
    if order is None or order["owner"] != "demo-user":
        return "订单不存在或无权查看"
    return SHIPPING.get(order_id, "暂无物流记录")


# 【手写版新增登记1】告诉回复函数：现在还可以请求物流工具。
TOOL_SPECS = REFUND_TOOL_SPECS + [{
    "name": "get_shipping_status",
    "description": "查询当前用户订单的物流状态。",
    "parameters": {
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
    },
}]


def scripted_reply(messages, tool_specs):
    """用固定关键词选择预设请求，只检验执行程序，不模拟自然语言理解。"""
    question = next(m["content"] for m in messages if m["role"] == "user")
    if "物流" in question:
        name, label = "get_shipping_status", "物流状态"
    elif "退款" in question:
        name, label = "get_refund_status", "退款状态"
    else:
        raise ValueError("离线实验只支持包含物流或退款的A1001问题")
    if not any(spec["name"] == name for spec in tool_specs):
        raise ValueError("没有提供对应查询工具说明")
    results = [m for m in messages if m["role"] == "tool"]
    if results:
        return {"role": "assistant", "content": f"A1001的{label}：{results[-1]['content']}。"}
    return {"role": "assistant", "content": "", "tool_calls": [{
        "name": name,
        "args": {"order_id": "A1001"},
        "id": "call_two_tools_1",
        "type": "tool_call",
    }]}


def run_python(call_model, question=QUESTION):
    # 步骤1：准备消息；与单工具版相比，问题和处理要求覆盖两种查询。
    messages = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": question},
    ]
    # 【手写版新增登记2】让执行程序按工具名找到物流函数。
    tools = {
        "get_refund_status": get_refund_status,
        "get_shipping_status": get_shipping_status,
    }
    for _ in range(3):
        # 步骤2：取得回复；工具增加了，这个执行循环仍然复用。
        reply = call_model(messages, TOOL_SPECS)
        messages.append(reply)
        # 步骤3：检查工具请求，没有请求就结束。
        requests = reply.get("tool_calls", [])
        if not requests:
            return messages
        for request in requests:
            # 步骤4：请求哪个名字，就执行查找表中的哪个函数。
            function = tools[request["name"]]
            result = function(**request["args"])
            # 步骤5：回填结果，并配对调用ID。
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": request["id"],
            })
        # 步骤6：继续请求模型，让它读到刚才的工具结果。
    raise RuntimeError("达到3次模型调用上限")


def run_langchain(model, question=QUESTION):
    from langchain.agents import create_agent
    from langchain.agents.middleware import ModelCallLimitMiddleware

    # 步骤1：登记模型、工具和要求；此时不执行查询。
    agent = create_agent(
        model=model,
        # 【框架版新增登记】追加物流函数，工具说明与函数查找由框架组织。
        tools=[get_refund_status, get_shipping_status],
        system_prompt=INSTRUCTION,
        middleware=[ModelCallLimitMiddleware(run_limit=3, exit_behavior="error")],
    )
    # 步骤2—6：沿用框架循环；无需为物流查询另写分发、回填和再次调用。
    result = agent.invoke({
        "messages": [{"role": "user", "content": question}],
    })
    return result["messages"]


def main():
    print("两种工具都已登记；固定响应只验证执行，不验证模型选工具的能力。")
    for question in (QUESTION, "查一下A1001的退款状态。"):
        print("\n问题：", question)
        plain = run_python(scripted_reply, question)
        framework = run_langchain(make_scripted_model(scripted_reply), question)
        print("手写Python版：")
        for message in plain[1:]:
            print(message["role"], message["content"], message.get("tool_calls", ""))
        print("LangChain版：")
        for message in framework:
            print(message.type, message.content, getattr(message, "tool_calls", ""))


if __name__ == "__main__":
    main()
