import json
import unittest

from langchain_core.messages import AIMessage
from pydantic import ValidationError

from agent_demo import build_agent
from extract_demo import build_chain, extract_with_retry
from fixtures import DEMO_TEXT, GOOD_ARGS, NO_ORDER_TEXT, ScriptedModel, tool_reply
from schemas import (
    EvidenceMismatch,
    OmittableNullable,
    RequiredNullable,
    Ticket,
    check_order_evidence,
    prepare_draft,
)
from validation_demo import parse_ticket


class StructuredOutputTest(unittest.TestCase):
    def test_json_syntax_and_schema_are_different_checks(self):
        with self.assertRaises(json.JSONDecodeError):
            parse_ticket("这不是JSON")
        for value in ({"category": "退款进度"}, {**GOOD_ARGS, "urgency": "非常急"},
                      {**GOOD_ARGS, "summary": "x" * 61},
                      {**GOOD_ARGS, "refund_status": "已到账"}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_ticket(json.dumps(value))

    def test_nullable_and_omittable_are_independent(self):
        with self.assertRaises(ValidationError):
            RequiredNullable.model_validate({})
        self.assertIsNone(RequiredNullable.model_validate({"order_id": None}).order_id)
        self.assertIsNone(OmittableNullable.model_validate({}).order_id)
        self.assertEqual(RequiredNullable.model_json_schema()["required"], ["order_id"])

    def test_unknown_order_id_is_not_a_placeholder_string(self):
        for bad in ("null", "", "未知", 1001):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                Ticket.model_validate({**GOOD_ARGS, "order_id": bad})
        self.assertIsNone(Ticket.model_validate({**GOOD_ARGS, "order_id": None}).order_id)

    def test_chain_binds_schema_without_calling_model(self):
        model = ScriptedModel(responses=[tool_reply(GOOD_ARGS)])
        chain = build_chain(model)
        self.assertEqual(model.calls, 0)
        packet = chain.invoke({"text": DEMO_TEXT, "validation_hint": ""})
        self.assertIsInstance(packet["parsed"], Ticket)
        spec = model.seen_tools[0]["function"]["parameters"]
        self.assertFalse(spec["additionalProperties"])
        self.assertIn("category", spec["required"])
        self.assertEqual(spec["properties"]["urgency"]["enum"], ["普通", "着急"])
        self.assertEqual(model.calls, 1)

    def test_include_raw_retains_invalid_reply(self):
        model = ScriptedModel(responses=[tool_reply({**GOOD_ARGS, "urgency": "非常急"})])
        packet = extract_with_retry(model, DEMO_TEXT, max_attempts=1)
        self.assertIsNone(packet["parsed"])
        self.assertIsInstance(packet["parsing_error"], ValidationError)
        self.assertEqual(packet["raw"].tool_calls[0]["args"]["urgency"], "非常急")
        self.assertEqual(prepare_draft(packet, DEMO_TEXT)["state"], "needs_review")

    def test_broken_tool_json_is_not_a_draft(self):
        reply = AIMessage(content="", additional_kwargs={"tool_calls": [{
            "id": "broken", "type": "function",
            "function": {"name": "Ticket", "arguments": '{"category":'},
        }]})
        model = ScriptedModel(responses=[reply])
        packet = extract_with_retry(model, DEMO_TEXT, max_attempts=1)
        self.assertIsNotNone(packet["parsing_error"])
        self.assertIsNone(packet["parsed"])
        self.assertIsNone(prepare_draft(packet, DEMO_TEXT)["draft"])

    def test_plain_text_without_tool_call_is_not_success(self):
        model = ScriptedModel(responses=[AIMessage(content="用户想查询退款")])
        packet = extract_with_retry(model, DEMO_TEXT, max_attempts=1)
        self.assertIsNone(packet["parsed"])
        self.assertIsNone(packet["parsing_error"])
        self.assertEqual(prepare_draft(packet, DEMO_TEXT)["reason"], "invalid_structure")

    def test_missing_order_produces_followup_instead_of_invention(self):
        model = ScriptedModel(responses=[tool_reply({**GOOD_ARGS, "order_id": None})])
        packet = extract_with_retry(model, NO_ORDER_TEXT)
        draft = prepare_draft(packet, NO_ORDER_TEXT)
        self.assertEqual(draft["state"], "ready")
        self.assertEqual(draft["next_step"], "请用户补充订单号")
        self.assertIsNone(draft["draft"]["order_id"])

    def test_format_valid_order_still_requires_source_check(self):
        ticket = Ticket.model_validate({**GOOD_ARGS, "order_id": "A9999"})
        with self.assertRaises(EvidenceMismatch):
            check_order_evidence(ticket, DEMO_TEXT)
        packet = {"parsed": ticket, "parsing_error": None}
        self.assertEqual(prepare_draft(packet, DEMO_TEXT)["reason"], "order_not_in_source")
        with self.assertRaises(EvidenceMismatch):
            check_order_evidence(Ticket.model_validate(GOOD_ARGS), "订单A10010")

    def test_retry_is_bounded_and_starts_with_fresh_messages(self):
        model = ScriptedModel(responses=[
            tool_reply({**GOOD_ARGS, "urgency": "非常急"}), tool_reply(GOOD_ARGS),
        ])
        packet = extract_with_retry(model, DEMO_TEXT)
        self.assertEqual(packet["attempts"], 2)
        self.assertEqual(model.calls, 2)
        self.assertEqual([m.type for m in model.seen_messages[1]], ["system", "human"])
        self.assertIn("上次未得到有效工单", model.seen_messages[1][0].content)
        self.assertEqual(prepare_draft(packet, DEMO_TEXT)["state"], "ready")

    def test_retry_exhaustion_keeps_failure_visible(self):
        bad = tool_reply({**GOOD_ARGS, "urgency": "非常急"})
        model = ScriptedModel(responses=[bad, bad])
        packet = extract_with_retry(model, DEMO_TEXT)
        self.assertEqual(model.calls, 2)
        self.assertEqual(packet["attempts"], 2)
        self.assertIsNone(prepare_draft(packet, DEMO_TEXT)["draft"])

    def test_model_execution_error_is_not_hidden_as_parsing_error(self):
        model = ScriptedModel(responses=[])
        with self.assertRaisesRegex(RuntimeError, "固定响应已耗尽"):
            extract_with_retry(model, DEMO_TEXT)

    def test_agent_has_a_separate_structured_response_field(self):
        model = ScriptedModel(responses=[tool_reply(GOOD_ARGS)])
        result = build_agent(model).invoke({"messages": [{"role": "user", "content": DEMO_TEXT}]})
        self.assertEqual(result["structured_response"].model_dump(), GOOD_ARGS)
        self.assertEqual([m.type for m in result["messages"]], ["human", "ai", "tool"])
        self.assertEqual(result["messages"][1].tool_calls[0]["id"], result["messages"][2].tool_call_id)

    def test_dictionary_schema_requires_own_runtime_validation(self):
        model = ScriptedModel(responses=[tool_reply({**GOOD_ARGS, "urgency": "非常急"})])
        extractor = model.with_structured_output(Ticket.model_json_schema())
        data = extractor.invoke(DEMO_TEXT)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["urgency"], "非常急")
        with self.assertRaises(ValidationError):
            Ticket.model_validate(data)


if __name__ == "__main__":
    unittest.main()
