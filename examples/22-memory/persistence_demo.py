"""两个独立进程，用同一SQLite文件与thread_id接续会话。"""

import argparse

from langgraph.checkpoint.sqlite import SqliteSaver

from conversation_demo import build_agent
from manual_demo import FIRST, FOLLOWUP
from probe_model import ProbeModel


def run_phase(database_path, phase, thread_id="restart-demo"):
    config = {"configurable": {"thread_id": thread_id}}
    with SqliteSaver.from_conn_string(database_path) as checkpointer:
        agent = build_agent(ProbeModel(), checkpointer)
        previous = agent.get_state(config).values.get("messages", [])
        if phase == "seed" and previous:
            raise ValueError("该会话已有记录，请使用新的数据库路径或thread_id")
        if phase == "resume" and not previous:
            raise ValueError("该会话没有记录，请先运行seed")
        if phase not in {"seed", "resume"}:
            raise ValueError("phase必须为seed或resume")
        text = FIRST if phase == "seed" else FOLLOWUP
        result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config=config)
        return {"reply": result["messages"][-1].content, "messages": len(result["messages"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seed", "resume"])
    parser.add_argument("--db", required=True)
    parser.add_argument("--thread", default="restart-demo")
    options = parser.parse_args()
    print(run_phase(options.db, options.phase, options.thread))


if __name__ == "__main__":
    main()
