"""预先写好的响应，用于检查框架接口；不理解自然语言，不请求网络。"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field


DEMO_TEXT = "A1001的退款申请还没处理，麻烦帮我跟进一下，我挺着急。"
NO_ORDER_TEXT = "退款申请还没处理，我挺着急，帮我跟进一下。"
GOOD_ARGS = {
    "category": "退款进度",
    "order_id": "A1001",
    "urgency": "着急",
    "summary": "用户催促跟进退款申请",
}


def tool_reply(args):
    # 离线辅助：把预设字段放进AIMessage的工具参数，不执行Ticket业务函数。
    return AIMessage(content="", tool_calls=[{
        "name": "Ticket", "args": args, "id": "call_ticket_demo", "type": "tool_call",
    }])


class ScriptedModel(BaseChatModel):
    # 测试替身：依次交回responses，保存调用记录；不理解原话、不抽取新字段。
    responses: list[AIMessage]
    calls: int = 0
    seen_tools: list = Field(default_factory=list)
    seen_messages: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "scripted-structured-output-check"

    def bind_tools(self, tools, **kwargs):
        # 记录框架传来的结构说明；不在这里解析工单。
        converted = [convert_to_openai_tool(t) for t in tools]
        return self.bind(tools=converted, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # 交回下一条预设消息，真正的参数解析和校验由外层框架完成。
        if self.calls >= len(self.responses):
            raise RuntimeError("固定响应已耗尽")
        self.seen_tools = kwargs.get("tools", [])
        self.seen_messages.append(list(messages))
        message = self.responses[self.calls]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=message)])
