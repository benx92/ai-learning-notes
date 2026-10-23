"""23—31的可重复阅读实验。全部默认离线，使用临时教学数据。"""
import argparse
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from typing import TypedDict

from assistant import Assistant
from flow import RequestContext, build_flow
from harness import Background, Schedule, TaskBoard, assemble_request, bounded_call, persist_output
from routing import batch_graph, retry_graph
from team import MessageBus, Protocol


def state_demo(folder):
    app = Assistant(folder)
    result = build_flow(app.business, approval=False).invoke(
        {"task_id": "state", "order_id": "A3003", "reason": "尺寸不合适"},
        context=RequestContext("demo-user"))
    return {"trace": result["trace"], "stage": result["stage"], "draft": result["draft"],
            "applications": app.business.application_count()}


def routing_demo(folder):
    app = Assistant(folder)
    retries = [retry_graph().invoke({"attempts": 0, "failures": n, "ok": False, "status": ""},
                                    {"recursion_limit": 15}) for n in (0, 2, 8)]
    graph = batch_graph(app.business, "demo-user")
    batches = [graph.invoke({"order_ids": ids, "results": [], "ordered": []},
                            {"max_concurrency": 2})["ordered"]
               for ids in [[], ["A3003", "A3004", "missing", "A3003"]]]
    return {"retries": retries, "batches": batches}


def streaming_demo(folder):
    app = Assistant(folder)
    graph = build_flow(app.business, approval=False)
    normal = list(graph.stream({"task_id": "stream", "order_id": "A3003", "reason": "不合适"},
                              context=RequestContext("demo-user"), stream_mode=["updates", "custom"]))
    class FaultState(TypedDict):
        task_id: str
    def fail(state):
        get_stream_writer()({"task_id": state["task_id"], "stage": "checking"})
        raise RuntimeError("受控教学故障")
    builder = StateGraph(FaultState)
    builder.add_node("fail", fail)
    builder.add_edge(START, "fail")
    builder.add_edge("fail", END)
    fault = []
    try:
        for mode, data in builder.compile().stream({"task_id": "fault"}, stream_mode=["custom", "updates"]):
            fault.append({"mode": mode, "data": data})
    except RuntimeError:
        fault.append({"mode": "application_error", "data": {"stage": "failed", "task_id": "fault"}})
    return {"normal": normal, "fault": fault}


def skills_demo(folder):
    return {name: assemble_request(name, "query", {"policy_search", "order_query", "prepare_return"})
            for name in ["policy", "return"]}


def long_task_demo(folder):
    path = Path(folder) / "tasks.sqlite"
    board = TaskBoard(path)
    board.add("check", "核对一批售后事实")
    board.add("draft", "汇总核对结果", ["check"])
    blocked = not board.claim("draft", "worker")
    board.claim("check", "worker")
    calls, delays = [], []
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("教学超时")
        return {"order_id": "A3003", "source": "固定教学查询响应"}
    result = bounded_call(flaky, wait=delays.append)
    evidence = persist_output(json.dumps(result) * 100, Path(folder) / "outputs")
    board.remember("demo-user", "current-order", "A3003", "任务check的输入")
    board.complete("check", "worker", evidence)
    reopened = TaskBoard(path)
    return {"initially_blocked": blocked, "calls": len(calls), "simulated_delays": delays,
            "ready_after_reopen": reopened.claim("draft", "worker"),
            "memory": reopened.recall("demo-user", "current-order"), "tasks": reopened.list()}


def background_demo(folder):
    background = Background()
    started = Event()
    try:
        def slow(stop):
            started.set()
            stop.wait(1)
            return {"cancel_requested": stop.is_set()}
        job = background.start(slow)
        started.wait(2)
        before = background.get(job)
        other_input = "后台运行期间，主程序仍能处理这一输入"
        cancellation = background.cancel(job)
    finally:
        background.close()
    schedule = Schedule(Path(folder) / "schedule.sqlite")
    schedule.add("check-later", 100, interval=60, count=2)
    ticks = [schedule.tick(now) for now in (99, 100, 100)]
    pending = Schedule(Path(folder) / "schedule.sqlite").pending()
    schedule.cancel("check-later")
    return {"before": before, "other_input": other_input, "cancel": cancellation,
            "after": background.get(job), "ticks": ticks, "pending_before_cancel": pending,
            "after_cancel": schedule.tick(200)}


def delegation_demo(folder):
    from pydantic import Field
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from delegation import build_delegation

    class FixedModel(BaseChatModel):
        names: tuple[str, ...] = ()
        seen: list[dict] = Field(default_factory=list)
        @property
        def _llm_type(self):
            return "fixed-delegation-mechanism-check"
        def bind_tools(self, tools, **kwargs):
            return self.model_copy(update={"names": tuple(t.name for t in tools)})
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.seen.append({"tools": self.names, "message_count": len(messages)})
            results = [m for m in messages if isinstance(m, ToolMessage)]
            if results:
                message = AIMessage(content="固定响应汇总：" + "\n".join(str(m.content) for m in results))
            else:
                args = {"lookup": {"order_id": "A3003"}, "search": {"question": "会员退货"},
                        "order_expert": {"query": "核对A3003"}, "policy_expert": {"query": "解释会员退货"}}
                message = AIMessage(content="", tool_calls=[
                    {"name": name, "args": args[name], "id": "fixed-" + name, "type": "tool_call"}
                    for name in self.names])
            return ChatResult(generations=[ChatGeneration(message=message)])

    app = Assistant(folder)
    model = FixedModel()
    baseline, supervisor = build_delegation(model, app.business, app.policy, "demo-user")
    reports = {}
    for name, agent in [("baseline", baseline), ("delegated", supervisor)]:
        offset = len(model.seen)
        result = agent.invoke({"messages": [{"role": "user", "content": "核对A3003与会员退货条件"}]},
                              {"recursion_limit": 20, "max_concurrency": 1})
        reports[name] = {"calls": len(model.seen) - offset, "inputs": model.seen[offset:],
                         "answer": result["messages"][-1].content}
    return {"mode": "固定模型响应，只验证真实框架委派与消息交接", **reports}


def team_demo(folder):
    path = Path(folder) / "team.sqlite"
    board, bus, protocol = TaskBoard(path), MessageBus(path), Protocol()
    board.add("one", "只读核对一")
    board.add("two", "只读核对二")
    stop = Event()
    def worker(name):
        while not stop.is_set():
            for message in bus.inbox(name):
                if message["kind"] == "shutdown_request":
                    bus.send(name, "lead", "shutdown_response", message["task"], message["request"], {"approve": True})
                    bus.ack(message["id"], name)
                    return
                bus.ack(message["id"], name)
            for task in board.list():
                if task["status"] == "pending" and board.claim(task["id"], name):
                    evidence = {"source": "固定教学核对", "worker": name}
                    board.complete(task["id"], name, evidence)
                    bus.send(name, "lead", "result", task["id"], "run-1", evidence)
            stop.wait(0.01)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, name) for name in ("alice", "bob")]
        deadline = time.monotonic() + 3
        while any(t["status"] != "completed" for t in board.list()) and time.monotonic() < deadline:
            stop.wait(0.01)
        tasks = board.list()
        for name in ("alice", "bob"):
            request = protocol.request(name, "shutdown", "team-run")
            bus.send("lead", name, "shutdown_request", "team-run", request, {})
        while not protocol.finished() and time.monotonic() < deadline:
            for message in bus.inbox("lead"):
                if message["kind"] == "shutdown_response":
                    protocol.receive(message)
                bus.ack(message["id"], "lead")
            stop.wait(0.01)
        stop.set()
        for future in futures:
            future.result(timeout=2)
    return {"tasks": tasks, "protocol_finished": protocol.finished(), "requests": protocol.pending,
            "mode": "两个线程的固定执行者；不是两个真实模型Agent"}


DEMOS = {"state": state_demo, "routing": routing_demo, "stream": streaming_demo,
         "skills": skills_demo, "long-task": long_task_demo, "background": background_demo,
         "delegation": delegation_demo, "team": team_demo}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=DEMOS)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        print(json.dumps(DEMOS[args.demo](folder), ensure_ascii=False, indent=2, default=str))
