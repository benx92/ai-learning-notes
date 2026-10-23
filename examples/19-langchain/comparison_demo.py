"""同一业务函数、同一固定响应：对比手写Python循环与LangChain循环。"""

import json
import re


QUESTION = "查一下A1001的退款状态。"
INSTRUCTION = "查询退款状态必须使用工具，不能猜测。"
ORDERS = {
    "A1001": {"owner": "demo-user", "status": "审核中"},
    "A2002": {"owner": "other-user", "status": "已退款"},
}
TOOL_SPECS = [{
    "name": "get_refund_status",
    "description": "查询当前用户订单的退款状态。",
    "parameters": {
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
    },
}]


def get_refund_status(order_id: str) -> str:
    """查询当前用户订单的退款状态。"""
    if not isinstance(order_id, str) or not re.fullmatch(r"A[0-9]{4}", order_id):
        raise ValueError("订单号格式应为A加4位数字")
    order = ORDERS.get(order_id)
    if order is None or order["owner"] != "demo-user":
        return "订单不存在或无权查看"
    return order["status"]


def scripted_reply(messages, tool_specs):
    """程序写好的两种响应；不是大模型，也不理解用户问题。"""
    if not any(spec["name"] == "get_refund_status" for spec in tool_specs):
        raise ValueError("没有提供查询工具说明")
    results = [m for m in messages if m["role"] == "tool"]
    if results:
        return {"role": "assistant", "content": f"A1001的退款状态：{results[-1]['content']}。"}
    return {"role": "assistant", "content": "", "tool_calls": [{
        "name": "get_refund_status",
        "args": {"order_id": "A1001"},
        "id": "call_comparison_1",
        "type": "tool_call",
    }]}


def run_python(call_model):
    messages = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": QUESTION},
    ]
    tools = {"get_refund_status": get_refund_status}
    for _ in range(3):
        reply = call_model(messages, TOOL_SPECS)
        messages.append(reply)
        requests = reply.get("tool_calls", [])
        if not requests:
            return messages
        for request in requests:
            function = tools[request["name"]]
            result = function(**request["args"])
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": request["id"],
            })
    raise RuntimeError("达到3次模型调用上限")


def run_langchain(model):
    from langchain.agents import create_agent
    from langchain.agents.middleware import ModelCallLimitMiddleware

    agent = create_agent(
        model=model,
        tools=[get_refund_status],
        system_prompt=INSTRUCTION,
        middleware=[ModelCallLimitMiddleware(run_limit=3, exit_behavior="error")],
    )
    result = agent.invoke({
        "messages": [{"role": "user", "content": QUESTION}],
    })
    return result["messages"]


def make_scripted_model(reply_function=scripted_reply):
    """把同一个scripted_reply接到框架模型接口，不在适配器里执行工具。"""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from pydantic import Field

    class ComparisonModel(BaseChatModel):
        specs: list = Field(default_factory=list)

        @property
        def _llm_type(self):
            return "comparison-fixed-responses"

        def bind_tools(self, tools, **kwargs):
            specs = [convert_to_openai_tool(t)["function"] for t in tools]
            return self.model_copy(update={"specs": specs})

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            roles = {"human": "user", "ai": "assistant"}
            plain = [{"role": roles.get(m.type, m.type), "content": m.content}
                     for m in messages]
            reply = reply_function(plain, self.specs)
            message = AIMessage(content=reply["content"], tool_calls=reply.get("tool_calls", []))
            return ChatResult(generations=[ChatGeneration(message=message)])

    return ComparisonModel()


def main():
    print("固定响应只用来比较执行过程，不验证自然语言理解。")
    python_messages = run_python(scripted_reply)
    framework_messages = run_langchain(make_scripted_model())
    print("手写Python版：")
    for m in python_messages:
        if m["role"] != "system":
            print(m["role"], m["content"], json.dumps(m.get("tool_calls", []), ensure_ascii=False))
    print("LangChain版：")
    for m in framework_messages:
        print(m.type, m.content, json.dumps(getattr(m, "tool_calls", []), ensure_ascii=False))


if __name__ == "__main__":
    main()
