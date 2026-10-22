import asyncio
import json
import unittest

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from agent_demo import build_agent
from components_demo import get_refund_status
from offline_agent_demo import ScriptedModel


class ExamplesTest(unittest.TestCase):
    def test_prompt_formats_without_a_model(self):
        prompt = ChatPromptTemplate.from_messages([("human", "订单：{order_id}")])
        messages = prompt.invoke({"order_id": "A1001"}).to_messages()
        self.assertEqual(messages[0].content, "订单：A1001")
        with self.assertRaises(KeyError):
            prompt.invoke({})

    def test_schema_and_accessible_order(self):
        self.assertEqual(get_refund_status.args["order_id"]["type"], "string")
        result = json.loads(get_refund_status.invoke({"order_id": "A1001"}))
        self.assertEqual(result, {"ok": True, "order_id": "A1001", "status": "审核中"})

    def test_forbidden_and_missing_orders_hide_status(self):
        for order_id in ("A2002", "A9999"):
            result = json.loads(get_refund_status.invoke({"order_id": order_id}))
            self.assertFalse(result["ok"])
            self.assertNotIn("status", result)
            self.assertEqual(result["error"], "not_found_or_forbidden")

    def test_invalid_arguments_fail_before_a_result(self):
        with self.assertRaises(ValueError):
            get_refund_status.invoke({"order_id": "bad-id"})
        with self.assertRaises(ValidationError):
            get_refund_status.invoke({})
        with self.assertRaises(ValidationError):
            get_refund_status.invoke({"order_id": 1001})

    def test_common_model_execution_interfaces(self):
        model = FakeListChatModel(responses=["固定文本"])
        self.assertEqual(model.invoke("问题").content, "固定文本")
        self.assertEqual([m.content for m in model.batch(["问题1", "问题2"])],
                         ["固定文本", "固定文本"])
        self.assertEqual("".join(chunk.content for chunk in model.stream("问题")),
                         "固定文本")
        self.assertEqual(asyncio.run(model.ainvoke("问题")).content, "固定文本")

    def test_tool_call_produces_paired_message(self):
        result = get_refund_status.invoke({
            "name": "get_refund_status", "args": {"order_id": "A1001"},
            "id": "call_pair", "type": "tool_call",
        })
        self.assertIsInstance(result, ToolMessage)
        self.assertEqual(result.tool_call_id, "call_pair")
        self.assertTrue(json.loads(result.content)["ok"])

    def test_real_agent_loop_with_scripted_model(self):
        model = ScriptedModel()
        result = build_agent(model).invoke({"messages": [HumanMessage("查询A1001")]})
        messages = result["messages"]
        self.assertEqual([m.type for m in messages], ["human", "ai", "tool", "ai"])
        self.assertEqual(messages[1].tool_calls[0]["id"], messages[2].tool_call_id)
        self.assertEqual(model.calls, 2)
        self.assertEqual(json.loads(messages[2].content)["status"], "审核中")

    def test_repeated_requests_hit_the_tool_limit(self):
        model = ScriptedModel(repeat=True)
        with self.assertRaises(Exception) as caught:
            build_agent(model).invoke({"messages": [HumanMessage("不断查询A1001")]})
        self.assertEqual(type(caught.exception).__name__, "ToolCallLimitExceededError")
        self.assertEqual(model.calls, 3)


if __name__ == "__main__":
    unittest.main()
