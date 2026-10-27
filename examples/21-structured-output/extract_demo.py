"""完整抽取路径：准备输入、结构化模型、有限重试、草稿检查。默认离线。"""

import argparse
import json
import os

from langchain_core.prompts import ChatPromptTemplate

from fixtures import DEMO_TEXT, GOOD_ARGS, ScriptedModel, tool_reply
from schemas import Ticket, prepare_draft


def make_prompt():
    # 步骤1：声明抽取要求与原话的位置；validation_hint首次为空，失败后才追加提醒。
    return ChatPromptTemplate.from_messages([
        ("system", "从用户原话整理售后工单草稿，只抽取诉求，不核定退款事实。"
         "订单号未提供时使用JSON null，不生成订单号。{validation_hint}"),
        ("human", "用户原话：{text}"),
    ])


def build_chain(model):
    # 步骤2：按Ticket类的规则配置输出，不是创建一份已经填写好的工单。
    # 这一步只组装组件；invoke才请求模型并处理返回值。
    extractor = model.with_structured_output(
        # function_calling用工具参数承载数据；include_raw保留原始消息和解析状态。
        Ticket, method="function_calling", include_raw=True,
    )
    # 与纯文本链不同，这里直接返回解析后的对象及状态，不接StrOutputParser取正文。
    return make_prompt() | extractor


def extract_with_retry(model, text, max_attempts=2):
    # 最多尝试次数包含首次；默认一次失败后只再尝试一次。
    if max_attempts < 1:
        raise ValueError("max_attempts必须至少为1")
    chain = build_chain(model)
    hint = ""
    for attempt in range(1, max_attempts + 1):
        # 每次都用原始text重新填模板；hint是本次附加的校验提醒。
        result = chain.invoke({"text": text, "validation_hint": hint})
        result = {**result, "attempts": attempt}  # 复制结果字典并追加当前尝试次数。
        # 同时检查错误和结果类型；没有异常，不代表一定拿到了Ticket。
        if result["parsing_error"] is None and isinstance(result["parsed"], Ticket):
            return result
        # 只有结构结果失败才继续；网络或模型调用异常会直接向上抛出。
        hint = "上次未得到有效工单。检查必填字段、分类取值、摘要长度和订单号格式，再提交Ticket数据。"
    # 次数耗尽交回最后一次失败信息，不伪造一份成功结果。
    return result


def make_live_model():
    from langchain_deepseek import ChatDeepSeek

    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请设置自己的DEEPSEEK_API_KEY和LC_CHAT_MODEL")
    # 创建客户端供链使用，此时不发送抽取请求；密钥由集成读取环境变量。
    return ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"],
        temperature=0,
        timeout=45,
        max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )


def main():
    # 入口1：读取--live开关；默认用固定回复，避免需要密钥才能学习接口。
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    options = parser.parse_args()
    model = make_live_model() if options.live else ScriptedModel(responses=[tool_reply(GOOD_ARGS)])
    if not options.live:
        print("固定响应只验证接口和校验，不代表模型理解了用户原话。")
    # 入口2：模板 -> 结构化调用 -> 校验 -> 必要时有限重试。
    result = extract_with_retry(model, DEMO_TEXT)
    print("模型尝试次数：", result["attempts"])
    print("原始消息类型：", type(result["raw"]).__name__)
    print("工具参数：", result["raw"].tool_calls)
    print("解析结果类型：", type(result["parsed"]).__name__)
    print("解析错误：", type(result["parsing_error"]).__name__ if result["parsing_error"] else None)
    # 入口3：核对来源并准备草稿；json.dumps仅将结果编码为便于查看的JSON文本。
    print(json.dumps(prepare_draft(result, DEMO_TEXT), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
