"""31：持久消息、类型关联、原子认领与团队结束的协议实验。"""
from contextlib import closing
import json
import sqlite3
import uuid


class MessageBus:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS mail(id TEXT PRIMARY KEY,sender TEXT,recipient TEXT,kind TEXT,task TEXT,request TEXT,payload TEXT,acked INTEGER DEFAULT 0)")

    def send(self, sender, recipient, kind, task, request, payload):
        message_id = uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO mail VALUES(?,?,?,?,?,?,?,0)",
                       (message_id, sender, recipient, kind, task, request, json.dumps(payload)))
        return message_id

    def inbox(self, recipient):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM mail WHERE recipient=? AND acked=0 ORDER BY rowid", (recipient,))]

    def ack(self, message_id, recipient):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE mail SET acked=1 WHERE id=? AND recipient=?", (message_id, recipient))


class Protocol:
    def __init__(self):
        self.pending = {}

    def request(self, worker, kind, task):
        request_id = uuid.uuid4().hex
        self.pending[request_id] = {"worker": worker, "kind": kind, "task": task, "status": "pending"}
        return request_id

    def receive(self, message):
        pending = self.pending.get(message["request"])
        if not pending or pending["status"] != "pending":
            return False
        if (message["sender"] != pending["worker"] or message["recipient"] != "lead"
                or message["task"] != pending["task"] or message["kind"] != pending["kind"] + "_response"):
            return False
        pending["status"] = "approved" if json.loads(message["payload"]).get("approve") is True else "rejected"
        return True

    def finished(self):
        return all(item["status"] != "pending" for item in self.pending.values())
