"""离线行为检查；不证明真实模型效果。"""
from contextlib import closing
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from assistant import Assistant
from business import Business
from context_demo import main as context_main, current_user
from flow import RequestContext, build_flow
from harness import Background, Schedule, TaskBoard, assemble_request, bounded_call, persist_output
from routing import batch_graph, retry_graph
from team import MessageBus, Protocol

HERE = Path(__file__).parent


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.app = Assistant(self.folder)

    def tearDown(self):
        self.temp.cleanup()

    def test_23_updates_and_input_filter(self):
        graph = build_flow(self.app.business, approval=False)
        result = graph.invoke({"task_id": "t", "order_id": "A3003", "reason": "尺寸不合适",
                               "checked": {"ok": True}}, context=RequestContext("demo-user"))
        self.assertEqual(result["trace"], ["lookup", "check", "collect_reason", "prepare"])
        self.assertTrue(result["facts"]["ok"])
        self.assertEqual(result["stage"], "draft_ready")
        self.assertEqual(self.app.business.application_count(), 0)

    def test_rejected_input_cannot_fake_pass(self):
        result = build_flow(self.app.business, approval=False).invoke(
            {"task_id": "t", "order_id": "A3004", "reason": "不合适", "checked": {"ok": True}},
            context=RequestContext("demo-user"))
        self.assertEqual(result["stage"], "rejected")
        self.assertNotIn("prepare", result["trace"])

    def test_retry_bound(self):
        graph = retry_graph()
        for failures, expected in [(0, "done"), (2, "done"), (8, "failed")]:
            result = graph.invoke({"attempts": 0, "failures": failures, "ok": False, "status": ""}, {"recursion_limit": 15})
            self.assertEqual(result["status"], expected)
            self.assertLessEqual(result["attempts"], 3)

    def test_dynamic_batch_empty_duplicates_errors(self):
        graph = batch_graph(self.app.business, "demo-user")
        for ids in [[], ["A3003"], ["A3003", "A3003", "missing", "A3004"]]:
            result = graph.invoke({"order_ids": ids, "results": [], "ordered": []}, {"max_concurrency": 2})
            self.assertEqual([r["order_id"] for r in result["ordered"]], ids)

    def test_reason_approval_idempotency(self):
        result = self.app.start("t", "demo-user", "A3003")
        self.assertEqual(result["interrupts"][0]["kind"], "need_reason")
        result = self.app.resume("t", "demo-user", reason="尺寸不合适")
        self.assertEqual(result["interrupts"][0]["kind"], "approval")
        result = self.app.resume("t", "demo-user", action="approve")
        self.assertEqual(result["stage"], "submitted")
        repeated = self.app.resume("t", "demo-user", action="approve")
        self.assertEqual(repeated["result"]["application_id"], result["result"]["application_id"])
        self.assertEqual(self.app.business.application_count(), 1)
        self.assertTrue(self.app.business.submit(result["draft"]["draft_id"], "demo-user")["reused"])

    def test_cancel_and_identity(self):
        self.app.start("t", "demo-user", "A3003", "尺寸不合适")
        with self.assertRaises(PermissionError):
            self.app.resume("t", "other-user", action="approve")
        result = self.app.resume("t", "demo-user", action="cancel")
        self.assertEqual(result["stage"], "cancelled")
        self.assertEqual(self.app.business.application_count(), 0)

    def test_changed_input_and_prepare_replay(self):
        self.app.start("t", "demo-user", "A3003", "尺寸不合适")
        with self.assertRaises(ValueError):
            self.app.start("t", "demo-user", "A3005", "尺寸不合适")
        first = self.app.business.prepare("t", "A3003", "尺寸不合适", "demo-user")
        second = self.app.business.prepare("t", "A3003", "尺寸不合适", "demo-user")
        self.assertEqual(first["draft_id"], second["draft_id"])

    def test_expired_draft(self):
        self.app.start("t", "demo-user", "A3003", "尺寸不合适")
        with closing(sqlite3.connect(self.folder / "business.sqlite")) as db, db:
            data = json.loads(db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()[0])
            for draft in data["drafts"].values():
                draft["expires_at"] = 0
            db.execute("UPDATE snapshot SET body=? WHERE id=1", (json.dumps(data),))
        result = self.app.resume("t", "demo-user", action="approve")
        self.assertEqual(result["stage"], "failed")
        self.assertEqual(result["result"]["error"], "draft_expired")

    def test_real_process_restart(self):
        def run(*args):
            out = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "assistant.py"),
                                  "--data", str(self.folder), *args], check=True,
                                 capture_output=True, text=True, encoding="utf-8")
            return out.stdout
        self.assertIn("approval", run("start", "restart", "A3003", "--reason", "不合适"))
        self.assertIn("submitted", run("resume", "restart", "--action", "approve"))
        self.assertEqual(Business(self.folder / "business.sqlite").application_count(), 1)

    def test_events_with_source(self):
        graph = build_flow(self.app.business, approval=False)
        chunks = list(graph.stream({"task_id": "event", "order_id": "A3003", "reason": "不合适"},
                                   context=RequestContext("demo-user"), stream_mode=["updates", "custom"]))
        custom = [value for mode, value in chunks if mode == "custom"]
        self.assertTrue(custom)
        self.assertTrue(all(c["task_id"] == "event" and c["source"] == "business_flow" for c in custom))

    def test_skills_do_not_grant_permissions(self):
        request = assemble_request("return", "query", {"order_query", "prepare_return", "submit"})
        self.assertEqual(request["tools"], ["order_query"])
        with self.assertRaises(ValueError):
            assemble_request("../../secret", "query", set())

    def test_task_dependencies_claim_race_and_reopen(self):
        path = self.folder / "tasks.sqlite"
        board = TaskBoard(path)
        board.add("check", "核对事实")
        board.add("draft", "准备草稿", ["check"])
        self.assertFalse(board.claim("draft", "bob"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda owner: board.claim("check", owner), ["alice", "bob"]))
        self.assertEqual(sum(claims), 1)
        owner = "alice" if claims[0] else "bob"
        with self.assertRaises(ValueError):
            board.complete("check", owner, None)
        board.complete("check", owner, {"order_id": "A3003", "checked": True})
        self.assertTrue(TaskBoard(path).claim("draft", "bob"))

    def test_memory_scope_output_and_retry(self):
        board = TaskBoard(self.folder / "tasks.sqlite")
        board.remember("alice", "reason", "尺寸不合适", "用户更正消息17")
        self.assertIsNone(board.recall("bob", "reason"))
        self.assertEqual(board.recall("alice", "reason")[0], "尺寸不合适")
        output = persist_output("订单事实" * 1000, self.folder / "output")
        self.assertEqual(Path(output["path"]).read_text(encoding="utf-8"), "订单事实" * 1000)
        attempts, delays = [], []
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise TimeoutError()
            return "ok"
        self.assertEqual(bounded_call(flaky, wait=delays.append), "ok")
        self.assertEqual(delays, [1, 2])

    def test_background_nonblocking_and_cooperative_cancel(self):
        started = Event()
        background = Background()
        try:
            def slow(stop):
                started.set()
                stop.wait(5)
                return {"cooperatively_stopped": stop.is_set()}
            job = background.start(slow)
            self.assertTrue(started.wait(2))
            self.assertEqual(background.get(job)["status"], "running")
            background.cancel(job)
        finally:
            background.close()
        self.assertTrue(background.get(job)["result"]["cooperatively_stopped"])

    def test_schedule_restart_dedup_cancel(self):
        path = self.folder / "schedule.sqlite"
        schedule = Schedule(path)
        schedule.add("daily", 100, interval=60, count=2)
        self.assertEqual(schedule.tick(99), [])
        self.assertEqual(schedule.tick(100), [("daily", 100)])
        reopened = Schedule(path)
        self.assertEqual(reopened.tick(100), [])
        self.assertEqual(reopened.pending(), [("daily", 100)])
        reopened.acknowledge("daily", 100)
        reopened.cancel("daily")
        self.assertEqual(reopened.tick(200), [])

    def test_protocol_type_sender_and_ack(self):
        bus = MessageBus(self.folder / "mail.sqlite")
        protocol = Protocol()
        request = protocol.request("alice", "shutdown", "t")
        bus.send("bob", "lead", "shutdown_response", "t", request, {"approve": True})
        bus.send("alice", "lead", "plan_response", "t", request, {"approve": True})
        bus.send("alice", "lead", "shutdown_response", "t", request, {"approve": True})
        accepted = [protocol.receive(message) for message in bus.inbox("lead")]
        self.assertEqual(accepted, [False, False, True])
        self.assertTrue(protocol.finished())
        for message in bus.inbox("lead"):
            bus.ack(message["id"], "lead")
        self.assertEqual(bus.inbox("lead"), [])

    def test_context_isolation(self):
        self.assertTrue(all(row["input"] == row["observed"] for row in asyncio.run(context_main())))
        with self.assertRaises(LookupError):
            current_user.get()

    def test_policy_evidence_and_no_answer(self):
        result = self.app.policy("会员签收10天能退货吗")
        self.assertEqual(result["status"], "evidence_only")
        self.assertTrue(result["evidence"])
        self.assertEqual(self.app.policy("火星天气")["status"], "insufficient_evidence")

    def test_custom_order_rejected(self):
        result = self.app.start("custom", "demo-user", "A3005", "不合适")
        self.assertEqual(result["stage"], "rejected")
        self.assertEqual(result["result"]["error"], "custom_item_not_supported")

    def test_partial_stream_failure_is_explicit(self):
        from experiments import streaming_demo
        result = streaming_demo(self.folder)
        self.assertEqual(result["fault"][0]["data"]["stage"], "checking")
        self.assertEqual(result["fault"][-1]["data"]["stage"], "failed")

    def test_real_framework_delegation_and_team_cleanup(self):
        from experiments import delegation_demo, team_demo
        delegated = delegation_demo(self.folder)
        self.assertEqual(delegated["baseline"]["calls"], 2)
        self.assertEqual(delegated["delegated"]["calls"], 6)
        experts = [call for call in delegated["delegated"]["inputs"] if len(call["tools"]) == 1]
        self.assertEqual([c["message_count"] for c in experts], [2, 4, 2, 4])
        team = team_demo(self.folder)
        self.assertTrue(team["protocol_finished"])
        self.assertTrue(all(task["status"] == "completed" for task in team["tasks"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
