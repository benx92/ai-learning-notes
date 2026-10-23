"""27—29：按需说明、持久任务、预算与后台调度的独立机制实验。"""
from contextlib import closing
import hashlib
import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event


SKILLS = {
    "policy": {"description": "解释政策并保留条件与来源", "file": "policy.md", "tools": {"policy_search"}},
    "return": {"description": "核对订单并准备申请", "file": "return.md", "tools": {"order_query", "prepare_return"}},
}


def assemble_request(skill_name, stage, allowed, facts=None):
    if skill_name not in SKILLS:
        raise ValueError("未知说明名称")
    entry = SKILLS[skill_name]
    body = (Path(__file__).parent / "skills" / entry["file"]).read_text(encoding="utf-8")
    stage_tools = {"policy_search", "order_query"} if stage == "query" else {"order_query", "prepare_return"}
    tools = sorted(entry["tools"] & set(allowed) & stage_tools)
    return {"stable": "只依据可核对事实回答；提交由独立确认入口处理。",
            "catalog": [{"name": k, "description": v["description"]} for k, v in SKILLS.items()],
            "instruction": body, "facts": facts or {}, "tools": tools}


class TaskBoard:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, subject TEXT NOT NULL, deps TEXT NOT NULL,
                    status TEXT NOT NULL, owner TEXT, evidence TEXT);
                CREATE TABLE IF NOT EXISTS memories (
                    owner TEXT, key TEXT, value TEXT, source TEXT,
                    PRIMARY KEY(owner,key));
            """)

    def add(self, task, subject, deps=()):
        with closing(sqlite3.connect(self.path)) as db, db:
            if any(not db.execute("SELECT 1 FROM tasks WHERE id=?", (d,)).fetchone() for d in deps):
                raise ValueError("依赖必须先创建；新任务只能依赖已有任务")
            db.execute("INSERT INTO tasks VALUES(?,?,?,'pending',NULL,NULL)", (task, subject, json.dumps(list(deps))))

    def claim(self, task, owner):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT deps FROM tasks WHERE id=? AND status='pending'", (task,)).fetchone()
            if not row:
                return False
            for dep in json.loads(row[0]):
                if db.execute("SELECT status FROM tasks WHERE id=?", (dep,)).fetchone() != ("completed",):
                    return False
            return db.execute("UPDATE tasks SET status='in_progress',owner=? WHERE id=? AND status='pending'",
                              (owner, task)).rowcount == 1

    def complete(self, task, owner, evidence):
        if not evidence:
            raise ValueError("缺少可核对的完成证据")
        with closing(sqlite3.connect(self.path)) as db, db:
            count = db.execute("UPDATE tasks SET status='completed',evidence=? WHERE id=? AND owner=? AND status='in_progress'",
                               (json.dumps(evidence, ensure_ascii=False), task, owner)).rowcount
            if count != 1:
                raise ValueError("任务未认领、已完成或负责人不匹配")

    def fail(self, task, owner, error):
        with closing(sqlite3.connect(self.path)) as db, db:
            count = db.execute("UPDATE tasks SET status='failed',evidence=? WHERE id=? AND owner=? AND status='in_progress'",
                               (json.dumps({"error": str(error)}), task, owner)).rowcount
            if count != 1:
                raise ValueError("不能更新不属于当前执行者的任务")

    def list(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY id")]

    def remember(self, owner, key, value, source):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO memories VALUES(?,?,?,?) ON CONFLICT(owner,key) DO UPDATE SET value=excluded.value,source=excluded.source",
                       (owner, key, value, source))

    def recall(self, owner, key):
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("SELECT value,source FROM memories WHERE owner=? AND key=?", (owner, key)).fetchone()


def persist_output(text, folder, preview_chars=120):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(text.encode()).hexdigest()
    path = folder / (digest + ".txt")
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "sha256": digest, "chars": len(text), "preview": text[:preview_chars]}


def bounded_call(call, *, attempts=3, wait=lambda seconds: None):
    """仅重试TimeoutError；真实SDK错误应在适配层归类，等待函数由调用方提供。"""
    if attempts < 1:
        raise ValueError("attempts必须大于0")
    for number in range(attempts):
        try:
            return call()
        except TimeoutError:
            if number == attempts - 1:
                raise
            wait(min(2 ** number, 8))


class Background:
    def __init__(self, workers=2):
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.jobs = {}

    def start(self, function):
        job_id = uuid.uuid4().hex
        stop = Event()
        self.jobs[job_id] = (self.pool.submit(function, stop), stop)
        return job_id

    def cancel(self, job_id):
        future, stop = self.jobs[job_id]
        stop.set()
        return {"requested": True, "cancelled_before_start": future.cancel()}

    def get(self, job_id):
        future, _ = self.jobs[job_id]
        if future.cancelled():
            return {"status": "cancelled"}
        if not future.done():
            return {"status": "running"}
        try:
            return {"status": "completed", "result": future.result()}
        except Exception as exc:
            return {"status": "failed", "error": type(exc).__name__}

    def close(self):
        for future, stop in self.jobs.values():
            stop.set()
            future.cancel()
        self.pool.shutdown(wait=True, cancel_futures=True)


class Schedule:
    """可控时钟的持久调度账本。interval为秒数，不实现cron表达式。"""
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, due REAL, interval REAL, remaining INTEGER, active INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS occurrences(job TEXT, due REAL, status TEXT, PRIMARY KEY(job,due))")

    def add(self, job, due, interval=0, count=1):
        if count < 1 or interval < 0 or (count > 1 and interval == 0):
            raise ValueError("周期和次数不合法")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO schedules VALUES(?,?,?,?,1)", (job, due, interval, count))

    def tick(self, now):
        emitted = []
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for job, due, interval, remaining in db.execute("SELECT id,due,interval,remaining FROM schedules WHERE active=1 AND due<=?", (now,)).fetchall():
                # 每次tick最多补发每个计划的一次；离线积压策略在正文解释。
                db.execute("INSERT INTO occurrences VALUES(?,?,'queued')", (job, due))
                db.execute("UPDATE schedules SET due=?,remaining=?,active=? WHERE id=?",
                           (due + interval, remaining - 1, int(remaining > 1), job))
                emitted.append((job, due))
        return emitted

    def pending(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("SELECT job,due FROM occurrences WHERE status='queued' ORDER BY due").fetchall()

    def acknowledge(self, job, due):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE occurrences SET status='done' WHERE job=? AND due=?", (job, due))

    def cancel(self, job):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE schedules SET active=0 WHERE id=?", (job,))
            db.execute("UPDATE occurrences SET status='cancelled' WHERE job=? AND status='queued'", (job,))
