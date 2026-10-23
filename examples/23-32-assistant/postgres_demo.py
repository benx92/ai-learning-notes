"""可选PostgreSQL实验：需自行提供独立练习库DATABASE_URL；不会自动运行。"""
import argparse
import os
import uuid
import psycopg


def record(dsn, request_id, order_id, owner):
    with psycopg.connect(dsn) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tutorial_applications (
                request_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL UNIQUE,
                order_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        # 此表仅演示请求去重，不承担订单资格校验或真实申请提交。
        inserted = connection.execute(
            "INSERT INTO tutorial_applications(request_id,application_id,order_id,owner_id) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT(request_id) DO NOTHING RETURNING application_id",
            (request_id, "tutorial_" + uuid.uuid4().hex, order_id, owner),
        ).fetchone()
        row = connection.execute(
            "SELECT application_id,order_id,owner_id FROM tutorial_applications WHERE request_id=%s",
            (request_id,),
        ).fetchone()
        if row is None or row[1:] != (order_id, owner):
            raise ValueError("请求编号已绑定其他输入或记录不可见")
        return {"application_id": row[0], "reused": inserted is None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("order")
    args = parser.parse_args()
    print(record(os.environ["DATABASE_URL"], args.request, args.order, "demo-user"))
