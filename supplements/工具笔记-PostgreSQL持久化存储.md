# 工具说明：应用里的PostgreSQL持久化

本地SQLite实验能说明重启恢复，但当多个应用实例需要访问同一份数据时，需要明确数据由谁管理、怎样连接、并发写入遵循什么规则。PostgreSQL是独立运行的数据库服务，Python驱动是连接它的客户端，二者不是同一个软件。

这里围绕申请记录、检查点与长期记忆介绍最小读写，不把数据库运维扩成新的学习阶段。综合案例仍默认使用SQLite；以下PostgreSQL脚本是可选实验，未在本次环境连接服务器执行。

## 先分清三类数据

| 数据 | 用途 | 常见访问方式 |
| --- | --- | --- |
| 订单、草稿、申请 | 可信业务事实与写入结果 | 业务表与事务 |
| 图检查点 | 执行状态和恢复位置 | `PostgresSaver` |
| 长期记录 | 跨会话偏好与事实 | 业务表或`PostgresStore` |

同一数据库里可以保存三类数据，但它们的Schema、主键、保留策略与访问权限不同。保存检查点不等于自动保存所有业务表，也不会让旧偏好永远正确。

## 连接、库表和类型怎样理解

数据库包含表，表包含记录和字段。连接串说明主机、端口、库、账号与连接选项。密码属于凭证，放到环境或受控配置，不写进公开文章和日志。

常用字段可以采用：稳定编号用文本或UUID，时间用`TIMESTAMPTZ`，状态用带约束的文本，金额用明确精度的数值或最小货币单位整数。`JSONB`适合保存可变结构，但不代替关键字段的唯一、非空与业务约束。

例如申请去重需要`request_id PRIMARY KEY`。数据库会拒绝相同键的重复记录，这比每个调用方各自“先查一下”更可靠。规则仍要与操作语义匹配，不能给不相关动作错误复用同一个键。

## 先验证连接，再验证业务

安装服务可参考[官方下载说明](https://www.postgresql.org/download/)。已有练习库时，用`psql`连接，核对实际库名与版本：

```powershell
psql -h localhost -p 5432 -U tutorial_user -d tutorial_db
```

进入后可执行`SELECT version();`，用`\dt`查看表，用`\d tutorial_applications`查看结构，`\q`退出。反斜杠命令属于psql客户端，不是发给数据库的通用SQL。

连接拒绝先看服务与端口，认证失败看账号和配置，找不到表看当前库、Schema和初始化，不能一律修改SQL语法。数据库数据寿命取决于服务数据目录或持久卷，不取决于Python对象是否仍在。

## 参数化查询与事务一起使用

可选脚本[postgres_demo.py](../examples/23-32-assistant/postgres_demo.py)使用Psycopg 3。安装驱动后，设置`DATABASE_URL`指向独立练习库，再执行：

```powershell
python -m pip install "psycopg[binary]"
python -X utf8 examples/23-32-assistant/postgres_demo.py request-1 A3003
python -X utf8 examples/23-32-assistant/postgres_demo.py request-1 A3003
```

脚本会创建名为`tutorial_applications`的教学表并保留记录，第二次应返回相同编号并标记复用。该表只演示请求去重，不校验订单资格，也不连接真实申请服务。

Psycopg使用`%s`占位，值单独传入，不能用字符串拼接或给占位符加引号。表名与列名不是普通值，需要动态标识符时使用驱动提供的标识符组合功能。

`with psycopg.connect(...)`正常退出时提交，异常时回滚并关闭连接。注意这与标准库`sqlite3.Connection`上下文不自动关闭连接的语义不同，不能把不同驱动的清理规则照搬。

## 冲突处理怎样形成去重结果

脚本先`INSERT ... ON CONFLICT(request_id) DO NOTHING RETURNING application_id`，再按同一请求查询既有记录，并核对订单和所有者。相同编号对应不同输入会抛错，不把另一笔记录当作本次成功。

在默认Read Committed隔离下，单条插入可能因另一个事务的唯一键结果而跳过；后续查询使用新的语句快照。不要假设一条复杂查询里“插入失败后必然能从旧快照找到竞争行”，也不要把任何隔离级别都当成同样行为。

若流程还要更新订单的已申请状态，应在同一业务事务内锁定或条件更新相关记录，建立合适唯一约束。调用外部服务不自动加入本地事务，需要外部幂等键、结果查询或补偿机制。

任务认领可以用带状态条件的`UPDATE ... RETURNING`判断谁成功。复杂队列还可能使用行锁与`SKIP LOCKED`，但要处理失联、重试和租约，不能只增加一个锁就宣称整个任务系统可靠。

## 索引、查询计划与连接池

主键和唯一约束通常有对应索引。按所有者和状态频繁查任务时，可以考虑相应组合索引；每增加索引也增加写入和存储成本，不能把所有字段都索引一遍。

用`EXPLAIN`观察计划，必要时在练习环境用`EXPLAIN ANALYZE`观察实际执行。后者会真正运行语句，对写操作尤其不能当作纯查看。小表使用全表扫描并不自动表示索引失效，优化器会考虑代价。

连接池复用昂贵连接并限制数量，不会消除事务冲突，也不让任意多个请求安全共享一个正在使用的连接。业务事务应短小，避免持锁等待模型回复或人工批准。

## 框架检查点与Store怎样接入

安装相应PostgreSQL集成后，可通过`PostgresSaver.from_conn_string`与`PostgresStore.from_conn_string`取得相应对象，首次使用分别调用`setup()`完成表结构初始化。正式服务通常把迁移作为明确的部署步骤。

编译图时传入`checkpointer`与`store`，运行时用稳定`thread_id`恢复检查点，长期记录则按可信用户命名空间读取。二者不能互相替代。

集成对象的连接与生命周期必须覆盖图的实际调用，不能退出连接上下文后继续使用图。自己提供连接池时，还要按集成版本核对自动提交、行工厂等连接要求。

本例没有安装并运行PostgresSaver或PostgresStore，也没有把切换数据库等同于完成生产部署。实际迁移应验证两个进程恢复、重复写入、事务回滚、归属隔离与备份恢复。数据库保存的是明确的数据与约束，不会替程序补齐尚未设计的业务语义。

## 参考资料

- [PostgreSQL INSERT与ON CONFLICT](https://www.postgresql.org/docs/18/sql-insert.html)
- [事务隔离](https://www.postgresql.org/docs/18/transaction-iso.html)
- [Psycopg参数绑定](https://www.psycopg.org/psycopg3/docs/basic/params.html)
- [Psycopg事务](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [LangGraph数据库记忆](https://docs.langchain.com/oss/python/langgraph/add-memory)
