"""用普通Python保存和重传历史；探针只读本轮输入，不理解自然语言。"""

import re


FIRST = "我想跟进A1001的退款进度。"
FOLLOWUP = "那这笔呢？"
BASE_PROMPT = "你是教学售后助手。没有订单号时先询问；本例不查询实时订单。"


def probe_reply(messages):
    order_id = None
    style = None
    for message in messages:
        if message["role"] in {"user", "system"}:
            matches = re.findall(r"(?<![A-Za-z0-9])A[0-9]{4}(?![A-Za-z0-9])", message["content"])
            if matches:
                order_id = matches[-1]
        if message["role"] == "system" and "回复偏好：简短" in message["content"]:
            style = "简短"
    reply = (f"本轮输入可找到订单号{order_id}；尚未查询实时状态。"
             if order_id else "本轮输入没有订单号，需要用户补充。")
    return reply + (" 回复偏好：简短。" if style else "")


def chat_with_history(histories, conversation_id, text, call_model):
    messages = [*histories.get(conversation_id, []), {"role": "user", "content": text}]
    reply = call_model([{"role": "system", "content": BASE_PROMPT}, *messages])
    histories[conversation_id] = [*messages, {"role": "assistant", "content": reply}]
    return reply


def main():
    print("只发送最新一句：", probe_reply([{"role": "user", "content": FOLLOWUP}]))
    histories = {}
    print("手工保存历史，第1轮：", chat_with_history(histories, "conversation-a", FIRST, probe_reply))
    print("手工保存历史，第2轮：", chat_with_history(histories, "conversation-a", FOLLOWUP, probe_reply))
    print("另一场会话：", chat_with_history(histories, "conversation-b", FOLLOWUP, probe_reply))
    print("conversation-a保存的消息条数：", len(histories["conversation-a"]))


if __name__ == "__main__":
    main()
