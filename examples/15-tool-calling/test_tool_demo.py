import copy
import json
import unittest
from unittest.mock import patch

import tool_demo as demo


def call(call_id="call_1", name="get_refund_status", arguments='{"order_id":"A1001"}'):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": arguments}}


class ToolCallingTests(unittest.TestCase):
    def test_offline_round_trip(self):
        answer, history = demo.run("查询订单A1001退款状态", demo.offline_model)
        self.assertIn("教学数据", answer)
        self.assertIn("审核中", answer)
        self.assertEqual([m["role"] for m in history],
                         ["system", "user", "assistant", "tool", "assistant"])
        self.assertEqual(history[2]["tool_calls"][0]["id"], history[3]["tool_call_id"])

    def test_missing_id_does_not_execute(self):
        with patch.object(demo, "get_refund_status") as query:
            answer, history = demo.run("查退款状态", demo.offline_model)
        query.assert_not_called()
        self.assertIn("请提供订单号", answer)
        self.assertEqual(len(history), 3)

    def test_ownership_and_missing_record(self):
        for order_id in ("A2002", "A9999"):
            with self.subTest(order_id=order_id):
                answer, history = demo.run(f"查询订单{order_id}", demo.offline_model)
                result = json.loads(history[3]["content"])
                self.assertEqual(result, {"ok": False, "error": "not_found_or_forbidden"})
                self.assertNotIn("已退款", answer)

    def test_reject_invalid_arguments_before_query(self):
        inputs = ["{", "null", "[]", "{}", '{"order_id":15}',
                  '{"order_id":"A1001","current_user":"other-user"}',
                  '{"order_id":"A1001;DROP TABLE orders"}', {"order_id": "A1001"}]
        with patch.object(demo, "get_refund_status") as query:
            for arguments in inputs:
                with self.subTest(arguments=arguments):
                    self.assertFalse(demo.execute_tool(call(arguments=arguments), "demo-user")["ok"])
        query.assert_not_called()

    def test_unknown_tool_never_enters_query(self):
        with patch.object(demo, "get_refund_status") as query:
            result = demo.execute_tool(call(name="submit_refund"), "demo-user")
        self.assertEqual(result["error"], "unknown_tool")
        query.assert_not_called()

    def test_multiple_calls_and_failures_are_paired(self):
        snapshots = []
        def model(messages, tool_choice):
            snapshots.append(copy.deepcopy(messages))
            if len(snapshots) == 1:
                return {"role": "assistant", "content": "开始查询", "tool_calls": [
                    call("one"), call("two", arguments="{"), call("three", name="unlisted")]}
            return {"role": "assistant", "content": "部分查询失败，不能确认全部状态。"}
        _, history = demo.run("查询", model)
        self.assertEqual([m["tool_call_id"] for m in history if m["role"] == "tool"],
                         ["one", "two", "three"])
        results = [json.loads(m["content"]) for m in snapshots[1] if m["role"] == "tool"]
        self.assertEqual([r["ok"] for r in results], [True, False, False])

    def test_invalid_batch_rejected_before_any_execution(self):
        batches = [[call("same"), call("same")], [call("valid"), call("")],
                   [call(str(i)) for i in range(5)]]
        for batch in batches:
            with self.subTest(batch=batch), patch.object(demo, "get_refund_status") as query:
                with self.assertRaises(RuntimeError):
                    demo.run("查询", lambda m, c: {"tool_calls": batch})
                query.assert_not_called()

    def test_round_budget_allows_final_answer_without_extra_tool(self):
        choices = []
        def model(messages, tool_choice):
            choices.append(tool_choice)
            if tool_choice == "none":
                return {"role": "assistant", "content": "按已取得的教学结果回答。"}
            return {"tool_calls": [call(f"round_{len(choices)}")]}
        with patch.object(demo, "get_refund_status", wraps=demo.get_refund_status) as query:
            _, history = demo.run("查询", model)
        self.assertEqual(choices, ["auto", "auto", "auto", "none"])
        self.assertEqual(query.call_count, 3)
        self.assertEqual(len([m for m in history if m["role"] == "tool"]), 3)

    def test_disallowed_final_call_and_reused_id_stop(self):
        with patch.object(demo, "get_refund_status") as query:
            with self.assertRaises(RuntimeError):
                demo.run("查询", lambda m, c: {"tool_calls": [call()]}, max_tool_rounds=0)
            query.assert_not_called()
        with patch.object(demo, "get_refund_status", wraps=demo.get_refund_status) as query:
            with self.assertRaises(RuntimeError):
                demo.run("查询", lambda m, c: {"tool_calls": [call()]})
            self.assertEqual(query.call_count, 1)

    def test_live_adapter_request_and_truncation_without_network(self):
        with patch.dict(demo.os.environ, {"DEEPSEEK_API_KEY": "test-placeholder",
                                         "DEEPSEEK_MODEL": "test-model"}), \
                patch.object(demo, "urlopen") as network:
            network.return_value.__enter__.return_value.read.return_value = json.dumps({
                "choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": "测试回答"}}]}).encode()
            self.assertEqual(demo.live_model([{"role": "user", "content": "测试"}], "none")
                             ["content"], "测试回答")
            request = network.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(payload["tool_choice"], "none")
            self.assertFalse(payload["stream"])
            network.return_value.__enter__.return_value.read.return_value = json.dumps({
                "choices": [{"finish_reason": "length", "message": {}}]}).encode()
            with self.assertRaisesRegex(RuntimeError, "未正常完成"):
                demo.live_model([], "auto")


if __name__ == "__main__":
    unittest.main()
