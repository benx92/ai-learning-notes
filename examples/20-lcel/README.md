# 用LangChain组织一次政策解释：配套示例

配合[文章正文](../../20-用LangChain组织一次政策解释.md)阅读。用政策解释任务先理解一次政策解释需要的三个步骤，再比较普通Python逐步调用与LCEL整链调用。字段映射、并行、异步、流式等按实际需要阅读扩展。

源码入口：[GitHub目录](https://github.com/benx92/ai-learning-notes/tree/main/examples/20-lcel)、[基础入口basic_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/basic_demo.py)、[复用组件与扩展chain_demo.py](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/chain_demo.py)、[重试与回退](https://github.com/benx92/ai-learning-notes/blob/main/examples/20-lcel/reliability_demo.py)。

两种对比写法都使用LangChain组件：逐步写`prompt.invoke()`、`model.invoke()`、`parser.invoke()`，与组装`prompt | model | parser`后统一调用相比，主要区别是数据交接由谁组织。源码注释标出相同的三个步骤。

## 文件

- `basic_demo.py`：正文优先入口，只观察逐步调用、整链调用和空问题提前返回；`--live`只执行一次在线生成。
- `chain_demo.py`：复用组件与可选扩展实验，默认离线打印数据形状和执行结果，`--live`才调用在线模型。
- `reliability_demo.py`：模拟只读查询的有限重试与失败回退，没有网络请求或业务写入。
- `test_examples.py`：14项本地测试，验证执行次数、数据类型、分支拦截、并行重叠、批量异常位置、异步与流式交接。
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

## 阅读与调用顺序

1. 先运行`basic_demo.py`。`run_stepwise()`逐行准备输入、调用模型、读取文字；`build_basic_chain()`把相同职责组织成共同的链。
2. 看`answer_question()`中的普通if：空问题直接返回，不调用模型。先理解这个产品行为，无须先学习分支组件。
3. 按需读[组件组合与运行方式扩展](../../supplements/20-组件组合与运行方式扩展.md)，再运行原有`chain_demo.py`与`reliability_demo.py`。不用一次加入所有组件。

基础链和基础入口需要`context/question`。扩展中的`build_pipeline()`另演示页面的`tier/question`怎样转为模板变量，两个入口的字段不能混用。

基础入口默认输出逐步调用结果、整链调用结果和空问题提示；前两项都使用相同的固定回复，不验证自然语言理解。14项测试包含原有12项组件检查，以及2项基础入口检查，核对空问题不请求模型、有效问题实际调用次数和两条路径结果一致。

## 可选在线调用

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe basic_demo.py --live
```

脚本读取进程环境变量，不自动读取`.env`。在线调用消耗服务额度，不要提交真实密钥。当前配置为单次请求超时45秒、客户端自动重试关闭、供应商非思考模式；改变服务或模式时按官方文档核对。

示例未主动接入外部追踪服务；若已有环境配置，应自行核对数据发送范围。`run_name`只用于标识执行，不会独立创建监控服务。

## 验证范围

14项测试使用真实核心组件与固定响应，未使用真实密钥验证在线生成。并行测试用同步屏障确认两个支路可以重叠执行，不把机器耗时写成性能保证。批量测试核对错误对应的输入位置，不假定已执行任务能够回滚。

本例没有向量检索、实时订单查询、业务写入、持久会话或完整审批系统。程序完成数据交接，不代表模型答案已经正确。
