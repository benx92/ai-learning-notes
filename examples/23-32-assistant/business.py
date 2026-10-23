"""持久化教学业务：复用15篇ReturnService，事务保存其虚构记录。"""
from contextlib import closing
import copy
import importlib.util
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("return_business", ROOT / "15-tool-calling/return_demo.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


class Business:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS requests (task TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL)")

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
            service = legacy.ReturnService()
            memo = {}
            if row:
                data = json.loads(row[0])
                service.orders = data["orders"]
                service.drafts = data["drafts"]
                service.applications = data["applications"]
                memo = data["prepared"]
                for draft in service.drafts.values():
                    draft["expires"] = time.monotonic() + draft.pop("expires_at") - time.time()
            yield service, memo
            drafts = copy.deepcopy(service.drafts)
            for draft in drafts.values():
                draft["expires_at"] = time.time() + draft.pop("expires") - time.monotonic()
            data = dict(orders=service.orders, drafts=drafts,
                        applications=service.applications, prepared=memo)
            db.execute("INSERT INTO snapshot VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                       (json.dumps(data, ensure_ascii=False),))

    def register(self, task, user, payload=None):
        if not task or not user:
            raise ValueError("task和user不能为空")
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner,payload FROM requests WHERE task=?", (task,)).fetchone()
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if row:
                if row[0] != user:
                    raise PermissionError("任务不存在或无权访问")
                if payload is not None and row[1] != encoded:
                    raise ValueError("相同任务编号不能替换输入；请使用新编号")
                return False
            if payload is None:
                raise PermissionError("任务不存在或无权访问")
            db.execute("INSERT INTO requests VALUES(?,?,?)", (task, user, encoded))
            return True

    def order(self, order_id, user):
        with self.transaction() as (service, _):
            order = service.orders.get(order_id)
            if not order or order["owner"] != user:
                return {"ok": False, "error": "not_found_or_forbidden"}
            return {"ok": True, "order_id": order_id, **copy.deepcopy(order)}

    def check(self, order_id, user):
        with self.transaction() as (service, _):
            error = service._check(order_id, user)
            return {"ok": error is None, "error": error}

    def prepare(self, task, order_id, reason, user):
        with self.transaction() as (service, memo):
            if task in memo:
                draft_id = memo[task]
                draft = service.drafts[draft_id]
                if (draft["user"], draft["order_id"], draft["reason"]) != (user, order_id, reason.strip()):
                    raise ValueError("准备请求与已有草稿不一致")
                return {"ok": True, "draft_id": draft_id, "order_id": order_id,
                        "reason": draft["reason"], "status": "awaiting_confirmation", "reused": True}
            result = service.prepare(order_id, reason, user)
            if result["ok"]:
                memo[task] = result["draft_id"]
            return result

    def submit(self, draft_id, user):
        """只供可信审批入口后的节点调用，不暴露为模型可随意调用的工具。"""
        with self.transaction() as (service, _):
            # 已成功的同一动作重复到达时，先返回既有业务记录。
            if draft_id in service.applications:
                draft = service.drafts.get(draft_id)
                if not draft or draft["user"] != user:
                    return {"ok": False, "error": "invalid_draft"}
                return {"ok": True, "reused": True, **copy.deepcopy(service.applications[draft_id])}
            confirmed = service.confirm_from_ui(draft_id, user)
            if not confirmed["ok"]:
                return confirmed
            return service.submit(draft_id, user)

    def application_count(self):
        with self.transaction() as (service, _):
            return len(service.applications)
