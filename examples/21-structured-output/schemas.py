"""工单草稿的数据约束与一个有限的来源核对。"""

import re
from typing import Literal  # 列出字段允许使用的固定值，不让模型自由命名分类。

from pydantic import BaseModel, ConfigDict, Field  # 数据对象基类、校验配置、字段约束。


class Ticket(BaseModel):
    """从用户原话整理的售后工单草稿，不表示订单事实已核验。"""

    # Ticket是我们定义的数据结构；BaseModel提供校验方法，不是大语言模型。
    # 拒绝多余字段，并关闭本例不需要的宽松类型转换。
    model_config = ConfigDict(extra="forbid", strict=True)

    # Literal只允许这三个分类；没有默认值，所以category必须提供。
    category: Literal["退款进度", "退货申请", "其他"] = Field(description="用户主要诉求")
    order_id: str | None = Field(
        default=None,  # 允许省略订单号；省略时用Python空值，不自动编造。
        pattern=r"^A[0-9]{4}$",  # 若提供字符串，必须完整符合A加4位数字。
        description="只提取原话明确出现的订单号，未提供时为null，不猜测",
    )
    # description解释字段含义；是否忠实原话仍需评估，不由类型校验保证。
    urgency: Literal["普通", "着急"] = Field(description="仅在用户明确表达着急或催促时填着急")
    summary: str = Field(min_length=1, max_length=60, description="概括原话，不添加退款状态等新事实")


class RequiredNullable(BaseModel):
    # 值允许None，但没有默认值，所以字段不能省略。
    order_id: str | None


class OmittableNullable(BaseModel):
    # 值允许None，也提供了默认值，所以整个字段可以省略。
    order_id: str | None = None


class EvidenceMismatch(ValueError):
    # 本例定义的异常类型，专门表示抽取订单号与原话不符。
    pass


def check_order_evidence(ticket, original_text):
    # 没提供订单号是合法未知值，留给后面的追问逻辑。
    if ticket.order_id is None:
        return
    # 转义订单号，并检查前后不是字母或数字，避免把A10010中的A1001误当依据。
    pattern = rf"(?<![A-Za-z0-9]){re.escape(ticket.order_id)}(?![A-Za-z0-9])"
    if re.search(pattern, original_text) is None:
        raise EvidenceMismatch("抽取的订单号未在原话中独立出现")


def next_step(ticket):
    # 只返回处理建议，不创建工单、不查询订单，也不执行退款。
    if ticket.category == "其他":
        return "人工分拣"
    if ticket.order_id is None:
        return "请用户补充订单号"
    if ticket.category == "退款进度":
        return "进入退款跟进队列"
    return "进入退货咨询队列"


def prepare_draft(envelope, original_text):
    # 步骤1：envelope是包含parsed/parsing_error等字段的结果字典。
    ticket = envelope["parsed"]
    if envelope["parsing_error"] is not None or not isinstance(ticket, Ticket):
        return {"state": "needs_review", "reason": "invalid_structure", "draft": None}
    # 步骤2：结构合格后，再核对订单号是否来自用户原话。
    try:
        check_order_evidence(ticket, original_text)
    except EvidenceMismatch:
        return {"state": "needs_review", "reason": "order_not_in_source", "draft": None}
    # 步骤3：数据对象转为普通字典，并给出下一步建议；这里不写数据库。
    return {"state": "ready", "draft": ticket.model_dump(), "next_step": next_step(ticket)}
