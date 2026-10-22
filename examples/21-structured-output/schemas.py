"""工单草稿的数据约束与一个有限的来源核对。"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Ticket(BaseModel):
    """从用户原话整理的售后工单草稿，不表示订单事实已核验。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    category: Literal["退款进度", "退货申请", "其他"] = Field(description="用户主要诉求")
    order_id: str | None = Field(
        default=None,
        pattern=r"^A[0-9]{4}$",
        description="只提取原话明确出现的订单号，未提供时为null，不猜测",
    )
    urgency: Literal["普通", "着急"] = Field(description="仅在用户明确表达着急或催促时填着急")
    summary: str = Field(min_length=1, max_length=60, description="概括原话，不添加退款状态等新事实")


class RequiredNullable(BaseModel):
    order_id: str | None


class OmittableNullable(BaseModel):
    order_id: str | None = None


class EvidenceMismatch(ValueError):
    pass


def check_order_evidence(ticket, original_text):
    if ticket.order_id is None:
        return
    pattern = rf"(?<![A-Za-z0-9]){re.escape(ticket.order_id)}(?![A-Za-z0-9])"
    if re.search(pattern, original_text) is None:
        raise EvidenceMismatch("抽取的订单号未在原话中独立出现")


def next_step(ticket):
    if ticket.category == "其他":
        return "人工分拣"
    if ticket.order_id is None:
        return "请用户补充订单号"
    if ticket.category == "退款进度":
        return "进入退款跟进队列"
    return "进入退货咨询队列"


def prepare_draft(envelope, original_text):
    ticket = envelope["parsed"]
    if envelope["parsing_error"] is not None or not isinstance(ticket, Ticket):
        return {"state": "needs_review", "reason": "invalid_structure", "draft": None}
    try:
        check_order_evidence(ticket, original_text)
    except EvidenceMismatch:
        return {"state": "needs_review", "reason": "order_not_in_source", "draft": None}
    return {"state": "ready", "draft": ticket.model_dump(), "next_step": next_step(ticket)}
