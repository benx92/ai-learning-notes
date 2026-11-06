"""26：逐条消费真实图事件；内存检查点只供本进程暂停恢复。"""
import argparse
import json
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from business import Business
from flow import RequestContext, build_flow


def to_events(graph, inputs, config, *, task_id, context=None):
    """无子图、无模型的教学适配器：一次调用只有一个终止事件。"""
    paused = False
    try:
        for mode, data in graph.stream(
            inputs, config, context=context, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                yield {"type": "stage", "task_id": task_id, "stage": data["stage"]}
            elif "__interrupt__" in data:
                paused = True
                yield {"type": "interrupt", "task_id": task_id,
                       "items": [{"id": item.id, "value": item.value}
                                 for item in data["__interrupt__"]]}
            else:
                for node, update in data.items():
                    if "stage" in update:
                        yield {"type": "state", "task_id": task_id,
                               "node": node, "stage": update["stage"]}
    except RuntimeError as exc:
        yield {"type": "error", "task_id": task_id, "error": type(exc).__name__}
        return
    yield {"type": "paused" if paused else "done", "task_id": task_id}


def to_sse(event):
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def events_demo(folder, *, sse=False):
    service = Business(Path(folder) / "business.sqlite")
    graph = build_flow(service, InMemorySaver())
    config = {"configurable": {"thread_id": "events-26"}}
    context = RequestContext("demo-user")
    def render(inputs):
        terminal = []
        for event in to_events(graph, inputs, config, task_id="events-26", context=context):
            if event["type"] in {"paused", "done", "error"}:
                terminal.append(event["type"])
            print(to_sse(event) if sse else json.dumps(event, ensure_ascii=False),
                  end="" if sse else "\n", flush=True)
        assert len(terminal) == 1
        return terminal[0]
    assert render({"task_id": "events-26", "order_id": "A3003", "reason": "尺寸不合适"}) == "paused"
    draft = graph.get_state(config).values["draft"]
    assert render(Command(resume={"action": "cancel", "draft_id": draft["draft_id"]})) == "done"
    assert graph.get_state(config).values["stage"] == "cancelled"
    assert service.application_count() == 0
    builder = StateGraph(FaultState)
    builder.add_node("fail", fail)
    builder.add_edge(START, "fail")
    builder.add_edge("fail", END)
    failure_types = []
    for event in to_events(builder.compile(), {"task_id": "fault-26"}, {}, task_id="fault-26"):
        failure_types.append(event["type"])
        print(to_sse(event) if sse else json.dumps(event, ensure_ascii=False),
              end="" if sse else "\n", flush=True)
    assert failure_types == ["stage", "error"]


def consume(graph, inputs, config, *, context=None):
    """逐条打印，不先用list收完整条流；最后由调用方核对快照。"""
    for mode, data in graph.stream(
        inputs, config, context=context, stream_mode=["updates", "custom"]
    ):
        print(json.dumps({"mode": mode, "data": data}, ensure_ascii=False, default=str), flush=True)


def approval_demo(folder):
    service = Business(Path(folder) / "business.sqlite")
    graph = build_flow(service, InMemorySaver())
    config = {"configurable": {"thread_id": "stream-26"}}
    context = RequestContext("demo-user")
    consume(graph, {"task_id": "stream-26", "order_id": "A3003", "reason": "尺寸不合适"},
            config, context=context)
    snapshot = graph.get_state(config)
    pending = [item.value for task in snapshot.tasks for item in task.interrupts]
    assert snapshot.next == ("review",) and pending[0]["kind"] == "approval"
    assert service.application_count() == 0
    print("界面状态：等待确认；申请数：0", flush=True)

    # 固定教学选择，不是模型批准；演示不接收真实网页用户输入。
    response = {"action": "cancel", "draft_id": pending[0]["draft"]["draft_id"]}
    consume(graph, Command(resume=response), config, context=context)
    final = graph.get_state(config)
    assert not final.next and final.values["stage"] == "cancelled"
    assert service.application_count() == 0
    print("界面状态：已取消；申请数：0", flush=True)


class FaultState(TypedDict):
    task_id: str


def fail(state):
    get_stream_writer()({"task_id": state["task_id"], "stage": "checking"})
    raise RuntimeError("受控教学故障")


def fault_demo():
    builder = StateGraph(FaultState)
    builder.add_node("fail", fail)
    builder.add_edge(START, "fail")
    builder.add_edge("fail", END)
    try:
        consume(builder.compile(), {"task_id": "fault-26"}, {})
    except RuntimeError as exc:
        print(json.dumps({"mode": "application_error", "data": {
            "task_id": "fault-26", "stage": "failed", "error": str(exc)
        }}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", action="store_true", help="输出界面事件")
    parser.add_argument("--sse", action="store_true", help="输出SSE报文，不启动HTTP服务")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        if args.events or args.sse:
            events_demo(folder, sse=args.sse)
        else:
            approval_demo(folder)
    if not args.events and not args.sse:
        fault_demo()


if __name__ == "__main__":
    main()
