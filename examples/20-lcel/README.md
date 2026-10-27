# 用LangChain组织一次政策解释：配套示例

配合[文章正文](../../20-用LangChain组织一次政策解释.md)阅读。正文只使用同一份会员教学条款和同一个期限问题，讲清“填消息模板→取得模型回复→取出文字”，再比较普通Python逐步调用与LCEL整链调用。目录中另有独立的接入与扩展实验，不属于正文必须完成的步骤。

源码入口：[GitHub目录](https://github.com/benx92/ai-learning-notes/tree/main/examples/20-lcel)、[基础入口basic_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/basic_demo.py)、[复用组件与扩展chain_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/chain_demo.py)、[重试与回退](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/reliability_demo.py)。

两种对比写法都使用LangChain组件：逐步写`prompt.invoke()`、`model.invoke()`、`parser.invoke()`，与组装`prompt | model | parser`后统一调用相比，主要区别是数据交接由谁组织。源码注释标出相同的三个步骤。

## 文件

- `basic_demo.py`：正文入口，用同一份资料和问题观察逐步调用、整链调用；两种路径都经过模板、模型和解析器。`--live`只执行一次在线生成。内部`answer_question()`另保留基本输入检查，由测试覆盖。
- `rag_bridge.py`：复用13篇的ask，将检索得到的原文交给本篇的链，保留证据与资料不足状态；完整运行需要13篇的依赖与已入库数据库。
- `test_rag_bridge.py`：2项接入检查，控制检索返回值验证真实ask与链的交接，不测向量召回效果。
- `chain_demo.py`：复用组件与可选扩展实验，默认离线打印数据形状和执行结果，`--live`才调用在线模型。
- `reliability_demo.py`：模拟只读查询的有限重试与失败回退，没有网络请求或业务写入。
- `test_examples.py`：14项本地测试，验证执行次数、数据类型、分支拦截、并行重叠、批量异常位置、异步与流式交接；加上`test_rag_bridge.py`共16项。
- `requirements.txt`：固定直接依赖版本。

条款来自固定教学字典。`tier`只用于选择演示条款，不是用户认证或订单资格依据。离线的`FakeListChatModel`总是返回预设的会员政策文本，不理解问题，也不会因为输入改成普通订单就自行改写答案。用它检查执行，不要用它验证政策判断。

## 安装与运行

首次下载时，在准备保存项目的目录执行：

```powershell
git clone https://github.com/benx92/ai-learning-notes.git
cd ai-learning-notes
```

已有仓库直接进入仓库根目录，再切换到示例目录：

```powershell
cd examples/20-lcel
```

在本目录打开PowerShell，使用Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe basic_demo.py
# 以下两项是按需运行的扩展实验。
.\.venv\Scripts\python.exe chain_demo.py
.\.venv\Scripts\python.exe reliability_demo.py
.\.venv\Scripts\python.exe -m unittest -v
```

固定`langchain-core==1.6.10`与`langchain-deepseek==1.1.1`。当前实验未使用`create_agent`，无需额外安装LangChain Agent入口。安装工具仍会解析间接依赖，长期复现实验时应记录完整环境。

默认程序先逐步调用，再运行整链作对照，因此会多次使用固定响应；在线模式只执行一次完整政策解释链。

可以观察这些结果：

- 输入整理得到`context`和`question`；提示类型为`ChatPromptValue`，模型响应为`AIMessage`，解析结果兼容字符串。
- `build_inputs()`重建两字段字典；`build_preserved_inputs()`保留原字段并追加`context`。
- 有效的空问题输入返回“请先填写政策问题。”，不调用模型；格式不合法的输入仍会先被`normalize`拒绝。
- 固定流式响应`a b`直接产生`['a', ' ', 'b']`；Lambda后处理得到`['A B']`，Generator得到`['A', ' ', 'B']`。这是分片机制观察，不是线上Token或延迟测量。
- 重试实验总共尝试3次；回退明确说明尚未完成核对，不伪造成功结果。

`build_inputs()`的两路工作已由开发者写在函数里：`context`按已有`tier`从教学字典取条款，`question`保留原问题。它不自动拆分一句话、不推断身份，也不发起两次资料服务请求。`rag_bridge.py`另走完整问题进入已有知识库检索的路线；一次检索可返回多段资料，但资料是否充分仍需检查。

## 阅读与调用顺序

1. 先运行`basic_demo.py`，确认逐步调用与整链调用都返回同一段固定解释文字。
2. 对照正文检查`make_prompt()`怎样填资料和问题，`make_model()`创建什么对象，以及`StrOutputParser`怎样读取回复。
3. 比较`run_stepwise()`的三次组件调用和`build_basic_chain()`的组合。知识重点是相同数据怎样交接，以及Runnable与LCEL分别提供什么。

正文主线到此结束。需要检索接入时再看下方`rag_bridge.py`说明；需要其他组合或运行方式时，再按需读[组件组合与运行方式扩展](../../supplements/20-组件组合与运行方式扩展.md)，运行`chain_demo.py`或`reliability_demo.py`。

基础链和基础入口需要`context/question`。扩展中的`build_pipeline()`另演示页面的`tier/question`怎样转为模板变量，两个入口的字段不能混用。

基础入口默认输出逐步调用结果和整链调用结果，两项都使用相同的固定回复，不验证自然语言理解。16项测试包含原有12项组件检查、2项基础入口检查，以及2项跨篇数据交接检查，核对空问题不请求模型、有效问题实际调用次数和两条路径结果一致。

## 独立接入实验：把第13篇资料输入接到本篇的链

`POLICIES["member"]`是基础实验手选的教学文字，未按问题检索。`rag_bridge.py`则继续使用13篇的`ask()`：问题先进入检索，命中结果交给`pack_context()`，选入的原文传给链的context，来源继续保留在evidence。

先按[13篇README](../13-rag/README.md)准备好RAG环境，完成`refund-policy.md`入库，并确认`text_demo`中已有记录。然后在同一个环境安装本目录requirements.txt，使嵌入、向量库与LangChain核心依赖同时可用。保持仓库目录关系，从本目录运行：

```powershell
python -m pip install -r requirements.txt
python rag_bridge.py --db ../13-rag/text_demo --question "定制商品有什么退货限制？"
```

这里的python必须是前面能运行13篇的那个环境内解释器；基础示例新建的轻量.venv不一定有RAG依赖。`--db`必须指向实际完成入库的目录，不能仅新建同名空目录；入库、模型配置与向量空间保持13篇原约定。

默认检索使用实际知识库，生成仍是固定回复，所以应先核对evidence与实际送入的原文，不把固定回答当作该问题的有效政策解释。配置本篇LC_CHAT_MODEL与自己的密钥后加`--live`才会在线生成；不会读取13篇RAG_CHAT_MODEL，也不传递13篇原HTTP生成器的用量字段。

本次自动检查以受控的检索返回值验证问题、原文、来源的交接，以及没有证据时不调用链；没有重新安装并测试真实嵌入模型或验证线上答案。它是固定RAG路线的接入，不是已经实现知识工具与订单工具的混合Agent。

## 可选在线调用

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe basic_demo.py --live
```

脚本读取进程环境变量，不自动读取`.env`。在线调用消耗服务额度，不要提交真实密钥。当前配置为单次请求超时45秒、客户端自动重试关闭、供应商非思考模式；改变服务或模式时按官方文档核对。

示例未主动接入外部追踪服务；若已有环境配置，应自行核对数据发送范围。`run_name`只用于标识执行，不会独立创建监控服务。

## 验证范围

16项测试使用真实核心组件与固定响应，未使用真实密钥验证在线生成。并行测试用同步屏障确认两个支路可以重叠执行，不把机器耗时写成性能保证。批量测试核对错误对应的输入位置，不假定已执行任务能够回滚。

`basic_demo.py`与`chain_demo.py`本身不执行向量检索；`rag_bridge.py`通过复用第13篇模块接入已有向量检索。这里没有实现自动拆分子问题、实时订单查询、业务写入、持久会话、完整审批系统或可部署的网页界面。程序完成数据交接，不代表模型答案已经正确。
