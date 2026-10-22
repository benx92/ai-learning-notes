"""用固定模型响应观察真实框架循环，不请求在线模型。"""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent_demo import build_agent


class ScriptedModel(BaseChatModel):
    """固定请求用于验证框架调度，不模拟语言理解。"""

    repeat: bool = False
    calls: int = 0

    @property
    def _llm_type(self):
        return "scripted-framework-check"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        has_result = any(isinstance(m, ToolMessage) for m in messages)
        if has_result and not self.repeat:
            message = AIMessage(content="教学查询结果：A1001仍在审核中。")
        else:
            message = AIMessage(content="", tool_calls=[{
                "name": "get_refund_status",
                "args": {"order_id": "A1001"},
                "id": f"call_test_{self.calls}",
                "type": "tool_call",
            }])
        return ChatResult(generations=[ChatGeneration(message=message)])


def main():
    model = ScriptedModel()
    agent = build_agent(model)
    result = agent.invoke({
        "messages": [{"role": "user", "content": "查一下A1001的退款状态。"}],
    })
    print("固定响应用于观察框架，不代表模型理解了问题。")
    for index, message in enumerate(result["messages"], start=1):
        print(f"{index}. {type(message).__name__}: {message.content}")
        if getattr(message, "tool_calls", None):
            print("   tool_calls:", json.dumps(message.tool_calls, ensure_ascii=False))
        if isinstance(message, ToolMessage):
            print("   tool_call_id:", message.tool_call_id)
    print(f"模型调用：{model.calls}次")
    print("工具结果：", sum(isinstance(m, ToolMessage) for m in result["messages"]), "条")


if __name__ == "__main__":
    main()
