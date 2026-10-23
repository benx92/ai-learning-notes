# 第19章：LangChain组件与执行循环

配合[第19章正文](../../19-LangChain入门它到底帮我们封装了什么.md)，先运行`comparison_demo.py`：用同一业务函数和相同的固定响应，对照普通Python循环与LangChain Agent循环。只沿一次退款查询，观察模型请求、函数执行、结果回传和第二次模型调用分别由谁组织。主实验不需要其他组件练习或外部资料库；其余脚本供后续按需查阅。

## 文件

- `comparison_demo.py`：正文主实验。`run_python()`用普通字典和函数手写循环，不依赖LangChain；`run_langchain()`把同一个业务函数交给真实框架调度。两者使用相同的预设回复逻辑，完整脚本需要安装本章依赖。
- `two_tools_demo.py`：正文新增物流查询的完整实验，保留退款工具，对照两版登记位置；固定响应按关键词提出预设请求，不验证自然语言理解。
- `test_two_tools.py`：检查两种请求分发、后端状态变化与物流访问检查。
- `test_comparison.py`：改变后端状态和订单归属，检查两条路径是否使用真实业务结果、保持访问检查并配对请求ID。

- `reading_demo.py`：可选扩展，比较普通Python消息与模板消息，再手动查询A1001；不请求聊天模型。
- `components_demo.py`：真实组件的离线练习，不请求聊天模型。打印模板消息、工具参数类型与带调用ID的结果。
- `offline_agent_demo.py`：用固定模型响应运行真实Agent与查询工具，打印四条消息、调用ID和调用次数，不需要API Key。`ScriptedModel`同时供测试使用，不具备自然语言理解能力。
- `agent_demo.py`：可选的在线只读Agent，复用相同工具。需要自己的DeepSeek密钥和支持相应工具调用方式的模型。
- `test_examples.py`：使用固定模型响应检查真实Agent循环，测试对象不具备自然语言理解能力。
- `requirements.txt`：本例固定的直接依赖版本。

## 安装与运行

在该目录的PowerShell中，使用Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe comparison_demo.py
.\.venv\Scripts\python.exe two_tools_demo.py
.\.venv\Scripts\python.exe reading_demo.py
.\.venv\Scripts\python.exe components_demo.py
.\.venv\Scripts\python.exe offline_agent_demo.py
.\.venv\Scripts\python.exe -m unittest -v
```

直接依赖：LangChain 1.4.6、langchain-core 1.6.10、langchain-deepseek 1.1.1。本次独立环境复核中的LangGraph为1.2.16；需要保存完整环境时，记录间接依赖实际版本。

`reading_demo.py`的模板准备和手动查询是同一售后场景的两种需求，不代表已经运行了一个有持久记忆的聊天应用。模板不会调用模型；工具的手动查询也不需要模型。`agent_demo.py`单独展示模型选择查询工具的路径，没有自动继承离线脚本中的政策消息。

`offline_agent_demo.py`固定查询A1001，预期轨迹依次是`HumanMessage`、带工具请求的`AIMessage`、对应的`ToolMessage`、最终`AIMessage`，模型调用2次、工具结果1条。它真正执行本地查询函数，但模型响应是程序预先写好的，不能拿它测试任意问法或判断在线模型效果。现有测试仍单独覆盖归属拒绝与重复调用限额。

在线练习另行设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe agent_demo.py
```

脚本不自动读取`.env`。不要将真实密钥写入仓库。未主动配置外部追踪服务；如果已有环境配置，需要自行确认其追踪与数据发送设置。

## 本地验证范围

原有8项测试覆盖模板字段、工具参数与类型、归属拒绝、结果配对、真实框架循环、调用限额，以及invoke、batch、stream、ainvoke的返回方式。模型执行测试均使用固定响应，不具备自然语言理解能力。在线集成对象的构造已检查，未使用真实密钥请求聊天模型。

新增2项对比检查覆盖后端状态变化与归属拒绝，两种实现都执行相同的业务函数。`scripted_reply()`只产生预设请求或读取传入的工具结果，不执行查询；`make_scripted_model()`仅转换框架格式。手写版的`TOOL_SPECS`是实验内部约定，不是供应商HTTP请求体。未接入真实模型的手写版传输适配；在线框架练习仍使用`agent_demo.py`。

工具数据是固定教学快照：A1001属于`demo-user`、状态审核中；A2002属于他人，不返回状态。固定用户不能代替真实认证。工具只查询，不提交申请。政策Document直接创建，不代表解析了文件或完成RAG。

主对比实验两版都限制最多3次模型调用；它只演示只读查单，未扩展并发工具、工具异常恢复或跨次会话。原有`agent_demo.py`的模型调用上限3次，工具调用上限2次，触顶抛错。网络等待限制为单次请求45秒，模型客户端自动重试关闭。示例没有跨运行会话持久化、完整界面、生产错误文案或真实售后后端。

新增物流实验复用主实验的订单记录和模型适配器。`make_scripted_model(reply_function=...)`允许接入相同的双工具固定响应；不传参数时仍使用原退款响应。物流记录是教学快照，不连接真实物流服务。2项新增测试覆盖物流与退款分发、业务结果变化、调用ID配对以及归属拒绝和订单号检查。
