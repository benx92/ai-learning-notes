# 工具说明：并发请求中的ContextVar

两个请求分别处理甲、乙用户。若把`current_user`放进普通全局变量，甲设置后等待查询，乙覆盖为自己的身份，甲恢复时就可能读到乙。问题不是“变量写错”，而是两个并发调用共享了同一位置。

ContextVar让值跟随当前执行上下文，适合请求标识、日志关联和调用范围内的辅助信息。它不会认证用户，也不会让数据库自动按用户隔离。

## 为什么线程局部变量也可能不够

同一线程可以交替运行多个协程。`threading.local()`按线程区分，它们仍可能看到同一个线程局部值；ContextVar能够在协程任务的上下文中分别保存绑定。

| 方式 | 适合的位置 | 注意点 |
| --- | --- | --- |
| 显式传参 | 业务函数与可见依赖 | 参数可能层层传递 |
| 线程局部变量 | 纯多线程线程内信息 | 同线程多协程不独立 |
| ContextVar | 跨异步调用的请求信息 | 作用范围与继承需明确 |

核心业务可以继续显式接收用户。使用ContextVar不是把所有参数藏起来，而是在日志等横切调用中减少无关传参。

## set返回的Token用于恢复旧值

<!-- example-kind: usage -->
```python
from contextvars import ContextVar

request_id = ContextVar("request_id")
token = request_id.set("request-32")
try:
    print(request_id.get())
finally:
    request_id.reset(token)
```

`token`记录设置前的绑定，用于离开当前范围时恢复。嵌套调用设置临时值后，恢复的是外层原值，而不是统一清成空值。同一个Token不能重复使用，也不能随意跨上下文重置。

没有默认值、也尚未设置时，`get()`抛`LookupError`。对必须由请求入口提供的信息，这种失败可能比悄悄使用`anonymous`更容易发现问题。默认值应按实际语义选择。

## 用两个协程观察交错执行

配套[context_demo.py](../examples/23-32-assistant/context_demo.py)让两个协程分别绑定用户，主动让出执行，再读取自己的值，最后在`finally`恢复。

```powershell
python -X utf8 examples/23-32-assistant/context_demo.py
```

结果中每项`input`与`observed`一致，分别为alice和bob。`test_series.py`还检查协程完成后调用者没有残留绑定。

这个实验验证上下文传播，不连接订单系统。真实服务应先从登录会话取得身份，再进入上下文范围，业务函数仍检查资源归属。

## 创建任务时会带走哪一份值

asyncio创建任务时通常复制当前上下文绑定。若先设置甲再创建任务甲，随后设置乙再创建任务乙，它们可以继承不同值；如果先创建全部任务，再修改父上下文，不能期待已经创建的任务自动跟着变化。

后台任务可能比请求活得更久。让它隐式继承请求身份，容易在请求结束后继续使用过期授权。长期任务更适合显式保存任务、所有者和授权范围，执行时重新核验。

线程传播要按实际API检查。普通线程池提交不要一概假设自动继承，必要时每次用`copy_context()`取得独立副本，再调用`ctx.run(function)`。同一个Context不能同时被多个线程进入。`asyncio.to_thread`另有上下文传播语义，也不应与任意线程创建方式混同。

## 上下文绑定独立，不代表对象深拷贝

如果值是字典，复制上下文通常复制的是绑定，字典对象本身仍可能共享。两个任务对同一个字典执行原地修改，仍会互相影响。

因此请求ID、用户ID等优先使用不可变值，需要新数据时设置新对象，避免把模块级可变默认字典当作每个请求的新容器。

`copy_context()`也不是安全沙箱，不会隔离文件、数据库、网络或进程级变量。它只提供另一份上下文绑定环境。

## 接回日志与业务执行

日志函数可以从ContextVar取请求编号，使同一次请求的多层调用有共同关联。业务任务跨进程恢复时，则从持久任务记录重新建立可信运行上下文，不能指望旧ContextVar跨进程保存。

本系列退货图使用`Runtime[RequestContext]`显式传用户，和这里的ContextVar不是同一个接口。二者都应服从可信入口和归属检查，不能把上下文里有值当作授权证明。

## 参考资料

- [Python contextvars](https://docs.python.org/3/library/contextvars.html)
- [asyncio任务与线程](https://docs.python.org/3/library/asyncio-task.html)
