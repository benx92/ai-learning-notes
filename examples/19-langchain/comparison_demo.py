"""同一业务函数、同一固定响应：对比手写Python循环与LangChain循环。"""

import json
import re


QUESTION = "查一下A1001的退款状态。"
INSTRUCTION = "查询退款状态必须使用工具，不能猜测。"
ORDERS = {
    "A1001": {"owner": "demo-user", "status": "审核中"},
    "A2002": {"owner": "other-user", "status": "已退款"},
}
# 手写版需要自己维护这份工具说明；LangChain版从函数签名和docstring生成。
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
    # 【两版共用的业务代码】格式检查、归属检查和查询规则仍由开发者实现。
    if not isinstance(order_id, str) or not re.fullmatch(r"A[0-9]{4}", order_id):
        raise ValueError("订单号格式应为A加4位数字")
    order = ORDERS.get(order_id)
    if order is None or order["owner"] != "demo-user":
        return "订单不存在或无权查看"
    return order["status"]


def scripted_reply(messages, tool_specs):
    """程序写好的两种响应；不是大模型，也不理解用户问题。"""
    # 【离线实验辅助】只返回请求或回答，真正的订单查询由外部执行循环完成。
    if not any(spec["name"] == "get_refund_status" for spec in tool_specs):
        raise ValueError("没有提供查询工具说明")
    results = [m for m in messages if m["role"] == "tool"]
    if results:
        # 第二轮：读取执行循环传回的实际结果，不把“审核中”写死在回答中。
        return {"role": "assistant", "content": f"A1001的退款状态：{results[-1]['content']}。"}
    # 第一轮：只提出“请查A1001”的请求，此时尚未执行查询函数。
    return {"role": "assistant", "content": "", "tool_calls": [{
        "name": "get_refund_status",
        "args": {"order_id": "A1001"},
        "id": "call_comparison_1",
        "type": "tool_call",
    }]}


def run_python(call_model):
    # 步骤1：自己准备消息，以及“工具名 -> 实际函数”的查找表。
    messages = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": QUESTION},
    ]
    tools = {"get_refund_status": get_refund_status}
    # 自己维护执行循环，最多允许3次模型调用。
    for _ in range(3):
        # 步骤2：取得一轮模型回复；离线时call_model就是scripted_reply。
        reply = call_model(messages, TOOL_SPECS)
        messages.append(reply)
        # 步骤3：自己检查是否请求工具；没有请求时，返回最终消息记录。
        requests = reply.get("tool_calls", [])
        if not requests:
            return messages
        for request in requests:
            # 步骤4：自己找函数并执行；本例相当于get_refund_status(order_id="A1001")。
            function = tools[request["name"]]
            result = function(**request["args"])
            # 步骤5：自己把结果放回消息，用请求ID标明它回答的是哪次调用。
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": request["id"],
            })
        # 步骤6：进入下一轮循环，让模型读取工具结果，再判断是否继续。
    raise RuntimeError("达到3次模型调用上限")


def run_langchain(model):
    from langchain.agents import create_agent
    from langchain.agents.middleware import ModelCallLimitMiddleware

    # 步骤1：提供模型、业务函数和要求；创建Agent时还没有执行订单查询。
    agent = create_agent(
        model=model,
        # 传函数本身，不写get_refund_status("A1001")；参数稍后由工具请求提供。
        tools=[get_refund_status],
        system_prompt=INSTRUCTION,
        # 对应手写版的range(3)：限制本次运行最多调用模型3次。
        middleware=[ModelCallLimitMiddleware(run_limit=3, exit_behavior="error")],
    )
    # 步骤2—6：invoke启动框架循环，完成模型调用、请求判断、工具执行、结果回填与继续。
    # 我们不再手写for循环和按名称查找函数的代码，业务函数仍是上面同一个函数。
    result = agent.invoke({
        "messages": [{"role": "user", "content": QUESTION}],
    })
    # 返回整个过程的消息；最后一条通常是最终回答，中间保留工具请求与结果。
    return result["messages"]


def make_scripted_model(reply_function=scripted_reply):
    """把同一个scripted_reply接到框架模型接口，不在适配器里执行工具。"""
    # 【离线实验辅助】让两版收到相同回复；使用已有在线模型客户端时不需要写这个适配器。
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
            # 只保存给回复函数看的工具说明，不执行工具。
            specs = [convert_to_openai_tool(t)["function"] for t in tools]
            return self.model_copy(update={"specs": specs})

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            # 把框架消息转成固定响应函数认识的格式，再把响应包装成框架消息。
            roles = {"human": "user", "ai": "assistant"}
            plain = [{"role": roles.get(m.type, m.type), "content": m.content}
                     for m in messages]
            reply = reply_function(plain, self.specs)
            message = AIMessage(content=reply["content"], tool_calls=reply.get("tool_calls", []))
            return ChatResult(generations=[ChatGeneration(message=message)])

    return ComparisonModel()


def main():
    print("固定响应只用来比较执行过程，不验证自然语言理解。")
    # 手写版：把回复函数交给自己维护的执行循环。
    python_messages = run_python(scripted_reply)
    # 框架版：先把同一个回复函数适配成模型对象，再交给Agent执行循环。
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
