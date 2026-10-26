import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_deepseek import ChatDeepSeek

# 使用扩展实验中已封装的只读工具；业务检查在工具内部，返回JSON字符串。
from extensions.components_demo import get_refund_status


def build_agent(model):
    # 步骤3：组装执行对象；这一步登记工具，还没有开始查询。
    return create_agent(
        model=model,
        # 传工具对象本身，Agent收到模型请求后才会调用它。
        tools=[get_refund_status],
        system_prompt=(
            "你是教学售后助手。查询具体订单状态必须使用工具，不得猜测。"
            "订单号缺失时询问用户。查不到时如实说明。"
            "结果是虚构教学数据，不代表真实订单。你不能提交或批准申请。"
        ),
        middleware=[
            # 最多3次模型调用、2次工具调用；超限停止并报错。
            ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=2, exit_behavior="error"),
        ],
    )


def main():
    # 步骤1：检查运行配置；密钥来自环境变量，不写进源码。
    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请先设置自己的DEEPSEEK_API_KEY和可用的LC_CHAT_MODEL")
    # 步骤2：创建在线模型客户端，替代离线实验的固定响应与适配器。
    # 构造客户端不等于已经发送聊天请求；真正请求发生在下面invoke运行过程中。
    model = ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"],
        timeout=45,
        max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )
    agent = build_agent(model)
    # 步骤4：交给Agent运行“模型请求 -> 执行工具 -> 回传结果 -> 再请求模型”的循环。
    result = agent.invoke({
        "messages": [{"role": "user", "content": "查一下A1001的退款状态。"}],
    })
    # 步骤5：查看完整消息，确认工具是否执行、结果是否交回，最后再看最终回答。
    for message in result["messages"]:
        print(type(message).__name__, message.content)
        if getattr(message, "tool_calls", None):
            print("工具请求：", message.tool_calls)


if __name__ == "__main__":
    main()
