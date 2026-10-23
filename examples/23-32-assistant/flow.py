"""23/25/26：同一退货任务的状态、持久中断与事件。"""
import operator
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt


@dataclass(frozen=True)
class RequestContext:
    user: str


class Input(TypedDict):
    task_id: str
    order_id: str
    reason: str


class State(Input, total=False):
    facts: dict
    checked: dict
    draft: dict
    decision: str
    result: dict
    stage: str
    trace: Annotated[list[str], operator.add]


def build_flow(business, saver=None, *, approval=True):
    def event(state, stage):
        get_stream_writer()({"task_id": state["task_id"], "stage": stage,
                             "source": "business_flow"})

    def lookup(state: State, runtime: Runtime[RequestContext]):
        event(state, "querying")
        facts = business.order(state["order_id"], runtime.context.user)
        return {"facts": facts, "stage": "queried", "trace": ["lookup"]}

    def check(state: State, runtime: Runtime[RequestContext]):
        checked = business.check(state["order_id"], runtime.context.user)
        return {"checked": checked, "stage": "checked", "trace": ["check"]}

    def collect_reason(state: State):
        reason = state.get("reason", "").strip()
        while not reason or len(reason) > 200:
            answer = interrupt({"kind": "need_reason", "order_id": state["order_id"],
                                "question": "请提供1—200字的退货原因"})
            reason = answer.get("reason", "").strip() if isinstance(answer, dict) else ""
        return {"reason": reason, "trace": ["collect_reason"]}

    def prepare(state: State, runtime: Runtime[RequestContext]):
        draft = business.prepare(state["task_id"], state["order_id"],
                                 state["reason"], runtime.context.user)
        event(state, "draft_ready" if draft["ok"] else "prepare_failed")
        return {"draft": draft, "stage": "draft_ready" if draft["ok"] else "failed",
                "trace": ["prepare"]}

    def review(state: State):
        decision = interrupt({"kind": "approval", "draft": state["draft"],
                              "effect": "创建本地教学申请，等待审核；不会退款"})
        if (not isinstance(decision, dict) or decision.get("draft_id") != state["draft"]["draft_id"]
                or decision.get("action") not in {"approve", "cancel"}):
            raise ValueError("批准必须对应当前草稿，action只能为approve或cancel")
        return {"decision": decision["action"], "trace": ["review"]}

    def submit(state: State, runtime: Runtime[RequestContext]):
        result = business.submit(state["draft"]["draft_id"], runtime.context.user)
        stage = "submitted" if result["ok"] else "failed"
        event(state, stage)
        return {"result": result, "stage": stage, "trace": ["submit"]}

    def reject(state: State):
        return {"stage": "rejected", "result": state["checked"], "trace": ["reject"]}

    def cancel(state: State):
        event(state, "cancelled")
        return {"stage": "cancelled", "result": {"ok": True, "status": "cancelled"},
                "trace": ["cancel"]}

    builder = StateGraph(State, input_schema=Input, context_schema=RequestContext)
    for name, node in [("lookup", lookup), ("check", check), ("collect_reason", collect_reason),
                       ("prepare", prepare), ("reject", reject)]:
        builder.add_node(name, node)
    builder.add_edge(START, "lookup")
    builder.add_edge("lookup", "check")
    builder.add_conditional_edges("check", lambda s: "collect_reason" if s["checked"]["ok"] else "reject",
                                  ["collect_reason", "reject"])
    builder.add_edge("reject", END)
    builder.add_edge("collect_reason", "prepare")
    if approval:
        for name, node in [("review", review), ("submit", submit), ("cancel", cancel)]:
            builder.add_node(name, node)
        builder.add_conditional_edges("prepare", lambda s: "review" if s["draft"]["ok"] else END,
                                      ["review", END])
        builder.add_conditional_edges("review", lambda s: "submit" if s["decision"] == "approve" else "cancel",
                                      ["submit", "cancel"])
        builder.add_edge("submit", END)
        builder.add_edge("cancel", END)
    else:
        builder.add_edge("prepare", END)
    return builder.compile(checkpointer=saver)
