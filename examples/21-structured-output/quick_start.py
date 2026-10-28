"""最小在线抽取：配置模型、约定输出结构、读取工单字段。"""

import os

from langchain_deepseek import ChatDeepSeek

from schemas import Ticket


model = ChatDeepSeek(
    model=os.environ["LC_CHAT_MODEL"],
    temperature=0,
    timeout=45,
    max_retries=0,
    extra_body={"thinking": {"type": "disabled"}},
)
extractor = model.with_structured_output(
    Ticket, method="function_calling", include_raw=True,
)
result = extractor.invoke([
    ("system", "从原话整理售后工单草稿，只抽取诉求，不核定退款事实。"
     "未提供的订单号用null，不猜测。"),
    ("human", "A1001的退款申请还没处理，麻烦帮我跟进一下，我挺着急。"),
])
ticket = result["parsed"]
print(type(ticket).__name__)
print(ticket.order_id)
print(ticket.model_dump())
