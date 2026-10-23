"""24：有界重查，以及携带不同输入的动态派发。"""
import operator
from typing import Annotated, TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send


class RetryState(TypedDict):
    attempts: int
    failures: int
    ok: bool
    status: str


def retry_graph():
    def query(state):
        attempts = state["attempts"] + 1
        return {"attempts": attempts, "ok": attempts > state["failures"]}

    def route(state):
        if state["ok"]:
            return "done"
        return "query" if state["attempts"] < 3 else "failed"

    builder = StateGraph(RetryState)
    builder.add_node("query", query)
    builder.add_node("done", lambda s: {"status": "done"})
    builder.add_node("failed", lambda s: {"status": "failed"})
    builder.add_edge(START, "query")
    builder.add_conditional_edges("query", route, ["query", "done", "failed"])
    builder.add_edge("done", END)
    builder.add_edge("failed", END)
    return builder.compile()


class BatchState(TypedDict):
    order_ids: list[str]
    results: Annotated[list[dict], operator.add]
    ordered: list[dict]


def batch_graph(business, user):
    def dispatch(state):
        if not state["order_ids"]:
            return "collect"
        return [Send("worker", {"index": i, "order_id": order_id})
                for i, order_id in enumerate(state["order_ids"])]

    def worker(job):
        result = business.check(job["order_id"], user)
        return {"results": [{"index": job["index"], "order_id": job["order_id"], **result}]}

    def collect(state):
        ordered = sorted(state["results"], key=lambda item: item["index"])
        if [r["index"] for r in ordered] != list(range(len(state["order_ids"]))):
            raise ValueError("子任务结果缺失或重复")
        return {"ordered": ordered}

    builder = StateGraph(BatchState)
    builder.add_node("worker", worker)
    builder.add_node("collect", collect)
    builder.add_conditional_edges(START, dispatch, ["worker", "collect"])
    builder.add_edge("worker", "collect")
    builder.add_edge("collect", END)
    return builder.compile()
