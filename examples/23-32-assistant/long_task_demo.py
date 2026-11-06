"""28：使用固定响应观察计划、产物、记忆与有限恢复，不办理退货。"""
import hashlib
import json
import tempfile
from pathlib import Path

from harness import TaskBoard, bounded_call, persist_output


def long_task_demo(folder):
    path = Path(folder) / "tasks.sqlite"
    board = TaskBoard(path)
    board.add("check", "保存A3003的教学核对记录")
    board.add("summary", "汇总核对记录供后续准备使用", ["check"])
    blocked = not board.claim("summary", "worker")
    if not board.claim("check", "worker"):
        raise RuntimeError("未取得核对任务")
    calls, delays = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("教学超时")
        return {"order_id": "A3003", "reason": "尺寸不合适", "source": "固定教学响应"}

    result = bounded_call(flaky, wait=delays.append)
    # 重复文本仅用于制造长输出；文件是日志文本，不是一份JSON文档。
    evidence = persist_output(json.dumps(result, ensure_ascii=False) * 100, Path(folder) / "outputs")
    board.remember("demo-user", "A3003:reason", result["reason"], "本次固定教学响应")
    board.complete("check", "worker", evidence)
    reopened = TaskBoard(path)
    ready = reopened.claim("summary", "worker")
    if not ready:
        raise RuntimeError("汇总依赖尚未满足")
    saved = Path(evidence["path"]).read_text(encoding="utf-8")
    verified = hashlib.sha256(saved.encode()).hexdigest() == evidence["sha256"]
    if not verified:
        raise ValueError("保存的输出与引用不符")
    memory = reopened.recall("demo-user", "A3003:reason")
    summary = {"order_id": result["order_id"], "reason": memory[0],
               "source_sha256": evidence["sha256"], "business_action": "未创建草稿或申请"}
    summary_output = persist_output(json.dumps(summary, ensure_ascii=False), Path(folder) / "outputs")
    reopened.complete("summary", "worker", summary_output)
    return {"initially_blocked": blocked, "calls": len(calls), "simulated_delays": delays,
            "ready_after_reopen": ready, "output_verified": verified,
            "memory": memory, "summary": summary, "tasks": reopened.list()}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        print(json.dumps(long_task_demo(folder), ensure_ascii=False, indent=2))
