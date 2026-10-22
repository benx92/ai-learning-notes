# 第20章：Runnable与LCEL处理链

配合[第20章正文](../../20-Runnable与LCEL把模型调用串成链.md)阅读。用政策解释任务观察模板、模型、解析器怎样交接，再加入输入整理、并行映射、字段保留、空问题分支与流式处理。

## 文件

- `chain_demo.py`：默认离线打印数据形状和执行结果，`--live`才调用在线模型。
- `reliability_demo.py`：模拟只读查询的有限重试与失败回退，没有网络请求或业务写入。
- `test_examples.py`：12项本地测试，验证执行次数、数据类型、分支拦截、并行重叠、批量异常位置、异步与流式交接。
- `requirements.txt`：固定直接依赖版本。

条款来自固定教学字典。`tier`只用于选择演示条款，不是用户认证或订单资格依据。离线的`FakeListChatModel`总是返回预设的会员政策文本，不理解问题，也不会因为输入改成普通订单就自行改写答案。用它检查执行，不要用它验证政策判断。

## 安装与运行

在本目录打开PowerShell，使用Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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

## 可选在线调用

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe chain_demo.py --live
```

脚本读取进程环境变量，不自动读取`.env`。在线调用消耗服务额度，不要提交真实密钥。当前配置为单次请求超时45秒、客户端自动重试关闭、供应商非思考模式；改变服务或模式时按官方文档核对。

示例未主动接入外部追踪服务；若已有环境配置，应自行核对数据发送范围。`run_name`只用于标识执行，不会独立创建监控服务。

## 验证范围

12项测试使用真实核心组件与固定响应，未使用真实密钥验证在线生成。并行测试用同步屏障确认两个支路可以重叠执行，不把机器耗时写成性能保证。批量测试核对错误对应的输入位置，不假定已执行任务能够回滚。

本例没有向量检索、实时订单查询、业务写入、持久会话或完整审批系统。程序完成数据交接，不代表模型答案已经正确。
