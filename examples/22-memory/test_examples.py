import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import add_messages
from langgraph.store.memory import InMemoryStore

from conversation_demo import build_agent, two_turns
from manual_demo import FIRST, FOLLOWUP, chat_with_history, probe_reply
from preferences_demo import Viewer, build_preference_agent, set_reply_style
from probe_model import ProbeModel
from state_demo import build_state_agent, save_active_order
from summary_demo import SUMMARY, build_summary_agent


class MemoryTest(unittest.TestCase):
    def test_manual_history_is_explicit_and_separate(self):
        histories = {}
        chat_with_history(histories, "a", FIRST, probe_reply)
        self.assertIn("A1001", chat_with_history(histories, "a", FOLLOWUP, probe_reply))
        self.assertNotIn("A1001", chat_with_history(histories, "b", FOLLOWUP, probe_reply))
        self.assertEqual(len(histories["a"]), 4)
        self.assertEqual(len(histories["b"]), 2)

    def test_model_instance_does_not_restore_history(self):
        model = ProbeModel()
        model.invoke([HumanMessage(FIRST)])
        answer = model.invoke([HumanMessage(FOLLOWUP)])
        self.assertNotIn("A1001", answer.content)
        self.assertEqual(len(model.seen_messages[-1]), 1)

    def test_same_thread_restores_messages_into_actual_model_input(self):
        model = ProbeModel()
        agent = build_agent(model, InMemorySaver())
        result = two_turns(agent, "a")
        self.assertEqual([m.type for m in result["messages"]], ["human", "ai", "human", "ai"])
        self.assertEqual([m.type for m in model.seen_messages[1]], ["system", "human", "ai", "human"])
        self.assertEqual(model.seen_messages[1][1].content, FIRST)
        snapshot = agent.get_state({"configurable": {"thread_id": "a"}})
        self.assertEqual(len(snapshot.values["messages"]), 4)
        self.assertFalse(snapshot.next)

    def test_new_thread_and_new_saver_do_not_inherit_conversation(self):
        saver = InMemorySaver()
        agent = build_agent(ProbeModel(), saver)
        two_turns(agent, "a")
        other = agent.invoke({"messages": [HumanMessage(FOLLOWUP)]},
                             config={"configurable": {"thread_id": "b"}})
        self.assertNotIn("A1001", other["messages"][-1].content)
        restored = build_agent(ProbeModel(), saver).invoke(
            {"messages": [HumanMessage(FOLLOWUP)]}, config={"configurable": {"thread_id": "a"}})
        self.assertIn("A1001", restored["messages"][-1].content)
        fresh = build_agent(ProbeModel(), InMemorySaver()).invoke(
            {"messages": [HumanMessage(FOLLOWUP)]}, config={"configurable": {"thread_id": "a"}})
        self.assertNotIn("A1001", fresh["messages"][-1].content)

    def test_checkpointer_requires_thread_configuration(self):
        agent = build_agent(ProbeModel(), InMemorySaver())
        with self.assertRaises(ValueError):
            agent.invoke({"messages": [HumanMessage(FIRST)]})

    def test_message_merge_uses_ids_including_dictionary_ids(self):
        original = [HumanMessage(FIRST, id="h1"), AIMessage("记录收到", id="a1")]
        same_ids = [{"role": "user", "content": FIRST, "id": "h1"},
                    {"role": "assistant", "content": "记录收到", "id": "a1"}]
        self.assertEqual(len(add_messages(original, same_ids)), 2)
        no_ids = [{"role": "user", "content": FIRST}, {"role": "assistant", "content": "记录收到"}]
        self.assertEqual(len(add_messages(original, no_ids)), 4)

    def test_state_field_needs_explicit_model_injection(self):
        for inject in (False, True):
            with self.subTest(inject=inject):
                model = ProbeModel()
                agent = build_state_agent(model, inject_order=inject)
                config = {"configurable": {"thread_id": "state"}}
                agent.invoke({"messages": [HumanMessage(FIRST)]}, config=config)
                save_active_order(agent, config, "A1001", FIRST)
                result = agent.invoke({"messages": [HumanMessage(FOLLOWUP)]}, config=config)
                state = agent.get_state(config).values
                self.assertEqual(state["active_order_id"], "A1001")
                self.assertEqual(len(state["messages"]), 4)
                self.assertEqual([m.type for m in model.seen_messages[-1]], ["system", "human"])
                self.assertEqual("A1001" in result["messages"][-1].content, inject)

    def test_state_update_rejects_bad_or_unfounded_order(self):
        agent = build_state_agent(ProbeModel())
        config = {"configurable": {"thread_id": "state"}}
        for order, source in (("bad", FIRST), ("A9999", FIRST), ("A1001", "订单A10010")):
            with self.subTest(order=order, source=source), self.assertRaises(ValueError):
                save_active_order(agent, config, order, source)

    def test_preferences_cross_threads_without_carrying_old_order(self):
        store = InMemoryStore()
        set_reply_style(store, "user-a", "简短")
        model = ProbeModel()
        agent = build_preference_agent(model, store)
        agent.invoke({"messages": [HumanMessage(FIRST)]},
                     config={"configurable": {"thread_id": "old"}}, context=Viewer("user-a"))
        fresh = agent.invoke({"messages": [HumanMessage(FOLLOWUP)]},
                             config={"configurable": {"thread_id": "new"}}, context=Viewer("user-a"))
        self.assertNotIn("A1001", fresh["messages"][-1].content)
        self.assertIn("回复偏好：简短", fresh["messages"][-1].content)
        self.assertEqual([m.type for m in model.seen_messages[-1]], ["system", "human"])
        other = agent.invoke({"messages": [HumanMessage(FOLLOWUP)]},
                             config={"configurable": {"thread_id": "other"}}, context=Viewer("user-b"))
        self.assertNotIn("回复偏好：简短", other["messages"][-1].content)

    def test_passing_store_alone_does_not_expose_preferences(self):
        store = InMemoryStore()
        set_reply_style(store, "user-a", "简短")
        agent = build_preference_agent(ProbeModel(), store, inject_preference=False)
        result = agent.invoke({"messages": [HumanMessage(FOLLOWUP)]},
                              config={"configurable": {"thread_id": "a"}}, context=Viewer("user-a"))
        self.assertNotIn("回复偏好", result["messages"][-1].content)
        self.assertIsNone(InMemoryStore().get(("users", "user-a", "preferences"), "reply_style"))

    def test_store_update_and_delete_are_explicit(self):
        store = InMemoryStore()
        set_reply_style(store, "user-a", "简短")
        set_reply_style(store, "user-a", "详细")
        namespace = ("users", "user-a", "preferences")
        self.assertEqual(store.get(namespace, "reply_style").value["value"], "详细")
        store.delete(namespace, "reply_style")
        self.assertIsNone(store.get(namespace, "reply_style"))
        with self.assertRaises(ValueError):
            set_reply_style(store, "user-a", "未经约定的任意提示")

    def test_summary_triggers_and_changes_latest_state(self):
        model, summarizer = ProbeModel(), ProbeModel(fixed_reply=SUMMARY)
        agent = build_summary_agent(model, summarizer)
        config = {"configurable": {"thread_id": "summary"}}
        for text in (FIRST, "谢谢。"):
            agent.invoke({"messages": [HumanMessage(text)]}, config=config)
        self.assertEqual(len(summarizer.seen_messages), 0)
        result = agent.invoke({"messages": [HumanMessage(FOLLOWUP)]}, config=config)
        self.assertEqual(len(summarizer.seen_messages), 1)
        self.assertLess(len(result["messages"]), 6)
        self.assertIn(SUMMARY, result["messages"][0].content)
        self.assertIn(FIRST, str(summarizer.seen_messages[0]))
        self.assertIn("A1001", result["messages"][-1].content)
        # 当前状态被压缩，不代表旧检查点从存储里被抹除。
        history = list(agent.get_state_history(config))
        self.assertTrue(any(any(m.content == FIRST for m in x.values.get("messages", [])) for x in history))

    def test_sqlite_restores_across_two_real_processes(self):
        script = Path(__file__).with_name("persistence_demo.py")
        env = dict(os.environ, PYTHONUTF8="1")
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "checkpoints.sqlite")
            seed = subprocess.run([sys.executable, str(script), "seed", "--db", db],
                                  capture_output=True, text=True, encoding="utf-8", env=env, check=True)
            resume = subprocess.run([sys.executable, str(script), "resume", "--db", db],
                                    capture_output=True, text=True, encoding="utf-8", env=env, check=True)
            self.assertIn("'messages': 2", seed.stdout)
            self.assertIn("'messages': 4", resume.stdout)
            self.assertIn("A1001", resume.stdout)


if __name__ == "__main__":
    unittest.main()
