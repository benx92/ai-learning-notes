import asyncio
import unittest
from threading import Barrier

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnableSequence

from chain_demo import (
    DEMO_INPUT, FIXED_REPLY, POLICIES, build_basic_chain, build_inputs,
    build_pipeline, build_preserved_inputs, make_model, make_prompt, normalize,
    stream_observation,
)
from reliability_demo import run_fallback_demo, run_retry_demo
from basic_demo import answer_question, run_stepwise


class ModelCalls(BaseCallbackHandler):
    def __init__(self):
        self.count = 0

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.count += 1


class ChainTest(unittest.TestCase):
    def test_basic_entry_skips_model_for_blank_and_rejects_non_text(self):
        counter = ModelCalls()
        model = FakeListChatModel(responses=[FIXED_REPLY], callbacks=[counter])
        chain = build_basic_chain(model)
        self.assertEqual(answer_question(chain, POLICIES["member"], "  "), "请先填写政策问题。")
        with self.assertRaises(TypeError):
            answer_question(chain, POLICIES["member"], None)
        self.assertEqual(counter.count, 0)
        self.assertEqual(answer_question(chain, POLICIES["member"], "  期限？  "), FIXED_REPLY)
        self.assertEqual(counter.count, 1)

    def test_stepwise_entry_returns_same_plain_text_as_basic_chain(self):
        counter = ModelCalls()
        model = FakeListChatModel(responses=[FIXED_REPLY], callbacks=[counter])
        self.assertEqual(run_stepwise(model, POLICIES["member"], "期限？"), FIXED_REPLY)
        self.assertEqual(counter.count, 1)
        self.assertEqual(build_basic_chain(model).invoke({
            "context": POLICIES["member"], "question": "期限？",
        }), FIXED_REPLY)
        self.assertEqual(counter.count, 2)

    def test_building_a_chain_does_not_call_model(self):
        counter = ModelCalls()
        model = FakeListChatModel(responses=[FIXED_REPLY], callbacks=[counter])
        chain = build_basic_chain(model)
        self.assertIsInstance(chain, RunnableSequence)
        self.assertEqual(counter.count, 0)
        inputs = build_inputs().invoke(DEMO_INPUT)
        self.assertEqual(chain.invoke(inputs), FIXED_REPLY)
        self.assertEqual(counter.count, 1)

    def test_stepwise_types_and_values(self):
        inputs = build_inputs().invoke(DEMO_INPUT)
        prepared = make_prompt().invoke(inputs)
        self.assertEqual(type(prepared).__name__, "ChatPromptValue")
        self.assertEqual(prepared.to_messages()[1].content,
                         f"资料：{POLICIES['member']}\n问题：{DEMO_INPUT['question']}")
        reply = make_model().invoke(prepared)
        self.assertEqual(type(reply).__name__, "AIMessage")
        parsed = StrOutputParser().invoke(reply)
        self.assertIsInstance(parsed, str)
        self.assertEqual(parsed, FIXED_REPLY)

    def test_normalize_checks_and_does_not_mutate_input(self):
        data = {"tier": "member", "question": "  期限？  ", "extra": "keep outside"}
        self.assertEqual(normalize(data), {"tier": "member", "question": "期限？"})
        self.assertEqual(data["question"], "  期限？  ")
        for bad in ({"tier": "unknown", "question": "期限？"},
                    {"tier": "member", "question": None}, "期限？"):
            with self.assertRaises((TypeError, ValueError)):
                normalize(bad)

    def test_parallel_rebuilds_fields_assign_preserves_them(self):
        selected = build_inputs().invoke(DEMO_INPUT)
        preserved = build_preserved_inputs().invoke(DEMO_INPUT)
        self.assertEqual(set(selected), {"context", "question"})
        self.assertEqual(preserved, {**DEMO_INPUT, "context": POLICIES["member"]})
        self.assertNotIn("context", DEMO_INPUT)

    def test_parallel_branches_can_overlap_and_receive_same_input(self):
        barrier = Barrier(2, timeout=5)

        def branch(data):
            barrier.wait()
            return data["question"]

        parallel = RunnableParallel(a=RunnableLambda(branch), b=RunnableLambda(branch))
        result = parallel.invoke(DEMO_INPUT, config={"max_concurrency": 2})
        self.assertEqual(result, {"a": DEMO_INPUT["question"], "b": DEMO_INPUT["question"]})

    def test_empty_question_does_not_call_model(self):
        counter = ModelCalls()
        model = FakeListChatModel(responses=[FIXED_REPLY], callbacks=[counter])
        pipeline = build_pipeline(model)
        self.assertEqual(pipeline.invoke({"tier": "member", "question": "  "}), "请先填写政策问题。")
        self.assertEqual(counter.count, 0)
        self.assertEqual(pipeline.invoke(DEMO_INPUT), FIXED_REPLY)
        self.assertEqual(counter.count, 1)

    def test_batch_preserves_positions_and_returns_exceptions_when_requested(self):
        result = build_pipeline(make_model()).batch(
            [DEMO_INPUT, {"tier": "unknown", "question": "期限？"},
             {"tier": "member", "question": ""}],
            config={"max_concurrency": 2}, return_exceptions=True,
        )
        self.assertEqual(result[0], FIXED_REPLY)
        self.assertIsInstance(result[1], ValueError)
        self.assertEqual(result[2], "请先填写政策问题。")

    def test_async_invocation(self):
        result = asyncio.run(build_pipeline(make_model()).ainvoke(DEMO_INPUT))
        self.assertEqual(result, FIXED_REPLY)

    def test_streaming_buffer_and_incremental_transform(self):
        observed = stream_observation()
        self.assertEqual(observed["direct"], ["a", " ", "b"])
        self.assertEqual(observed["buffered"], ["A B"])
        self.assertEqual(observed["incremental"], ["A", " ", "B"])

    def test_missing_template_field_and_message_type_mismatch(self):
        with self.assertRaises(KeyError):
            make_prompt().invoke({"question": "期限？"})
        with self.assertRaises(AttributeError):
            (make_model() | RunnableLambda(lambda value: value.strip())).invoke("输入")

    def test_retry_counts_total_attempts(self):
        self.assertEqual(run_retry_demo(), {"attempts": 3, "result": "教学查询恢复"})

    def test_fallback_does_not_claim_success(self):
        self.assertEqual(run_fallback_demo(), "暂时无法取得资料，尚未完成政策核对。")


if __name__ == "__main__":
    unittest.main()
