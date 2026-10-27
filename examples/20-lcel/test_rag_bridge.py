import unittest

from rag_bridge import ask_with_chain


class RecordedRetriever:
    """只固定检索返回值，以便检查跨篇交接；不验证向量召回效果。"""

    def __init__(self, hits):
        self.hits = hits
        self.questions = []

    def retrieve(self, question, top_k, threshold):
        self.questions.append(question)
        return self.hits


class RecordedChain:
    def __init__(self):
        self.inputs = []

    def invoke(self, inputs):
        self.inputs.append(inputs)
        return "用于检查交接的回答"


class BridgeTest(unittest.TestCase):
    def test_question_and_retrieved_text_reach_chain_with_evidence(self):
        question = "定制商品有什么退货限制？"
        retriever = RecordedRetriever([{
            "chunk_id": "custom-rule", "source": "refund-policy.md", "chunk_index": 2,
            "location": "商品例外", "text": "定制商品不支持无理由退货。", "score": 0.8,
        }])
        chain = RecordedChain()
        result = ask_with_chain(retriever, chain, question)
        self.assertEqual(retriever.questions, [question])
        self.assertEqual(chain.inputs[0]["question"], question)
        self.assertIn("定制商品不支持无理由退货。", chain.inputs[0]["context"])
        self.assertIn("[资料1]", chain.inputs[0]["context"])
        self.assertEqual(result["evidence"][0]["chunk_id"], "custom-rule")
        self.assertEqual(result["status"], "generated_pending_verification")

    def test_no_evidence_skips_chain_and_preserves_failure(self):
        chain = RecordedChain()
        result = ask_with_chain(RecordedRetriever([]), chain, "运费谁承担？")
        self.assertEqual(chain.inputs, [])
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["evidence"], [])


if __name__ == "__main__":
    unittest.main()
