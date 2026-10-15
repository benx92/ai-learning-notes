# 第19章：LangChain组件与执行循环

配合正文理解框架封装了什么。示例独立运行，不需要RAG数据库或MCP服务。

## 文件

- `components_demo.py`：真实组件的离线练习，不请求聊天模型。打印模板消息、工具参数类型与带调用ID的结果。
- `agent_demo.py`：可选的在线只读Agent，复用相同工具。需要自己的DeepSeek密钥和支持相应工具调用方式的模型。
- `test_examples.py`：使用固定模型响应检查真实Agent循环，测试对象不具备自然语言理解能力。
- `requirements.txt`：本例固定的直接依赖版本。

## 安装与运行

在该目录的PowerShell中，使用Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe components_demo.py
.\.venv\Scripts\python.exe -m unittest -v
```

直接依赖：LangChain 1.4.6、langchain-core 1.6.10、langchain-deepseek 1.1.1。测试环境中的LangGraph为1.2.15；需要保存完整环境时，记录间接依赖实际版本。

在线练习另行设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe agent_demo.py
```

脚本不自动读取`.env`。不要将真实密钥写入仓库。未主动配置外部追踪服务；如果已有环境配置，需要自行确认其追踪与数据发送设置。

## 本地验证范围

已检查组件脚本输出；8项测试覆盖模板字段、工具参数与类型、归属拒绝、结果配对、真实框架循环、调用限额，以及invoke、batch、stream、ainvoke的返回方式。模型执行测试均使用固定响应，不具备自然语言理解能力。在线集成对象的构造已检查，未使用真实密钥请求聊天模型。

工具数据是固定教学快照：A1001属于`demo-user`、状态审核中；A2002属于他人，不返回状态。固定用户不能代替真实认证。工具只查询，不提交申请。政策Document直接创建，不代表解析了文件或完成RAG。

Agent单次模型调用上限3次，工具调用上限2次，触顶抛错。网络等待限制为单次请求45秒，模型客户端自动重试关闭。示例没有跨运行会话持久化、完整界面、生产错误文案或真实售后后端。
