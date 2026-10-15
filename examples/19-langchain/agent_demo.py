import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_deepseek import ChatDeepSeek

from components_demo import get_refund_status


def build_agent(model):
    return create_agent(
        model=model,
        tools=[get_refund_status],
        system_prompt=(
            "你是教学售后助手。查询具体订单状态必须使用工具，不得猜测。"
            "订单号缺失时询问用户。查不到时如实说明。"
            "结果是虚构教学数据，不代表真实订单。你不能提交或批准申请。"
        ),
        middleware=[
            ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=2, exit_behavior="error"),
        ],
    )


def main():
    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请先设置自己的DEEPSEEK_API_KEY和可用的LC_CHAT_MODEL")
    model = ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"],
        timeout=45,
        max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )
    agent = build_agent(model)
    result = agent.invoke({
        "messages": [{"role": "user", "content": "查一下A1001的退款状态。"}],
    })
    for message in result["messages"]:
        print(type(message).__name__, message.content)
        if getattr(message, "tool_calls", None):
            print("工具请求：", message.tool_calls)


if __name__ == "__main__":
    main()
