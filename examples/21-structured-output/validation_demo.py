"""不调用模型，观察JSON解析、字段校验、未知值和来源核对的差别。"""

import json

from pydantic import ValidationError

from schemas import OmittableNullable, RequiredNullable, Ticket, prepare_draft


def parse_ticket(raw_text):
    data = json.loads(raw_text)  # 步骤1：JSON文本转Python数据，只检查JSON语法。
    return Ticket.model_validate(data)  # 步骤2：按Ticket检查字段，成功才创建工单数据对象。


def main():
    raw = '{"category":"退款进度","order_id":"A1001","urgency":"着急","summary":"用户催促跟进退款申请"}'
    ticket = parse_ticket(raw)
    print("解析后类型：", type(ticket).__name__)
    print("读取字段：", ticket.category, ticket.order_id)
    for name, change in [
        ("缺少必填字段", {"urgency": None}),
        ("枚举值不符", {"urgency": "非常急"}),
        ("字符串null", {"order_id": "null"}),
        ("未知订单号", {"order_id": None}),
        ("新增未约定字段", {"refund_status": "已到账"}),
    ]:
        # 先转回字典，再用change覆盖部分字段，构造一个有差异的测试输入。
        data = ticket.model_dump() | change
        if name == "缺少必填字段":
            data.pop("urgency")
        try:
            parsed = Ticket.model_validate(data)
            print(name, "通过：", parsed.order_id)
        except ValidationError as exc:
            print(name, "拒绝：", [(e["loc"], e["type"]) for e in exc.errors()])

    for cls in (RequiredNullable, OmittableNullable):
        print(cls.__name__, "required:", cls.model_json_schema().get("required", []))

    # 此处故意构造来源错误的对象；model_copy(update=...)本身不重新校验更新值。
    invented = ticket.model_copy(update={"order_id": "A9999"})
    print("格式正确但来源不符：", prepare_draft(
        {"parsed": invented, "parsing_error": None}, "A1001的退款申请还没处理。",
    ))


if __name__ == "__main__":
    main()
