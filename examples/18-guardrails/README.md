# 第18章：调用包装与拦截实验

两个独立实验只使用Python标准库，不调用模型或业务服务，也不创建退货申请。

```powershell
py -3.12 confirmation_demo.py
py -3.12 middleware_order_demo.py
```

- `confirmation_demo.py`对应正文：未确认的请求只打印开始、结束与拒绝结果；确认分支才打印“进入业务函数”。布尔值由教学代码提供，实际确认必须读取受信任的记录。
- `middleware_order_demo.py`对应扩展说明：允许的查询执行，未知工具在业务函数之前被拒绝；外层日志保留两条路径。

两份实验的检查目的不同，分别保留，不把它们当作完整LangChain中间件或持久审批系统。实际草稿确认、归属、过期和防重复逻辑见[第15章申请服务](../15-tool-calling/return_demo.py)。第19章的[Agent配置](../19-langchain/agent_demo.py)另有框架调用限额。
