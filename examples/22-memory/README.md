# 第22章：会话状态、短期记忆与长期偏好

配合[正文](../../22-助手怎样接着上一次对话继续处理.md)，检查“那这笔呢”怎样接到先前的A1001。默认全部离线，不需要API Key、订单服务或嵌入模型。

建议沿“手工保存历史 → 框架恢复同一会话 → 跨进程保存 → 状态字段进入提示 → 跨会话偏好 → 长历史摘要”阅读。每一步增加一个需求，各脚本是独立实验；正文前部的参考代码表可按问题定位入口。

## 实验与文件

| 文件 | 实际验证什么 |
| --- | --- |
| `manual_demo.py` | 普通Python字典维护历史，同一会话接续，另一会话没有前文；单独运行只用标准库 |
| `probe_model.py` | 记录实际模型输入，用规则检查其中的订单号和偏好，不联网、不理解自然语言 |
| `conversation_demo.py` | 真实Agent、InMemorySaver、同一thread两轮和另一thread一轮；打印实际输入，可选`--live` |
| `persistence_demo.py` | SqliteSaver读写本地检查点，分别运行seed和resume验证跨进程恢复 |
| `state_demo.py` | 相同状态字段，是否显式加入提示的对比；临时缩小模型视图而保留完整状态 |
| `preferences_demo.py` | 用户主动设置偏好，按运行时用户身份读取Store，换thread仍可读取，另一用户无该记录 |
| `summary_demo.py` | 摘要中间件达到阈值后调用固定摘要模型，更新当前消息列表 |
| `test_examples.py` | 13项检查，包括两个真实Python子进程 |

## 安装与运行

首次下载时，在准备保存项目的目录打开 PowerShell：

```powershell
git clone https://github.com/benx92/ai-learning-notes.git
cd ai-learning-notes
cd examples/22-memory
```

已有仓库时，从仓库根目录进入 `examples/22-memory`。在该目录的 PowerShell 中，用 Python 3.12：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manual_demo.py
.\.venv\Scripts\python.exe conversation_demo.py
.\.venv\Scripts\python.exe state_demo.py
.\.venv\Scripts\python.exe preferences_demo.py
.\.venv\Scripts\python.exe summary_demo.py
.\.venv\Scripts\python.exe -m unittest -v
```

直接依赖固定LangChain 1.4.6、langchain-core 1.6.10、LangGraph 1.2.16、langgraph-checkpoint 4.3.0、langgraph-checkpoint-sqlite 3.1.2、langchain-deepseek 1.1.1。后者仅供在线练习。

SQLite实验分两次启动进程，文件路径和thread要一致：

```powershell
.\.venv\Scripts\python.exe persistence_demo.py seed --db memory-demo.sqlite
.\.venv\Scripts\python.exe persistence_demo.py resume --db memory-demo.sqlite
```

seed成功后记录2条，resume成功后记录4条。该文件保留教学检查点，不会自动删除；再次seed已存在记录的同一会话会报错，可使用新文件名或两次均指定同一个新`--thread`值。SQLite连接会在每次命令结束时关闭。

## 应看到的关键区别

- 同一thread恢复前文，第二轮探针输入含系统要求、首轮用户消息、首轮模型回复与新问题；会话状态在第二轮结束后有4条消息。
- 系统要求在模型请求中，本例的常驻`messages`状态不包含这条注入的SystemMessage。
- 换thread不继承对话；创建新的InMemorySaver也没有旧记录。创建新Agent但复用同一Saver可以找回原thread。
- `state_demo.py`两组都保存A1001和4条消息，但临时只向模型传系统要求和最后一条用户消息。只有显式在提示中注入状态字段，探针才能找到订单号。
- 同一用户换thread后仍可读取偏好，但不会因此继承另一场会话的A1001。传入Store却不读取和注入时，探针看不到偏好。
- 摘要实验三轮结束消息数为2、4、4，摘要模型调用1次。当前状态压缩后，旧检查点仍可能保留原话。

正文补充的调用片段分别复用 `chat_with_history()` 与 `build_preference_agent()`；摘要创建函数也直接摘录 `summary_demo.py`。`save_active_order()` 在第一轮结束后写入字段，第二轮提示中间件再读取它，没有自动接入第21篇的抽取脚本。

## 在线练习

```powershell
$env:DEEPSEEK_API_KEY = "填写自己的密钥"
$env:LC_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe conversation_demo.py --live
```

只运行主会话实验：两轮相同thread，一轮新thread，正常路径3次生成请求。每次运行最多一次模型调用，单次请求超时45秒，客户端自动重试关闭，使用DeepSeek非思考模式配置。脚本不自动读取`.env`，不要把真实密钥写入源码。在线请求使用自己的服务额度；更换服务或模式时核对支持范围。

本次没有使用真实密钥请求线上模型，没有验证真实模型指代理解、摘要准确率或偏好遵从效果。

## 测试与实现边界

13项测试覆盖手工历史分离、复用模型对象不恢复前文、检查点恢复到实际输入、新thread与新Saver、缺thread配置、按消息ID合并、状态字段是否注入、状态候选来源检查、偏好跨thread与用户命名空间、仅传Store不生效、偏好更新删除、摘要触发和旧检查点、两个独立进程恢复SQLite。

2026-10-28 文字修订时，使用现有 Python 3.14.6、LangChain 1.3.9、langchain-core 1.4.7、LangGraph 1.2.5、langgraph-checkpoint 4.1.1，运行手工历史示例、核对摘要后的消息组成，并通过除 SQLite 跨进程恢复外的12项测试。当前缺少 Python 3.12 与 SQLite 检查点集成，未重跑该项测试，也未完成上述锁定版本环境的完整复验。源码摘录和下载包同步检查使用 Python 3.14 通过；未请求真实模型服务。

ProbeModel只读取本次传入的用户/系统消息，以规则寻找订单号。`seen_messages`仅记录输入用于核对，不参与生成。固定摘要则直接返回预先写好的SUMMARY，不能用于测试真实摘要质量。

会话状态实验只用于无工具对话。`latest_user_view`不是通用裁剪策略，也没有按Token预算裁剪。用户身份、会话归属校验、真实订单查询、工单写入、并发冲突、持久化Store、语义检索、摘要效果评估均未实现。内存Store只验证跨thread，不提供跨进程存储。详见[状态与存储扩展](../../supplements/22-Memory会话存储与状态扩展.md)。
