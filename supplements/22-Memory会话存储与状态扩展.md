# Memory会话存储与状态扩展

配合[第22章正文](../22-Memory短期记忆长期记忆和会话状态.md)。正文沿连续对话讲清保存与复用，以下保留较长实现和排查边界，完整脚本在[22-memory](../examples/22-memory/README.md)。

## 数据范围与存储寿命是两条轴

| 信息 | 本例存储 | 复用范围 | 进程退出后 |
| --- | --- | --- | --- |
| 手工消息历史 | Python字典 | 应用按conversation_id选择 | 不保留 |
| Agent消息与自定义字段 | InMemorySaver | 按thread_id恢复 | 不保留 |
| 同一Agent状态 | SqliteSaver | 按thread_id恢复 | 文件存在且连接正确时可恢复 |
| 用户主动设置的回复风格 | InMemoryStore | 按用户namespace跨thread读取 | 不保留 |

长期记忆在本章指跨会话使用，并非某种自动永久保存的模型内部能力。持久化检查点也不会自动持久化Store；正式系统要分别选择实现。

## 模型输入探针怎样避免假装记住

`manual_demo.py: probe_reply()`只在这次传入的用户和系统内容中提取A加4位数字；对模型回复中的订单号不再次采信。它不使用以前调用的隐藏变量。

`ProbeModel`把消息转换后调用相同规则。`seen_messages`记录实际收到的输入，便于断言历史是否真的交回模型；模型没有从记录列表读取订单。摘要实验用`fixed_reply`返回固定摘要，只验证中间件机制，不能作为摘要质量证明。

复用模型对象与保存会话是不同的事。测试使用同一个ProbeModel先接收A1001，再单独接收“那这笔呢”，后一次依然找不到订单；恢复历史后才有依据。

## SQLite跨进程示例的资源与恢复范围

`persistence_demo.py: run_phase()`完整实现如下，文件已导入SqliteSaver、创建Agent函数、固定输入与ProbeModel：

<!-- example-source: examples/22-memory/persistence_demo.py -->

```python
def run_phase(database_path, phase, thread_id="restart-demo"):
    config = {"configurable": {"thread_id": thread_id}}
    with SqliteSaver.from_conn_string(database_path) as checkpointer:
        agent = build_agent(ProbeModel(), checkpointer)
        previous = agent.get_state(config).values.get("messages", [])
        if phase == "seed" and previous:
            raise ValueError("该会话已有记录，请使用新的数据库路径或thread_id")
        if phase == "resume" and not previous:
            raise ValueError("该会话没有记录，请先运行seed")
        if phase not in {"seed", "resume"}:
            raise ValueError("phase必须为seed或resume")
        text = FIRST if phase == "seed" else FOLLOWUP
        result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config=config)
        return {"reply": result["messages"][-1].content, "messages": len(result["messages"])}
```

检查点连接的上下文管理器在函数返回时关闭资源。Agent创建与调用都在连接有效期间；不能在退出`with`之后继续使用依赖这条连接的对象。

测试用临时目录启动seed、resume两个独立Python进程，核对消息数2变4及订单号A1001。人工运行的文件则会保留，脚本不会清空已有历史。此实验验证已完成一轮之后的恢复，没有验证外部业务写入执行到一半崩溃时的幂等与补偿。

`get_state(config)`返回状态快照，`values`是当前字段；`next`描述待执行节点。本例结束后`next`为空，表示没有待运行节点，不代表退款业务已经完成。历史快照可通过`get_state_history(config)`观察。

## 为什么保存字段还要显式读取

`state_demo.py`使用以下模型视图处理，仅保留最新用户消息供模型读取，但不改写已保存的消息列表：

<!-- example-source: examples/22-memory/state_demo.py -->

```python
@wrap_model_call
def latest_user_view(request, handler):
    latest = next(m for m in reversed(request.messages) if isinstance(m, HumanMessage))
    return handler(request.override(messages=[latest]))
```

固定或动态系统要求由调用机制另行组织，所以ProbeModel实际仍收到system、human两条。此处理只为展示状态与模型输入可以不同。若有工具调用、没有用户消息或需要保留多轮推理，就不能直接照搬。

`save_active_order()`先验证格式与文本来源，再用`agent.update_state()`保存选定订单。它不会调用模型。文本来源不等于订单授权，示例也未验证用户真实身份；正式应用还要决定订单选择如何确认、切换和清除。

LangChain的AgentState与自定义TypedDict描述数据字段，不应当作对任何外部输入的完整业务校验。需要的验证仍应放在写入路径。

## 长期偏好是显式读写策略

本例将单项回复风格作为一个独立key。重新put同一个key会替换该记录，删除使用store.delete；由于没有把其他偏好塞进同一value，这个例子不涉及跨字段合并。

如果后续换成整份用户档案，应明确未提及、修改、清空和删除的差别；普通读改写也不能自动解决两个并发请求覆盖彼此的修改。正式存储还需要合适的一致性策略。

Viewer.user_id由应用传入运行时context，提示中间件据此拼接namespace。它不从用户聊天文字或模型工具参数里决定身份。当前测试只验证不同namespace的选取，不提供会话归属校验、认证或访问控制系统。

命名空间和thread_id都只是定位信息。即使偏好读取正确，给另一个用户传错旧thread仍可能取到旧消息；这需要应用在进入Agent前统一验证关联关系。

## 摘要实验的触发与实际状态

`summary_demo.py`的创建函数如下；同文件导入了create_agent、SummarizationMiddleware、InMemorySaver与BASE_PROMPT：

<!-- example-source: examples/22-memory/summary_demo.py -->

```python
def build_summary_agent(model, summary_model):
    summarizer = SummarizationMiddleware(
        model=summary_model,
        trigger=("messages", 4),
        keep=("messages", 2),
        summary_prompt="只保留继续售后对话所需的信息，不添加事实。对话：{messages}",
        trim_tokens_to_summarize=None,
    )
    return create_agent(
        model=model, tools=[], system_prompt=BASE_PROMPT,
        checkpointer=InMemorySaver(), middleware=[summarizer],
    )
```

首次模型调用前1条消息，第二次前3条，第三次前5条。第三次达到阈值后执行一次摘要，最终当前消息列表4条，不再是未压缩路径的6条。中间件可能添加摘要包装文字，不能假定摘要消息的每个字符都来自自定义提示。

条数阈值只方便本地观察，不适合直接代替真实Token预算。长文、图文和工具结果大小差异很大，正式策略应为系统要求、工具说明、模型输出和必要历史保留余量。

摘要更新当前状态，但旧检查点仍可留有原始消息。删除某个Store键、删除当前状态中的消息、删除检查点历史和清理其他副本，是不同操作。本例没有实现全链路数据清理或保留期限。

## 参考资料

- [LangChain短期记忆](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain长期记忆](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [运行时Context](https://docs.langchain.com/oss/python/langchain/runtime)
- [上下文组织](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [检查点实现](https://reference.langchain.com/python/langgraph/checkpoints/)
