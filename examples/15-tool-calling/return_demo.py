"""退货申请的本地教学演示：只在当前进程中创建记录，不连接真实业务。"""

import copy
import json
import sys
import time
import uuid
from threading import Lock


class ReturnService:
    def __init__(self):
        self.orders = {
            "A3003": {"owner": "demo-user", "member": True, "days": 10,
                      "custom": False, "applied": False},
            "A3004": {"owner": "demo-user", "member": False, "days": 10,
                      "custom": False, "applied": False},
            "A3005": {"owner": "demo-user", "member": True, "days": 3,
                      "custom": True, "applied": False},
        }
        self.drafts = {}
        self.applications = {}
        self.lock = Lock()

    def _check(self, order_id, user):
        order = self.orders.get(order_id)
        if order is None or order["owner"] != user:
            return "not_found_or_forbidden"
        if order["applied"]:
            return "already_applied"
        if order["custom"]:
            return "custom_item_not_supported"
        limit = 15 if order["member"] else 7
        if order["days"] > limit:
            return "outside_application_window"
        return None

    def prepare(self, order_id, reason, user):
        if (not isinstance(order_id, str) or not isinstance(reason, str)
                or not reason.strip() or len(reason) > 200):
            return {"ok": False, "error": "invalid_arguments"}
        with self.lock:
            error = self._check(order_id, user)
            if error:
                return {"ok": False, "error": error}
            draft_id = "draft_" + uuid.uuid4().hex
            self.drafts[draft_id] = {
                "user": user, "order_id": order_id, "reason": reason.strip(),
                "confirmed": False, "expires": time.monotonic() + 300,
            }
            return {"ok": True, "status": "awaiting_confirmation",
                    "draft_id": draft_id, "order_id": order_id,
                    "reason": reason.strip(), "operation": "创建退货申请，等待审核"}

    def confirm_from_ui(self, draft_id, user):
        """仅由展示该草稿的确认界面调用；不作为模型工具暴露。"""
        with self.lock:
            draft = self.drafts.get(draft_id)
            if draft is None or draft["user"] != user:
                return {"ok": False, "error": "invalid_draft"}
            if time.monotonic() >= draft["expires"]:
                return {"ok": False, "error": "draft_expired"}
            draft["confirmed"] = True
            return {"ok": True, "status": "confirmed"}

    def submit(self, draft_id, user):
        with self.lock:
            draft = self.drafts.get(draft_id)
            if draft is None or draft["user"] != user:
                return {"ok": False, "error": "invalid_draft"}
            if not draft["confirmed"]:
                return {"ok": False, "error": "confirmation_required"}
            if draft_id in self.applications:
                return {"ok": True, "reused": True,
                        **copy.deepcopy(self.applications[draft_id])}
            if time.monotonic() >= draft["expires"]:
                return {"ok": False, "error": "draft_expired"}
            error = self._check(draft["order_id"], user)
            if error:
                return {"ok": False, "error": error}
            record = {"application_id": "return_" + uuid.uuid4().hex,
                      "order_id": draft["order_id"], "reason": draft["reason"],
                      "status": "submitted", "review_status": "pending",
                      "source": "本地进程中的虚构申请记录"}
            self.applications[draft_id] = record
            self.orders[draft["order_id"]]["applied"] = True
            return {"ok": True, "reused": False, **copy.deepcopy(record)}


def execute_return_tool(service, name, arguments, current_user):
    try:
        args = json.loads(arguments)
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": "invalid_json"}
    if not isinstance(args, dict):
        return {"ok": False, "error": "invalid_arguments"}
    if name == "prepare_return_application" and set(args) == {"order_id", "reason"}:
        return service.prepare(args["order_id"], args["reason"], current_user)
    if name == "submit_return_application" and set(args) == {"draft_id"}:
        if not isinstance(args["draft_id"], str):
            return {"ok": False, "error": "invalid_arguments"}
        return service.submit(args["draft_id"], current_user)
    return {"ok": False, "error": "unknown_tool_or_invalid_arguments"}


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    service = ReturnService()
    user = "demo-user"
    draft = execute_return_tool(service, "prepare_return_application",
                                '{"order_id":"A3003","reason":"尺寸不合适"}', user)
    print("申请草稿：", json.dumps(draft, ensure_ascii=False))
    draft_id = draft["draft_id"]
    arguments = json.dumps({"draft_id": draft_id})
    print("确认前提交：", execute_return_tool(service, "submit_return_application", arguments, user))
    if input("输入“确认提交”创建上述本地教学申请，其他输入取消：").strip() != "确认提交":
        print("已取消，未创建申请。")
        raise SystemExit(0)
    service.confirm_from_ui(draft_id, user)
    first = execute_return_tool(service, "submit_return_application", arguments, user)
    retry = execute_return_tool(service, "submit_return_application", arguments, user)
    print("首次提交：", json.dumps(first, ensure_ascii=False))
    print("重复提交：", json.dumps(retry, ensure_ascii=False))
    print("本地申请记录数量：", len(service.applications))
