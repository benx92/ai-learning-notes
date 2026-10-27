# 第21章：结构化输出与工单草稿

配合[正文](../../21-结构化输出让模型结果变成程序能用的数据.md)，观察用户原话怎样成为可校验工单。默认离线：回复预先写好，真正运行LangChain解析与Pydantic校验，不验证模型的自然语言理解能力。

公开入口：[GitHub示例目录](https://github.com/benx92/ai-learning-notes/tree/main/examples/21-structured-output)、[字段规则](https://github.com/benx92/ai-learning-notes/blob/main/examples/21-structured-output/schemas.py)、[主实验](https://github.com/benx92/ai-learning-notes/blob/main/examples/21-structured-output/extract_demo.py)。

先用普通字典和`Ticket(...)`理解字段检查，再对照`build_chain()`把同一份Ticket规则交给模型。`Ticket`是数据类型，`ticket`是一份具体数据，`model_validate()`等Pydantic方法不调用大语言模型。主实验和数据处理源码都带步骤注释。

## 文件与运行顺序

| 文件 | 作用 |
| --- | --- |
| `schemas.py` | Ticket结构、空值对照、订单号来源检查、下一步建议与草稿处理 |
| `validation_demo.py` | JSON解析与字段校验；缺字段、非法枚举、字符串null、额外字段和来源不符 |
| `fixtures.py` | 固定工具响应与`ScriptedModel`；只适配模型接口，不执行订单查询 |
| `extract_demo.py` | 模板与结构化模型组合、最多两次生成尝试、草稿判断；可选`--live` |
| `agent_demo.py` | 真实Agent的`ToolStrategy`与`structured_response`对照，固定响应 |
| `test_examples.py` | 14项接口、失败分支与来源检查测试 |

首次下载时，在准备保存项目的目录执行：

```powershell
git clone https://github.com/benx92/ai-learning-notes.git
cd ai-learning-notes
```

已有仓库直接进入仓库根目录，再执行`cd examples/21-structured-output`。在该目录的PowerShell运行，使用Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe validation_demo.py
.\.venv\Scripts\python.exe extract_demo.py
.\.venv\Scripts\python.exe agent_demo.py
.\.venv\Scripts\python.exe -m unittest -v
```

固定直接依赖：LangChain 1.4.6、langchain-core 1.6.10、langchain-deepseek 1.1.1、Pydantic 2.14.1。

## 应观察到什么

`extract_demo.py`的原始响应是`AIMessage`，数据在`tool_calls`，解析后为`Ticket`。默认输入中的订单号A1001有来源，最终返回`state: ready`与“进入退款跟进队列”。`ready`只表示通过本例草稿检查，不表示订单真实、已查询、已创建工单或已退款。

无订单号时应保留`None`并提示补充；订单号虽然符合格式但不在原话里时，应得到`needs_review`，`draft`为空。来源检查只是文本出现核对，不代替身份、归属和实时状态核验，也不自动证明摘要与分类正确。

`agent_demo.py`的最终数据在`structured_response`；消息轨迹依次为`human`、`ai`、`tool`，最后的工具消息只是接收结构数据。该例没有业务工具，策略内自动修正关闭，模型调用上限2次。

## 在线抽取

在同一PowerShell会话设置自己的凭证与支持本例工具调用方式的可用模型名：

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe extract_demo.py --live
```

不自动读取`.env`；不要把真实密钥提交到Git。使用`method="function_calling"`与非思考模式配置，单次请求超时45秒，客户端自动重试关闭，最多两次生成尝试。该配置用于本例的DeepSeek集成，更换供应商或模式需核对支持范围。在线调用使用自己的服务额度。

本次验证只运行了离线脚本与14项测试，未使用真实密钥发起生成请求，也未测试线上准确率、拒绝率、费用或延迟。未主动配置外部追踪；若环境已有追踪配置，应按自己的数据处理规则使用。

## 验证范围与边界

测试覆盖JSON语法与Schema校验的区别、空值与省略、非法字段拒绝、构造时不调用模型及Schema传递、错误响应保留、工具参数JSON截断、无工具调用、缺订单号追问、来源不符、有限重试与新消息准备、重试耗尽、模型执行错误外抛、Agent结果字段、字典Schema不自动执行Pydantic校验。

ScriptedModel只返回预先写好的响应；即使更改输入，它也不会智能抽取。不要用它测自然语言效果。解析重试保留原始输入，添加一般性校验提醒，没有根据具体字段错误自动修正。来源检查在解析成功后执行，失败直接返回待核对，不进入生成重试。

没有工单数据库、真实订单API、身份认证或审批写入。尚未实现多订单抽取、嵌套列表、结构化流式增量、原生JSON Schema服务路径；相关差别见[实现与接口说明](../../supplements/21-结构化输出实现与接口说明.md)。
