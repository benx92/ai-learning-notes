"""对照Agent最终输出的入口；固定响应，不查询或修改订单。"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy

from fixtures import DEMO_TEXT, GOOD_ARGS, ScriptedModel, tool_reply
from schemas import Ticket


def build_agent(model):
    return create_agent(
        model=model,
        tools=[],
        response_format=ToolStrategy(Ticket, handle_errors=False),
        system_prompt="从用户原话整理售后工单草稿，不猜测订单号，不核定订单事实。",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="error")],
    )


def main():
    model = ScriptedModel(responses=[tool_reply(GOOD_ARGS)])
    result = build_agent(model).invoke({"messages": [{"role": "user", "content": DEMO_TEXT}]})
    print("Agent结构化结果类型：", type(result["structured_response"]).__name__)
    print(result["structured_response"].model_dump_json())
    print("消息类型：", [m.type for m in result["messages"]])


if __name__ == "__main__":
    main()
