"""检查两种执行方式都实际使用相同业务结果并配对工具消息。"""

import unittest
from unittest.mock import patch

import comparison_demo as demo


class ComparisonTest(unittest.TestCase):
    def test_both_paths_use_current_backend_result(self):
        for status in ("审核中", "已退款"):
            with self.subTest(status=status), patch.dict(
                demo.ORDERS, {"A1001": {"owner": "demo-user", "status": status}}
            ):
                plain = demo.run_python(demo.scripted_reply)
                framework = demo.run_langchain(demo.make_scripted_model())
                self.assertEqual([m["role"] for m in plain[1:]],
                                 ["user", "assistant", "tool", "assistant"])
                self.assertEqual([m.type for m in framework], ["human", "ai", "tool", "ai"])
                self.assertEqual(plain[3]["content"], status)
                self.assertEqual(framework[2].content, status)
                self.assertEqual(plain[-1]["content"], framework[-1].content)
                self.assertEqual(plain[2]["tool_calls"][0]["id"], plain[3]["tool_call_id"])
                self.assertEqual(framework[1].tool_calls[0]["id"], framework[2].tool_call_id)

    def test_both_paths_preserve_business_access_check(self):
        with patch.dict(demo.ORDERS, {"A1001": {"owner": "other-user", "status": "秘密状态"}}):
            plain = demo.run_python(demo.scripted_reply)
            framework = demo.run_langchain(demo.make_scripted_model())
            self.assertEqual(plain[-1]["content"], framework[-1].content)
            self.assertNotIn("秘密状态", framework[-1].content)
            self.assertIn("无权查看", framework[-1].content)


if __name__ == "__main__":
    unittest.main()
