"""观察LCEL数据交接；默认固定响应离线运行，可选接入在线模型。"""

import argparse  # 读取命令行里的--live开关。
import os  # 从进程环境变量读取密钥和模型名。
from collections.abc import Iterator  # 标注逐片接收、逐片产出的迭代器类型。
from operator import itemgetter  # itemgetter("question")等价于从字典取question字段。

from langchain_core.language_models.fake_chat_models import FakeListChatModel  # 离线固定响应。
from langchain_core.output_parsers import StrOutputParser  # 模型消息转为文本。
from langchain_core.prompts import ChatPromptTemplate  # 用字典字段填充聊天消息。
from langchain_core.runnables import (
    RunnableBranch,  # 按程序条件选择一条路径。
    RunnableGenerator,  # 包装逐片处理的生成器。
    RunnableLambda,  # 把普通函数接入链的调用接口。
    RunnableParallel,  # 同一份输入交给多条支路，汇总成字典。
    RunnablePassthrough,  # 保留原输入，或用assign追加字段。
)


# 教学快照：只按tier选资料，不验证真实会员身份或订单资格。
POLICIES = {
    "member": "教学政策：会员订单签收后15日内可以申请退货，商品例外需另行核对。来源：demo-policy/member。",
    "general": "教学政策：普通订单签收后7日内可以申请退货，商品例外需另行核对。来源：demo-policy/general。",
}
# 完整流水线的外部输入；基础链需要的则是context/question。
DEMO_INPUT = {"tier": "member", "question": "会员订单的申请期限是多少？"}
# 用于检查执行过程的固定答案，不由输入内容计算得出。
FIXED_REPLY = "教学固定响应：会员订单的申请期限为签收后15日，商品例外仍需核对。"


def make_prompt():
    # make_prompt是本例自定义函数；ChatPromptTemplate是框架提供的模板组件。
    # from_messages根据“角色+文字格式”创建模板，不是向模型发送消息。
    # 步骤1：声明消息格式；{context}和{question}到invoke时才填入。
    # 创建模板不会请求模型，也不会检索资料。
    return ChatPromptTemplate.from_messages([
        # system保存处理要求；human中的两个占位符接收本次资料与问题。
        ("system", "只解释提供的教学政策，不判断具体订单资格，不查询或提交申请。"),
        ("human", "资料：{context}\n问题：{question}"),
    ])


def build_basic_chain(model):
    # 模板负责准备输入；解析器只提取文本，不再次调用模型。
    prompt = make_prompt()
    # StrOutputParser是组件类名；加()创建对象，保存到自定义变量parser中。
    # 它把AIMessage中的文本交给下一步；当前纯文本例子也可以直接读reply.content。
    parser = StrOutputParser()
    # 步骤1 -> 步骤2 -> 步骤3：填模板 -> 调模型 -> 从响应中取出文本。
    # 这里只建立连接；chain.invoke(inputs)才会真正按顺序执行。
    return prompt | model | parser


def normalize(data):
    # 普通Python业务步骤：校验输入、清理空白，返回新字典，不修改原输入。
    if not isinstance(data, dict):
        raise TypeError("输入必须是字典")
    # get取不到字段时返回None，下面的检查会拒绝缺失或不支持的值。
    tier = data.get("tier")
    question = data.get("question")
    if tier not in POLICIES:  # 只允许已有教学条款的标识。
        raise ValueError("tier必须是member或general")
    if not isinstance(question, str):  # 先检查类型，才可以安全调用strip。
        raise TypeError("question必须是字符串")
    # 全空白问题会变为""，交给后面的空问题分支处理。
    return {"tier": tier, "question": question.strip()}


def select_policy(data):
    # 输入是完整的tier/question字典，输出只是一段政策字符串。
    return POLICIES[data["tier"]]


def build_inputs():
    # 这两路由开发者预先写定：一路取政策，另一路保留原问题。
    # 没有分析或拆分问题；两个本地取值也不代表两次资料服务请求。
    # 两条支路收到同一份完整字典；支路名称成为汇总结果的键。
    return RunnableParallel(
        # 取条款字符串，放入输出的context字段。
        context=RunnableLambda(select_policy),
        # 取原问题字符串，放入输出的question字段；itemgetter来自operator。
        question=RunnableLambda(itemgetter("question")),
    )


def build_preserved_inputs():
    # 与上面的重建字典不同：保留tier和question，再追加context。
    # 输入必须是字典；select_policy仍然读取原输入里的tier。
    return RunnablePassthrough.assign(context=RunnableLambda(select_policy))


def build_pipeline(model):
    # 非空问题路径：tier/question -> context/question -> 提示 -> 模型响应 -> 文本。
    answer = build_inputs() | build_basic_chain(model)
    route = RunnableBranch(
        # 每个条件分支是(判断函数, 处理组件)；最后的answer是默认处理组件。
        # 条件成立时只返回提示，不进入上面的answer，也不调用模型。
        (lambda data: not data["question"],
         RunnableLambda(lambda data: "请先填写政策问题。")),
        # 默认分支必须提供；只有条件不成立时才执行这条链。
        answer,
    )
    # 实际执行从左向右：先清理空白，再判断清理后的问题是否为空。
    # 函数里先创建answer对象，不代表运行时会先执行answer。
    return RunnableLambda(normalize) | route


def uppercase_chunks(chunks: Iterator[str]) -> Iterator[str]:
    # chunks是文本片段迭代器，chunk是当前的一小段字符串，不是整段回答。
    for chunk in chunks:
        # 每收到一个文本片段就产出一个结果，不等待整个字符串收齐。
        yield chunk.upper()


def stream_observation():
    # 字符响应只用于确定性观察分片，不代表真实服务的Token边界或延迟。
    model = FakeListChatModel(responses=["a b"])
    chain = build_basic_chain(model)
    inputs = {"context": POLICIES["member"], "question": "观察流式交接"}
    # 直接观察基础链的分片；list只是收集输出用于对比，不是实时界面展示。
    direct = list(chain.stream(inputs))
    # 普通字符串函数先等输入收齐，最终只交出一个结果。
    buffered = list((chain | RunnableLambda(str.upper)).stream(inputs))
    # 生成器逐片接收并产出，保留增量交接。
    incremental = list((chain | RunnableGenerator(uppercase_chunks)).stream(inputs))
    # 返回三份片段列表，让调用方比较缓冲前后的差异。
    return {"direct": direct, "buffered": buffered, "incremental": incremental}


def make_model(live=False):
    # 不传参数时live=False；只有显式在线调用才会进入下面的客户端配置。
    if not live:
        # 离线测试对象：无论问题或条款怎样变化，都返回FIXED_REPLY。
        return FakeListChatModel(responses=[FIXED_REPLY])
    # 先检查配置，再导入在线集成；离线分支无需密钥。
    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("LC_CHAT_MODEL"):
        raise RuntimeError("请先设置自己的DEEPSEEK_API_KEY和可用的LC_CHAT_MODEL")
    from langchain_deepseek import ChatDeepSeek

    # 在线模式使用已有模型客户端；构造客户端本身不发送聊天请求。
    return ChatDeepSeek(
        model=os.environ["LC_CHAT_MODEL"],  # 使用账户可用的模型名。
        timeout=45,  # 单次请求等待上限，单位秒。
        max_retries=0,  # 关闭客户端自动重试，避免隐藏额外调用。
        extra_body={"thinking": {"type": "disabled"}},  # 本例使用供应商非思考模式。
    )


def main():
    # 入口步骤1：解析开关；不带--live时只运行固定响应实验。
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--live", action="store_true", help="使用自己的在线模型，产生对应服务费用")
    args = cli.parse_args()
    # 入口步骤2：准备模型对象，再创建完整流水线。
    model = make_model(args.live)
    # 先组装，不执行；下一步invoke才开始处理输入。
    pipeline = build_pipeline(model)
    if args.live:
        # 在线只执行一次完整流程，不再为展示中间值重复调用模型。
        print(pipeline.invoke(DEMO_INPUT, config={"run_name": "policy-explanation"}))
        return

    print("固定响应只用于观察接口与数据流，不理解问题，也不验证政策答案。")
    # 离线拆开观察：输入整理 -> 字段映射 -> 提示 -> 模型响应 -> 字符串。
    normalized = normalize(DEMO_INPUT)
    # tier/question -> context/question：选好政策，重建模板所需字段。
    inputs = build_inputs().invoke(normalized)
    # 字典 -> ChatPromptValue：填模板，此时尚未请求模型。
    prepared = make_prompt().invoke(inputs)
    # ChatPromptValue -> AIMessage：调用模型，本次默认是固定响应对象。
    reply = model.invoke(prepared)
    # AIMessage -> str：提取回答文本。
    text = StrOutputParser().invoke(reply)
    print("1. 原始输入：", DEMO_INPUT)
    print("2. 模板变量：", inputs)
    print("3. 模板输出类型：", type(prepared).__name__)
    print("   消息类型：", [type(m).__name__ for m in prepared.to_messages()])
    print("4. 模型输出类型：", type(reply).__name__)
    print("5. 解析结果是否为字符串：", isinstance(text, str), text)
    # 再运行整链用于对照；这会再次使用模型，所以只在离线演示里这样做。
    print("6. 同一输入运行整条链：", pipeline.invoke(DEMO_INPUT))
    print("7. 保留字段后追加context：", build_preserved_inputs().invoke(normalized))
    print("8. 空问题分支：", pipeline.invoke({"tier": "member", "question": "  "}))
    print("9. 流式观察：", stream_observation())


if __name__ == "__main__":
    # 直接运行文件才启动演示；其他脚本import这些函数时不会自动执行main。
    main()
