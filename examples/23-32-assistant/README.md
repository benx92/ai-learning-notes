# 23—32篇共享售后助手与机制实验

这里保存正文使用的实际程序。默认离线，不需要API Key，不调用真实模型，不连接真实电商，不发送消息或退款。订单、政策和申请均为教学数据。

## 文件与文章

| 位置 | 内容 |
| --- | --- |
| `business.py` | 复用15篇`ReturnService`，用SQLite事务保存教学记录 |
| `flow.py` | 23、25、26的任务状态、原因追问、持久审批、事件 |
| `routing.py` | 24的条件、有界重查、动态派发与完整汇总 |
| `harness.py`、`skills/` | 27—29的按需说明、任务表、输出与记忆、后台和时间账本 |
| `delegation.py` | 30的真实框架专家工具与单助手基线 |
| `team.py` | 31的持久消息与关联协议 |
| `experiments.py` | 每个主题的独立离线运行入口 |
| `assistant.py` | 32的完整命令入口，以及可选真实模型聊天 |
| `context_demo.py`、`rich_demo.py`、`postgres_demo.py` | 四篇工具说明的相关实验 |
| `test_series.py` | 程序行为检查，含真实子进程恢复 |

程序按仓库目录关系导入`../15-tool-calling/return_demo.py`、`../13-rag/loader.py`、`rag.py`和`refund-policy.md`。单独复制本目录会缺少这些文件。下载[配套包](../23-32-example.zip)时保留目录结构，从包内`examples/23-32-assistant`运行。

## 准备环境

在仓库根目录执行，使用Python 3.12或更高版本。建议独立环境：

```powershell
py -3.12 -m venv .venv-series
.\.venv-series\Scripts\python.exe -m pip install -r examples/23-32-assistant/requirements.txt
.\.venv-series\Scripts\python.exe -X utf8 -m unittest discover -s examples/23-32-assistant -p test_series.py -v
```

以下命令中的`python`指这个环境的解释器，可激活环境或改为完整路径。默认不自动读取`.env`；可选在线路径从当前进程环境读取配置。不要将密钥写入脚本、文章或版本库。

固定依赖为LangChain 1.4.6、langchain-core 1.6.10、LangGraph 1.2.16、langgraph-checkpoint 4.3.0、SQLite集成3.1.2与langchain-deepseek 1.1.1。不同版本的流事件形状可能变化。

## 逐个观察机制

进入`examples/23-32-assistant`后执行：

```powershell
python -X utf8 experiments.py state
python -X utf8 experiments.py routing
python -X utf8 experiments.py stream
python -X utf8 experiments.py skills
python -X utf8 experiments.py long-task
python -X utf8 experiments.py background
python -X utf8 experiments.py delegation
python -X utf8 experiments.py team
```

每项实验使用自己的临时目录并在结束后清理，不更改实际订单或其他项目。`stream`还会演示部分进度后受控失败。`delegation`用固定响应模型运行真实Agent框架，当前脚本基线2次、委派组6次模型函数调用，不能据此推断真实效果或普遍成本。`team`是两个固定线程执行者，不是两台真实模型。

技能加载实验只展示实际输入和工具范围，不宣称已经自动接入聊天主循环。长任务实验把计划、输出保存、记忆与有限恢复连在同一工作项中；没有真实自动摘要或模型记忆提取。

## 完整售后流程

在本目录运行：

```powershell
python -X utf8 assistant.py --data ./data/my-reading policy "会员签收10天能退货吗"
python -X utf8 assistant.py --data ./data/my-reading order A3003
python -X utf8 assistant.py --data ./data/my-reading start request-1 A3003
python -X utf8 assistant.py --data ./data/my-reading resume request-1 --reason "尺寸不合适"
python -X utf8 assistant.py --data ./data/my-reading show request-1
python -X utf8 assistant.py --data ./data/my-reading resume request-1 --action approve
```

最后一条也可以选择`--action cancel`，二者是替代动作。确认入口先显示当前草稿；批准只创建本地待审核申请。重复确认返回已有业务结果，不新增申请。

每条命令都是新进程，恢复依赖相同数据目录和任务编号。草稿有效期300秒，等待过久返回`draft_expired`，不自动延长旧授权。已经申请的订单不能再次准备新的申请；重做实验请选新的练习数据目录，保留旧数据以便核对。

`--user`只模拟本地身份，真实服务必须从登录态取得用户。其他身份不能读取或恢复已有任务。相同任务编号不可替换输入。

数据目录包含：

- `business.sqlite`：教学订单、草稿、申请与任务归属。
- `checkpoints.sqlite`：运行状态、暂停与恢复位置。
- `events.jsonl`：任务、操作、阶段及错误类别。

同一任务的图调用按顺序执行。本例没有支持多个进程同时无约束地恢复同一任务；业务幂等不等于图并发协调。

## 可选真实模型与语义检索

真实聊天设置`DEEPSEEK_API_KEY`和`LC_CHAT_MODEL`，再运行：

```powershell
python -X utf8 assistant.py --data ./data/online chat
```

这会按账户实际模型计费。模型可以查证据、查单、建立准备任务、补充原因，没有批准工具。根据它返回的任务编号，使用独立`show`与`resume --action`入口确认或取消。输入`/exit`结束聊天。

聊天消息只存内存，业务任务持久。在线工具选择与真实回答质量未由本次离线测试验证，遇到提供商错误应先检查实际配置和权限。

默认政策检索为确定性关键词匹配，结果标为`evidence_only`，不冒充向量检索或生成回答。加`--vector`会调用原13篇`Pipeline`，需另装`../13-rag/requirements.txt`及准备嵌入模型；加`--online-policy`会调用原生成服务，另需`RAG_CHAT_MODEL`。例如：

```powershell
python -X utf8 assistant.py --data ./data/vector --vector --online-policy policy "会员签收10天能退货吗"
```

这两个可选路径没有在本次交付中下载模型或请求在线服务。完整引用由原`pack_context`生成，证据不足时不调用生成器。

## 工具说明实验

`context_demo.py`只用标准库。Rich为可选依赖，运行`python -m pip install rich`后执行`rich_demo.py`。PostgreSQL需自己准备独立练习库及`DATABASE_URL`，安装`psycopg[binary]`后按正文运行；它会创建并写入教学表，本次未连接数据库执行。

worktree说明提供练习命令，没有自动操作当前仓库。PostgreSQL集成与工作区命令查过文档，不能因此标为已实测数据库或仓库变更。

## 检查与阅读范围

行为检查覆盖状态更新、入口字段过滤、规则拒绝、重试上限、空批次、重复订单、消息来源、两进程恢复、取消、过期、身份、去重、任务依赖、认领竞争、记忆归属、输出保存、后台协作取消、调度账本、协议校验与请求上下文。

同步检查在仓库根目录运行`python -X utf8 examples/check_article_sync.py`。它校验源码摘录、JSON与下载包，不验证模型理解、外部接口或数据库部署。

本次在Python 3.12.14上通过21项行为检查、8个独立实验及Rich 15.0.0展示实验；配套包独立解压后再次通过21项检查。机器可读记录见[verification.json](verification.json)。完整仓库的同步检查不包含在精简下载包中。
