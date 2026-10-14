import json
import unittest
from unittest.mock import patch

from return_demo import ReturnService, execute_return_tool


class ReturnApplicationTests(unittest.TestCase):
    def setUp(self):
        self.service = ReturnService()
        self.user = "demo-user"

    def draft(self, order_id="A3003"):
        return self.service.prepare(order_id, "尺寸不合适", self.user)["draft_id"]

    def test_confirmation_required_before_record_is_created(self):
        draft = self.draft()
        self.assertEqual(self.service.submit(draft, self.user)["error"], "confirmation_required")
        self.assertEqual(len(self.service.applications), 0)

    def test_model_cannot_confirm_or_inject_confirmation(self):
        draft = self.draft()
        for name, args in [
            ("confirm_from_ui", {"draft_id": draft}),
            ("submit_return_application", {"draft_id": draft, "confirmed": True}),
            ("submit_return_application", {"draft_id": draft, "current_user": self.user}),
        ]:
            with self.subTest(name=name, args=args):
                result = execute_return_tool(self.service, name, json.dumps(args), self.user)
                self.assertFalse(result["ok"])
        self.assertFalse(self.service.drafts[draft]["confirmed"])
        self.assertEqual(len(self.service.applications), 0)

    def test_other_user_cannot_confirm_or_submit(self):
        draft = self.draft()
        self.assertFalse(self.service.confirm_from_ui(draft, "other-user")["ok"])
        self.service.confirm_from_ui(draft, self.user)
        self.assertFalse(self.service.submit(draft, "other-user")["ok"])
        self.assertEqual(len(self.service.applications), 0)

    def test_rules_are_checked_before_prepare(self):
        for order_id, error in [("A3004", "outside_application_window"),
                                ("A3005", "custom_item_not_supported"),
                                ("A9999", "not_found_or_forbidden")]:
            with self.subTest(order_id=order_id):
                self.assertEqual(self.service.prepare(order_id, "不合适", self.user)["error"], error)
        self.assertEqual(len(self.service.drafts), 0)

    def test_expiry_at_confirmation_and_submission(self):
        with patch("return_demo.time.monotonic", return_value=100):
            draft = self.draft()
        with patch("return_demo.time.monotonic", return_value=400):
            self.assertEqual(self.service.confirm_from_ui(draft, self.user)["error"], "draft_expired")
        with patch("return_demo.time.monotonic", return_value=200):
            self.service.confirm_from_ui(draft, self.user)
        with patch("return_demo.time.monotonic", return_value=400):
            self.assertEqual(self.service.submit(draft, self.user)["error"], "draft_expired")
        self.assertEqual(len(self.service.applications), 0)

    def test_submission_rechecks_changed_conditions(self):
        draft = self.draft()
        self.service.confirm_from_ui(draft, self.user)
        self.service.orders["A3003"]["custom"] = True
        self.assertEqual(self.service.submit(draft, self.user)["error"], "custom_item_not_supported")
        self.assertEqual(len(self.service.applications), 0)

    def test_retries_keep_one_application_and_unchanged_saved_result(self):
        draft = self.draft()
        self.service.confirm_from_ui(draft, self.user)
        first = self.service.submit(draft, self.user)
        first["reason"] = "尝试修改返回结果"
        retry = self.service.submit(draft, self.user)
        self.assertEqual(first["application_id"], retry["application_id"])
        self.assertTrue(retry["reused"])
        self.assertEqual(retry["reason"], "尺寸不合适")
        self.assertEqual(retry["review_status"], "pending")
        self.assertEqual(len(self.service.applications), 1)

    def test_two_confirmed_drafts_cannot_create_duplicate_applications(self):
        first, second = self.draft(), self.draft()
        for draft in (first, second):
            self.service.confirm_from_ui(draft, self.user)
        self.assertTrue(self.service.submit(first, self.user)["ok"])
        self.assertEqual(self.service.submit(second, self.user)["error"], "already_applied")
        self.assertEqual(len(self.service.applications), 1)


if __name__ == "__main__":
    unittest.main()
