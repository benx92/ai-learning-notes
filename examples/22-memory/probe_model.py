"""适配真实模型接口，记录实际收到的消息；不联网，不模拟语言理解。"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from manual_demo import probe_reply


class ProbeModel(BaseChatModel):
    seen_messages: list = Field(default_factory=list)
    fixed_reply: str | None = None

    @property
    def _llm_type(self):
        return "input-only-memory-probe"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen_messages.append(list(messages))
        roles = {"human": "user", "ai": "assistant"}
        plain = [{"role": roles.get(m.type, m.type), "content": m.content} for m in messages]
        content = self.fixed_reply if self.fixed_reply is not None else probe_reply(plain)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
