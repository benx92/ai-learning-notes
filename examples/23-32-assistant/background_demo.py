"""29：标准库离线实验，观察后台取消与到期事件到结果的交接。"""
import json
from pathlib import Path
import tempfile
from threading import Event

from harness import Background, Schedule


def background_demo(folder):
    background = Background()
    started = Event()
    try:
        def slow(stop):
            started.set()
            stop.wait()
            return {"order_id": "A3003", "cancel_requested": stop.is_set(),
                    "record_created": False}

        job = background.start(slow)
        if not started.wait(2):
            raise TimeoutError("后台执行者未及时启动")
        before = background.get(job)
        other_input = "核对尚未完成，主程序可以先接收政策问题"
        cancellation = background.cancel(job)
    finally:
        background.close()

    path = Path(folder) / "schedule.sqlite"
    schedule = Schedule(path)
    schedule.add("check-later", 100, interval=60, count=2)
    ticks = [schedule.tick(now) for now in (99, 100, 100)]
    reopened = Schedule(path)
    pending = reopened.pending()

    # 调度表不保存业务输入；这个映射仅用于本次教学装配。
    inputs = {"check-later": {"order_id": "A3003", "reason": "尺寸不合适"}}
    deliveries = []
    for plan_id, due in pending:
        done = Event()
        executor = Background()
        request = dict(inputs[plan_id])
        try:
            def check(stop):
                try:
                    return {**request, "source": "固定教学响应，未查询真实订单",
                            "record_created": True, "draft_created": False,
                            "application_created": False}
                finally:
                    done.set()

            execution = executor.start(check)
            if not done.wait(2):
                raise TimeoutError("教学核对未及时返回")
        finally:
            executor.close()
        outcome = executor.get(execution)
        event = {"plan_id": plan_id, "due": due, "job_id": execution, **outcome}
        deliveries.append(event)
        if outcome["status"] == "completed" and outcome["result"].get("record_created") is True:
            reopened.acknowledge(plan_id, due)

    pending_after_ack = reopened.pending()
    second_tick = reopened.tick(160)
    reopened.cancel("check-later")
    return {"before": before, "other_input": other_input, "cancel": cancellation,
            "after": background.get(job), "ticks": ticks,
            "pending_before_consume": pending, "deliveries": deliveries,
            "pending_after_ack": pending_after_ack, "second_tick": second_tick,
            "pending_after_cancel": reopened.pending(), "after_cancel": reopened.tick(200)}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        print(json.dumps(background_demo(folder), ensure_ascii=False, indent=2))
