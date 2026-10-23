import copy
import unittest
from unittest.mock import Mock, patch

import tool_demo
from two_request_demo import run_two_requests


def tool_call(call_id="call_one"):
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": call_id, "type": "function", "function": {
            "name": "get_refund_status", "arguments": '{"order_id":"A1001"}'}}]}


class TwoRequestChecks(unittest.TestCase):
    def test_second_request_receives_first_request_and_real_result(self):
        inputs = []

        def model(messages, choice):
            inputs.append((copy.deepcopy(messages), choice))
            return tool_demo.offline_model(messages, choice)

        report = run_two_requests("查一下订单A1001的退款状态", model)
        self.assertEqual([choice for _, choice in inputs], ["auto", "none"])
        self.assertEqual([len(messages) for messages, _ in inputs], [2, 4])
        history = inputs[1][0]
        self.assertEqual(history[2]["tool_calls"], report["first_response"]["tool_calls"])
        self.assertEqual(history[3]["tool_call_id"], history[2]["tool_calls"][0]["id"])
        self.assertIn("审核中", history[3]["content"])
        self.assertEqual(report["tool_result"]["refund_status"], "审核中")
        self.assertIn("审核中", report["answer"])
        self.assertEqual(len(report["messages"]), 5)

    def test_plain_first_response_does_not_execute_or_request_twice(self):
        with patch("two_request_demo.execute_tool") as execute:
            model = Mock(side_effect=tool_demo.offline_model)
            report = run_two_requests("查一下退款状态", model)
        execute.assert_not_called()
        self.assertEqual(model.call_count, 1)
        self.assertIsNone(report["tool_result"])
        self.assertIsNone(report["second_response"])
        self.assertIn("请提供订单号", report["answer"])

    def test_forbidden_result_is_returned_to_second_call(self):
        report = run_two_requests("查一下订单A2002的退款状态", tool_demo.offline_model)
        self.assertFalse(report["tool_result"]["ok"])
        self.assertIn("not_found_or_forbidden", report["answer"])
        self.assertNotIn("已退款", report["answer"])

    def test_invalid_or_multiple_calls_stop_before_execution(self):
        bad_id = tool_call("")
        multiple = tool_call()
        multiple["tool_calls"].append(tool_call("call_two")["tool_calls"][0])
        for first in (bad_id, multiple):
            with self.subTest(first=first):
                with patch("two_request_demo.execute_tool") as execute:
                    with self.assertRaises(RuntimeError):
                        run_two_requests("查一下A1001", lambda *_: first)
                execute.assert_not_called()

    def test_repeated_tool_request_in_second_response_never_executes(self):
        responses = iter([tool_call(), tool_call("second_call")])
        with patch("two_request_demo.execute_tool", wraps=tool_demo.execute_tool) as execute:
            with self.assertRaises(RuntimeError):
                run_two_requests("查一下A1001", lambda *_: next(responses))
        self.assertEqual(execute.call_count, 1)

    def test_invalid_arguments_use_existing_executor_and_fail_explicitly(self):
        first = tool_call()
        first["tool_calls"][0]["function"]["arguments"] = "{"
        count = 0

        def model(messages, _):
            nonlocal count
            count += 1
            return first if count == 1 else tool_demo.offline_model(messages, "none")

        with patch.object(tool_demo, "get_refund_status") as query:
            report = run_two_requests("查一下A1001", model)
        query.assert_not_called()
        self.assertEqual(report["tool_result"]["error"], "invalid_json")
        self.assertIn("invalid_json", report["answer"])


if __name__ == "__main__":
    unittest.main()
