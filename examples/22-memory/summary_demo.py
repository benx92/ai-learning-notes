"""使用固定摘要响应检查摘要中间件确实触发，未验证摘要质量。"""

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from manual_demo import BASE_PROMPT, FIRST, FOLLOWUP
from probe_model import ProbeModel


SUMMARY = "教学固定摘要：本次讨论的订单是A1001，尚未查询实时状态。"


def build_summary_agent(model, summary_model):
    summarizer = SummarizationMiddleware(
        model=summary_model,
        trigger=("messages", 4),
        keep=("messages", 2),
        summary_prompt="只保留继续售后对话所需的信息，不添加事实。对话：{messages}",
        trim_tokens_to_summarize=None,
    )
    return create_agent(
        model=model, tools=[], system_prompt=BASE_PROMPT,
        checkpointer=InMemorySaver(), middleware=[summarizer],
    )


def main():
    model = ProbeModel()
    summary_model = ProbeModel(fixed_reply=SUMMARY)
    agent = build_summary_agent(model, summary_model)
    config = {"configurable": {"thread_id": "summary-demo"}}
    for text in (FIRST, "谢谢。", FOLLOWUP):
        result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config=config)
        print("本轮结束后的消息条数：", len(result["messages"]))
    print("摘要模型调用次数：", len(summary_model.seen_messages))
    print("最终回复：", result["messages"][-1].content)
    print("当前状态中的第一条消息：", result["messages"][0].content)


if __name__ == "__main__":
    main()
