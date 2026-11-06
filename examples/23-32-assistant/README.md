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
| `long_task_demo.py` | 28的标准库独立入口：固定超时、记录保存、事实找回与汇总交接 |
| `background_demo.py` | 29的标准库独立入口：后台协作取消、到期实例、固定核对结果与消费确认 |
| `wait_variants.py` | 25的静态断点与并行中断ID映射实验，不办理业务 |
| `stream_demo.py` | 26的逐条事件消费、内存暂停与取消、受控失败；不依赖SQLite检查点集成 |
| `assistant.py` | 32的完整命令入口，以及可选真实模型聊天 |
| `context_demo.py`、`rich_demo.py`、`postgres_demo.py` | 四篇工具说明的相关实验 |
| `test_series.py` | 程序行为检查，含真实子进程恢复 |

程序按仓库目录关系导入`../15-tool-calling/return_demo.py`、`../13-rag/loader.py`、`rag.py`和`refund-policy.md`。单独复制本目录会缺少这些文件。下载[配套包](../23-32-example.zip)时保留目录结构，从包内`examples/23-32-assistant`运行。

## 准备环境

首次使用时，先取得完整仓库：

```powershell
git clone https://github.com/benx92/ai-learning-notes.git
cd ai-learning-notes
```

在仓库根目录执行，使用Python 3.12或更高版本。建议独立环境：

```powershell
py -3.12 -m venv .venv-series
.\.venv-series\Scripts\python.exe -m pip install -r examples/23-32-assistant/requirements.txt
.\.venv-series\Scripts\python.exe -X utf8 -m unittest discover -s examples/23-32-assistant -p test_series.py -v
```

以下命令中的`python`指这个环境的解释器，可激活环境或改为完整路径。默认不自动读取`.env`；可选在线路径从当前进程环境读取配置。不要将密钥写入脚本、文章或版本库。

固定依赖为LangChain 1.4.6、langchain-core 1.6.10、LangGraph 1.2.16、langgraph-checkpoint 4.3.0、SQLite集成3.1.2与langchain-deepseek 1.1.1。不同版本的流事件形状可能变化。

## 逐个观察机制

阅读第23篇时，先运行 `state` 即可。正文依次对照 `flow.py` 中的入口与状态定义、节点返回值、字段合并和注册连边；使用 `build_flow(..., approval=False)`，在草稿准备后结束。`check()` 重新读取业务记录，不直接以 `facts` 快照或调用方传入的通过标记作资格依据。A3004 的拒绝路径没有 `draft`，读取结果时应先判断 `stage`。

阅读第24篇时运行 `routing`：先看 `flow.py` 中资格结果怎样选择出口，再看 `routing.py` 的 `retry_graph()`、`batch_graph()`。前者用预设失败次数模拟重查，不发送网络请求；后者逐项读取本地订单规则，不自动给每项嵌入重试。正文提供独立调用片段，覆盖空列表、单项、重复订单与未知订单；`results` 是收集区，`ordered` 是排序和位置检查后的交付结果。正常批量核对不创建草稿或申请。

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

第26篇还提供独立入口，在本目录运行 `python -X utf8 stream_demo.py`。它逐条打印 `updates` 与 `custom`，使用内存检查点观察草稿后的等待，再用固定教学选择取消，最后演示先发进度再抛受控错误。每次运行使用临时业务数据，不创建申请；同一进程内暂停恢复不代表跨进程持久恢复。`experiments.py stream` 则先收集完整输出再统一打印，适合报告核对，二者展示方式不同。

流输出沿用默认 v1 接口：多模式列表产生 `(mode, data)`，单模式直接产生该模式数据；不要与官方文档显式 `version="v2"` 的统一字典形式混用。`application_error` 是脚本捕获错误后生成的展示记录，不是框架流模式。真实模型Token分片、网页重连与事件持久重放均未在此入口实现。

技能加载实验只展示实际输入和工具范围，不宣称已经自动接入聊天主循环。第28篇可单独运行 `python -X utf8 long_task_demo.py`，只需Python标准库；`experiments.py long-task`复用同一函数。它以A3003固定教学响应模拟前两次超时，记录等待[1,2]但不实际休眠；将响应重复100次保存为6000字符日志，记住退货原因，再重开任务表、读回校验日志并保存汇总。最终check与summary均completed，没有创建业务草稿或申请，没有真实自动摘要或模型记忆提取。临时产物在脚本结束后清理；任务表不实现失联执行者回收或完整崩溃恢复。

第27篇也可独立观察：在仓库根目录执行 `python -X utf8 -i examples/23-32-assistant/harness.py`，再运行正文的 `assemble_request()` 对照片段。`harness.py` 只依赖标准库，不需要完整框架环境；对照政策查询、申请查询、申请准备、空授权及未知名称。这个入口不查询订单、不办理业务，也不验证模型自主选择说明。原 `experiments.py skills` 入口仍需要本 README 的完整依赖。

第29篇可单独运行 `python -X utf8 background_demo.py`，只需Python标准库；`experiments.py background`导入同一个实验函数，但仍要求完整框架依赖。先用开始信号与停止事件观察运行中取消，`completed`仅表示函数正常返回，`record_created=false`说明未交付核对记录。随后用99、100、100扫描固定间隔计划，重开数据库并消费首次实例，将A3003和“尺寸不合适”的固定响应与计划、到期时刻、执行编号关联，成功后确认。160产生第二次实例，取消计划后待处理实例为空。没有真实查询、模型、网页输入或常驻调度器；输入映射和核对结果仅在内存，不能据此推断崩溃后完整恢复。调度类不提供多消费者认领，确认前还需在产品中可靠保存结果。

2026-11-06 使用已有Python 3.12.13运行29的标准库独立入口，状态与实例交接符合正文；抽取并独立执行既有后台取消、调度重开去重两项测试，通过。当前环境缺少LangGraph，综合实验入口及整份共享测试模块导入失败，未安装依赖，未将全套检查标为本轮通过。

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

在本目录运行 `python -X utf8 wait_variants.py` 可观察静态断点与并行中断的部分恢复。运行 `python -X utf8 stream_demo.py --events` 或 `--sse` 可观察规范化事件及SSE报文：等待以paused结束，取消以done结束，故障以error结束且没有done。只演示内存恢复与报文打印，没有HTTP服务、真实模型、子图或持久事件去重。

## 检查与阅读范围

2026-11-02 补读参考网站 LangGraph 的检查点与中断、高级流式、产出审批流三节正文后，按实际缺口补强25—26篇，并增加wait_variants.py与stream_demo.py的事件协议入口。Python 3.14.6现有环境执行通过静态断点、并行ID恢复与部分待办核对，以及paused/done/error唯一终止和SSE格式检查。保持A3003、草稿300秒、人工确认后仅创建待审核申请等既有约束；未移植来源的金额审批或邮件发送业务。以下“未读取原文”的旧记录仅描述补读之前的写作批次。

2026-11-02 续写第26篇：补齐节点增量与全量状态对照、默认v1解包、等待确认与失败展示，新增 `stream_demo.py` 并复用 `Business` 和 `build_flow()`，未改变既有业务实现或依赖。实际用 Python 3.14.6、LangGraph 1.2.5、langgraph-checkpoint 4.1.1 运行新增入口，确认等待 `review`、取消后申请数均为0，故障按 `checking → application_error` 展示；另订阅四种模式，得到四个节点更新、五个状态快照、最终 `draft_ready`、模型事件0。通过Context7官方文档核对流接口；未重跑完整共享测试、锁定依赖环境、SQLite持久恢复或真实模型流，也未验证网页与博客最终渲染。

2026-11-02 续写第25篇：沿用 A3003，补齐检查点接入、读取与恢复调用、中断重入和批准后路径，明确300秒过期后图结束为失败，需要新任务重新准备。未修改业务实现或依赖。使用 Context7 官方文档和现有源码核查；在 Python 3.14.6 上验证业务数据库重读、草稿复用、重复提交返回同一申请（申请数1）、身份拒绝和任务输入绑定。默认环境与现有 Python 3.12.13 虚拟环境缺少 `langgraph-checkpoint-sqlite`，未自动安装依赖，未重跑两进程图恢复、取消与过期的共享测试。正文命令为预期行为，历史全套测试记录仍按原日期理解；未核验在线模型、课程覆盖或最终发布渲染。

2026-10-27对第23篇做局部阅读修复：正文补齐入口字段、共享源码与运行入口，区分一次运行内的状态更新和跨进程恢复；未更改业务实现。已复跑`test_23_updates_and_input_filter`与`test_rejected_input_cannot_fake_pass`两项检查，通过成功路径、输入字段过滤及拒绝后不准备草稿的核对。此轮不替代下方历史全套检查，也不将24—32稿件标为写作验收完成。

2026-10-28 再次修订第23篇：补充办理任务的背景、实际节点与连边摘录、成功与拒绝结果对照。使用现有 Python 3.14.6、LangGraph 1.2.5、langgraph-checkpoint 4.1.1，直接运行 `Business` 与 `build_flow(..., approval=False)`，核对 A3003 的草稿路径、A3004 的拒绝路径，以及夹带通过标记不改变拒绝结果；两条路径申请数均为0。当前缺少 Python 3.12 和 SQLite 检查点集成，未重跑依赖该集成的共享测试与 `experiments.py` 入口，也未复验锁定依赖环境；本次不更改业务源码。

2026-10-28 续写第24篇：在同一现有环境直接运行 `retry_graph()` 与 `batch_graph()`，核对预设失败次数0、2、8分别在1、3、3次后得到 `done`、`done`、`failed`，以及故意将 `recursion_limit` 设为1后触发 `GraphRecursionError`。批量核对覆盖空列表、单项、`["A3003", "A3004", "missing", "A3003"]`，确认位置、订单号、资格与错误原因对应，申请数为0。未更改业务实现，未重跑共享完整测试或锁定依赖环境；本次验证的是离线控制流，不包含真实模型、网络异常恢复或并行性能。

行为检查覆盖状态更新、入口字段过滤、规则拒绝、重试上限、空批次、重复订单、消息来源、两进程恢复、取消、过期、身份、去重、任务依赖、认领竞争、记忆归属、输出保存、后台协作取消、调度账本、协议校验与请求上下文。

同步检查在仓库根目录运行`python -X utf8 examples/check_article_sync.py`。它校验源码摘录、JSON与下载包，不验证模型理解、外部接口或数据库部署。

本次在Python 3.12.14上通过21项行为检查、8个独立实验及Rich 15.0.0展示实验；配套包独立解压后再次通过21项检查。机器可读记录见[verification.json](verification.json)。完整仓库的同步检查不包含在精简下载包中。
