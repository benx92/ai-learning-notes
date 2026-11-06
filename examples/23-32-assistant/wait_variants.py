"""25：静态断点与并行中断的独立机制实验；不办理业务。"""
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    replies: Annotated[list[str], operator.add]


def static_demo():
    calls = []
    def work(state):
        calls.append(1)
        return {"replies": ["work"]}
    builder = StateGraph(State)
    builder.add_node("work", work)
    builder.add_edge(START, "work")
    builder.add_edge("work", END)
    graph = builder.compile(checkpointer=InMemorySaver(), interrupt_before=["work"])
    config = {"configurable": {"thread_id": "static-25"}}
    graph.invoke({"replies": []}, config)
    snapshot = graph.get_state(config)
    assert snapshot.next == ("work",) and not calls
    assert not any(task.interrupts for task in snapshot.tasks)
    graph.invoke(None, config)
    assert len(calls) == 1
    print("静态断点：节点开始前暂停；None续跑后执行1次")


def parallel_demo():
    def ask_a(state):
        answer = interrupt({"reviewer": "a"})
        return {"replies": ["a:" + answer]}
    def ask_b(state):
        answer = interrupt({"reviewer": "b"})
        return {"replies": ["b:" + answer]}
    builder = StateGraph(State)
    for name, node in [("a", ask_a), ("b", ask_b)]:
        builder.add_node(name, node)
        builder.add_edge(START, name)
        builder.add_edge(name, END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "parallel-25"}}
    graph.invoke({"replies": []}, config)
    snapshot = graph.get_state(config)
    pending = {item.value["reviewer"]: item.id
               for task in snapshot.tasks if task.name in snapshot.next
               for item in task.interrupts}
    assert set(pending) == {"a", "b"}
    graph.invoke(Command(resume={pending["a"]: "approve"}), config)
    snapshot = graph.get_state(config)
    remaining = [item for task in snapshot.tasks if task.name in snapshot.next
                 for item in task.interrupts]
    assert len(remaining) == 1 and remaining[0].value["reviewer"] == "b"
    result = graph.invoke(Command(resume={remaining[0].id: "cancel"}), config)
    assert sorted(result["replies"]) == ["a:approve", "b:cancel"]
    assert not graph.get_state(config).next
    print("并行中断：2项待答 → 按ID答1项 → 剩1项 → 全部结束")


if __name__ == "__main__":
    static_demo()
    parallel_demo()
