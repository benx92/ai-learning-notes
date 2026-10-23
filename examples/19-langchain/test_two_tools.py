"""验证两种工具的分发与原有业务访问检查。"""
import unittest
from unittest.mock import patch
import two_tools_demo as demo


class TwoToolsTest(unittest.TestCase):
    def test_dispatch_and_backend_results(self):
        for label, name, expected in [
            ("物流", "get_shipping_status", "新的物流快照"),
            ("退款", "get_refund_status", "已退款"),
        ]:
            with self.subTest(label=label), patch.dict(demo.SHIPPING, {"A1001": "新的物流快照"}), patch.dict(
                demo.ORDERS, {"A1001": {"owner": "demo-user", "status": "已退款"}}
            ):
                question = f"查一下A1001的{label}状态。"
                plain = demo.run_python(demo.scripted_reply, question)
                framework = demo.run_langchain(demo.make_scripted_model(demo.scripted_reply), question)
                self.assertEqual(plain[2]["tool_calls"][0]["name"], name)
                self.assertEqual(framework[1].tool_calls[0]["name"], name)
                self.assertEqual(plain[3]["content"], expected)
                self.assertEqual(framework[2].content, expected)
                self.assertEqual(plain[-1]["content"], framework[-1].content)
                self.assertEqual(framework[1].tool_calls[0]["id"], framework[2].tool_call_id)

    def test_shipping_access_check(self):
        with patch.dict(demo.ORDERS, {"A1001": {"owner": "other-user", "status": "保密"}}):
            plain = demo.run_python(demo.scripted_reply)
            framework = demo.run_langchain(demo.make_scripted_model(demo.scripted_reply))
            self.assertIn("无权查看", plain[-1]["content"])
            self.assertEqual(plain[-1]["content"], framework[-1].content)
            self.assertNotIn(demo.SHIPPING["A1001"], framework[-1].content)
        with self.assertRaises(ValueError):
            demo.get_shipping_status("不是订单号")


if __name__ == "__main__":
    unittest.main()
