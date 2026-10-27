"""对照Agent最终输出的入口；固定响应，不查询或修改订单。"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy

from fixtures import DEMO_TEXT, GOOD_ARGS, ScriptedModel, tool_reply
from schemas import Ticket


def build_agent(model):
    # 创建Agent对象，不立即运行；最终工单放在运行结果的structured_response中。
    return create_agent(
        model=model,
        tools=[],  # 没有查询订单或提交工单的业务工具。
        # 用工具参数承载最终Ticket；关闭策略自动修正，单独观察一次结构结果。
        response_format=ToolStrategy(Ticket, handle_errors=False),
        system_prompt="从用户原话整理售后工单草稿，不猜测订单号，不核定订单事实。",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="error")],
    )


def main():
    # 预设回复只验证Agent入口，不表示模型已经理解或核验了用户诉求。
    model = ScriptedModel(responses=[tool_reply(GOOD_ARGS)])
    result = build_agent(model).invoke({"messages": [{"role": "user", "content": DEMO_TEXT}]})
    print("Agent结构化结果类型：", type(result["structured_response"]).__name__)
    # Ticket对象编码为JSON字符串，用于打印；此处没有写入业务系统。
    print(result["structured_response"].model_dump_json())
    print("消息类型：", [m.type for m in result["messages"]])


if __name__ == "__main__":
    main()
