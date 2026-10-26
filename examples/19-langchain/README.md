# 第19篇：LangChain封装了什么

配合[正文](../../19-LangChain入门它到底帮我们封装了什么.md)使用。[GitHub示例目录](https://github.com/benx92/ai-learning-notes/tree/main/examples/19-langchain)。

## 正文先看这些文件

| 文件 | 正文用途 |
| --- | --- |
| `comparison_demo.py` | 主实验：同一业务函数、同一固定响应，对比手写Python循环与真实LangChain Agent循环 |
| `two_tools_demo.py` | 新增物流查询，对照工具说明、函数登记和工具列表的修改 |
| `agent_demo.py` | 可选在线入口，接入DeepSeek模型，使用扩展组件中的只读查询工具 |
| `test_comparison.py` | 主实验2项检查：后端状态变化、订单归属拒绝和调用ID配对 |
| `test_two_tools.py` | 双工具2项检查：退款与物流分发、结果变化、参数与访问检查 |
| `requirements.txt` | 固定直接依赖版本 |

先看主实验的`get_refund_status()`，然后直接对照`run_python()`与`run_langchain()`中的步骤注释：手写版自己维护步骤1—6，框架版登记模型与函数，再由`invoke()`启动框架执行。`tools=[get_refund_status]`传函数本身，此时不执行查询。

理解两版区别以后，再看`scripted_reply()`和`make_scripted_model()`如何提供相同的离线响应，最后看`main()`怎样启动两条路径。这两个辅助函数是实验需要，不是接入在线模型必须编写的代码。在线使用流程见`agent_demo.py`中步骤1—5的注释。

`scripted_reply()`产生预设请求或读取工具结果，不执行查询；`make_scripted_model()`只转换消息与工具说明。实际查询分别由手写循环和框架执行。固定响应不具备自然语言理解能力。

## 下载、安装与运行

首次下载，在准备保存项目的目录执行：

```powershell
git clone https://github.com/benx92/ai-learning-notes.git
cd ai-learning-notes
```

已有仓库直接进入仓库根目录。然后使用Python 3.12执行：

```powershell
cd examples/19-langchain
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe comparison_demo.py
.\.venv\Scripts\python.exe two_tools_demo.py
```

主实验不需要API Key。预期两条路径都经过用户消息、工具请求、工具结果和最终回答；A1001的退款状态为“审核中”，物流为“运输中，已到达杭州转运中心”。改变业务记录，结果也应随之变化。

直接依赖为LangChain 1.4.6、langchain-core 1.6.10、langchain-deepseek 1.1.1。独立环境复核使用LangGraph 1.2.16；直接依赖固定不等于所有间接依赖已锁定。

只检查正文两组离线实验（4项）：

```powershell
.\.venv\Scripts\python.exe -m unittest test_comparison test_two_tools -v
```

检查全部实验，包括扩展测试（12项）：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## 可选在线入口

在同一示例目录和PowerShell窗口中，配置自己的可用模型：

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用且支持工具调用的模型名"
.\.venv\Scripts\python.exe agent_demo.py
```

在线脚本从`extensions/components_demo.py`导入已封装的查询工具，返回含`ok`等字段的JSON字符串；主对比实验使用普通函数返回状态文本。两者是不同的实验数据接口。

脚本读取进程环境变量，不自动加载`.env`。模型调用上限3次，工具调用上限2次，触顶抛错；单次网络超时45秒，客户端自动重试关闭。当前未使用真实密钥验证在线回答效果。

## 扩展说明使用的文件

[组件与接口扩展说明](../../supplements/19-LangChain组件与接口扩展.md)中的实验集中放在`extensions/`：

| 文件 | 用途 |
| --- | --- |
| `extensions/components_demo.py` | 提示模板、Document、工具参数和ToolMessage的离线观察；同时提供在线入口使用的查询工具 |
| `extensions/offline_agent_demo.py` | 用固定模型响应检查在线入口所配置的Agent循环和调用限额 |
| `extensions/test_examples.py` | 上述组件、执行接口与Agent行为的8项测试 |
| `extensions/__init__.py` | 使扩展目录可作为Python包运行，并支持测试递归发现 |

从`19-langchain`目录运行，使用模块入口：

```powershell
.\.venv\Scripts\python.exe -m extensions.components_demo
.\.venv\Scripts\python.exe -m extensions.offline_agent_demo
```

`components_demo.py`直接创建政策Document，不解析文件或执行RAG。`offline_agent_demo.py`固定查询A1001，最终回答也是预设文本，只用于观察四条消息、调用ID和次数；实际后端结果变化的验证由正文主实验负责。

所有订单、用户与物流都是教学快照。固定用户不能代替真实认证，工具只查询，不提交申请。示例未实现真实售后后端、跨运行会话持久化或完整界面。
