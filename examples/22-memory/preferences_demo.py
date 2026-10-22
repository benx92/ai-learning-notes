"""用同一个Store跨会话读取用户主动设置的回复偏好。"""

from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from manual_demo import BASE_PROMPT, FIRST, FOLLOWUP
from probe_model import ProbeModel


@dataclass(frozen=True)
class Viewer:
    user_id: str


def set_reply_style(store, user_id, style):
    if style not in {"简短", "详细"}:
        raise ValueError("不支持的回复风格")
    store.put(("users", user_id, "preferences"), "reply_style",
              {"value": style, "source": "用户主动设置"})


@dynamic_prompt
def prompt_with_preference(request):
    user_id = request.runtime.context.user_id
    item = request.runtime.store.get(("users", user_id, "preferences"), "reply_style")
    style = item.value["value"] if item else None
    return BASE_PROMPT + (f" 回复偏好：{style}。" if style in {"简短", "详细"} else "")


def build_preference_agent(model, store, inject_preference=True):
    return create_agent(
        model=model, tools=[], system_prompt=BASE_PROMPT,
        store=store, checkpointer=InMemorySaver(), context_schema=Viewer,
        middleware=[prompt_with_preference] if inject_preference else [],
    )


def main():
    store = InMemoryStore()
    set_reply_style(store, "user-a", "简短")
    model = ProbeModel()
    agent = build_preference_agent(model, store)
    agent.invoke({"messages": [{"role": "user", "content": FIRST}]},
                 config={"configurable": {"thread_id": "a-yesterday"}}, context=Viewer("user-a"))
    fresh = agent.invoke({"messages": [{"role": "user", "content": FOLLOWUP}]},
                         config={"configurable": {"thread_id": "a-today"}}, context=Viewer("user-a"))
    print("新会话读取偏好：", fresh["messages"][-1].content)
    other = agent.invoke({"messages": [{"role": "user", "content": FOLLOWUP}]},
                         config={"configurable": {"thread_id": "b-today"}}, context=Viewer("user-b"))
    print("另一用户没有该偏好：", other["messages"][-1].content)
    print("长期记录：", store.get(("users", "user-a", "preferences"), "reply_style").value)


if __name__ == "__main__":
    main()
