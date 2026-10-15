"""本地售后 MCP 教学服务：提供虚构查询、政策资料和回复模板。"""

import argparse
import json
import re

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("after-sales-demo", host="127.0.0.1", port=8765, json_response=True)

POLICIES = {
    "member": "教学政策：会员订单签收后15日内可以申请退货，定制商品不支持无理由退货。",
    "ordinary": "教学政策：普通订单签收后7日内可以申请退货，定制商品不支持无理由退货。",
}
ORDERS = {"A1001": {"owner": "demo-user", "refund_status": "审核中"},
          "A2002": {"owner": "other-user", "refund_status": "已退款"}}


@mcp.tool()
def get_refund_status(order_id: str) -> str:
    """按用户提供的订单号查询教学退款状态，只读；不创建申请或执行退款。"""
    if not re.fullmatch(r"A[0-9]{4}", order_id):
        raise ValueError("订单号应为A加4位数字，如A1001")
    order = ORDERS.get(order_id)
    # 固定身份仅用于本机教学，真实服务应从认证信息取得当前用户。
    if order is None or order["owner"] != "demo-user":
        return json.dumps({"ok": False, "error": "not_found_or_forbidden"})
    return json.dumps({"ok": True, "order_id": order_id,
                       "refund_status": order["refund_status"],
                       "source": "虚构教学快照，不是实时订单"}, ensure_ascii=False)


@mcp.resource("policy://refund/overview", mime_type="text/plain")
def refund_overview() -> str:
    """退货政策概览，只提供教学资料。"""
    return "\n".join(POLICIES.values())


@mcp.resource("policy://refund/customer/{customer_type}", mime_type="text/plain")
def refund_policy(customer_type: str) -> str:
    """按客户类型读取教学条款：member或ordinary。"""
    if customer_type not in POLICIES:
        raise ValueError("客户类型只能是member或ordinary")
    return POLICIES[customer_type]


@mcp.prompt()
def explain_refund(order_id: str) -> str:
    """生成售后回复的任务模板；不查询订单，也不生成最终回答。"""
    return (f"请解释订单{order_id}的售后情况。先读取适用政策并查询退款状态，"
            "根据取得的事实回答。注明教学数据；资料不足就说明缺少什么，"
            "不要把申请提交、审核通过和退款完成混为一谈。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    args = parser.parse_args()
    mcp.run(transport=args.transport)
