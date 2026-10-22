"""区分已保存的状态字段与本轮模型能看见的内容。仅用于无工具对话。"""

import re
from typing import NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import dynamic_prompt, wrap_model_call
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from manual_demo import BASE_PROMPT, FIRST, FOLLOWUP
from probe_model import ProbeModel


class SupportState(AgentState):
    active_order_id: NotRequired[str | None]


@wrap_model_call
def latest_user_view(request, handler):
    latest = next(m for m in reversed(request.messages) if isinstance(m, HumanMessage))
    return handler(request.override(messages=[latest]))


@dynamic_prompt
def prompt_with_order(request):
    order_id = request.state.get("active_order_id")
    return BASE_PROMPT + (f" 当前会话选定的订单号：{order_id}。" if order_id else "")


def save_active_order(agent, config, order_id, source_text):
    if not re.fullmatch(r"A[0-9]{4}", order_id):
        raise ValueError("订单号格式不正确")
    if not re.search(rf"(?<![A-Za-z0-9]){re.escape(order_id)}(?![A-Za-z0-9])", source_text):
        raise ValueError("订单号未在本次来源中独立出现")
    agent.update_state(config, {"active_order_id": order_id})


def build_state_agent(model, inject_order=True):
    middleware = [latest_user_view]
    if inject_order:
        middleware.append(prompt_with_order)
    return create_agent(
        model=model, tools=[], system_prompt=BASE_PROMPT,
        state_schema=SupportState, checkpointer=InMemorySaver(), middleware=middleware,
    )


def main():
    for inject in (False, True):
        model = ProbeModel()
        agent = build_state_agent(model, inject_order=inject)
        config = {"configurable": {"thread_id": "state-demo"}}
        agent.invoke({"messages": [{"role": "user", "content": FIRST}]}, config=config)
        save_active_order(agent, config, "A1001", FIRST)
        result = agent.invoke({"messages": [{"role": "user", "content": FOLLOWUP}]}, config=config)
        print("注入状态字段：", inject, result["messages"][-1].content)
        print("保存的active_order_id：", agent.get_state(config).values["active_order_id"])
        print("保存的消息条数：", len(agent.get_state(config).values["messages"]))
        print("本轮模型输入条数：", len(model.seen_messages[-1]))


if __name__ == "__main__":
    main()
