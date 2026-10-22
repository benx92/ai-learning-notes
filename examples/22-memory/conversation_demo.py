"""同一个Agent、两条thread；默认使用输入探针，可选在线模型。"""

import argparse
import os

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from manual_demo import BASE_PROMPT, FIRST, FOLLOWUP
from probe_model import ProbeModel


def build_agent(model, checkpointer):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=BASE_PROMPT,
        checkpointer=checkpointer,
        middleware=[ModelCallLimitMiddleware(run_limit=1, exit_behavior="error")],
    )


def two_turns(agent, thread_id):
    config = {"configurable": {"thread_id": thread_id}}
    agent.invoke({"messages": [{"role": "user", "content": FIRST}]}, config=config)
    result = agent.invoke({"messages": [{"role": "user", "content": FOLLOWUP}]}, config=config)
    return result


def make_live_model():
    from langchain_deepseek import ChatDeepSeek

    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请设置自己的DEEPSEEK_API_KEY和LC_CHAT_MODEL")
    return ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"], timeout=45, max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    options = parser.parse_args()
    model = make_live_model() if options.live else ProbeModel()
    checkpointer = InMemorySaver()
    agent = build_agent(model, checkpointer)
    result = two_turns(agent, "conversation-a")
    print("同一会话第2轮：", result["messages"][-1].content)
    config = {"configurable": {"thread_id": "conversation-a"}}
    snapshot = agent.get_state(config)
    print("会话状态中的消息条数：", len(snapshot.values["messages"]))
    print("会话状态中的消息类型：", [m.type for m in snapshot.values["messages"]])
    fresh = agent.invoke({"messages": [{"role": "user", "content": FOLLOWUP}]},
                         config={"configurable": {"thread_id": "conversation-b"}})
    print("另一场会话：", fresh["messages"][-1].content)
    if not options.live:
        print("第2轮模型实际收到的消息：")
        for message in model.seen_messages[1]:
            print(message.type, message.content)


if __name__ == "__main__":
    main()
