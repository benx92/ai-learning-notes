# 第15篇：退款状态工具调用示例

这是文章《Function Calling 和 ToolCall：让模型从回答走向行动》的配套代码。正文用短片段解释消息往返与申请阶段；完整查询脚本是 `tool_demo.py`，完整申请服务是 `return_demo.py`。不要拼接正文代码块或把两个脚本拼成一个文件。逐段实现说明保留在仓库的 `supplements/15-工具调用实现与排查.md` 中。

使用 Python 3.10 或更新版本，仅依赖标准库。`tool_demo.py` 默认离线，不读取密钥，不请求外部服务，订单都是虚构教学数据。另一个独立文件 `return_demo.py` 演示申请草稿、确认与本地记录创建；两者都不连接真实登录、订单或退款系统。

在当前目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe tool_demo.py
.\.venv\Scripts\python.exe tool_demo.py "查一下退款状态"
.\.venv\Scripts\python.exe tool_demo.py "查一下订单A2002的退款状态"
```

默认查询A1001返回“审核中”；没有订单号则询问；A2002属于另一个教学用户，不返回其状态。离线模式用固定规则替代模型，只验证消息往返，不代表自然语言理解效果。

可选在线模式会请求 DeepSeek，产生 API 费用；仍然执行本地虚构订单查询。自己设置凭据，不要把实际密钥提交仓库。模型名称以当前账号可用列表为准。

```powershell
$env:DEEPSEEK_API_KEY = "替换为你自己的密钥"
$env:DEEPSEEK_MODEL = "填写账户可用且支持工具调用的模型名"
.\.venv\Scripts\python.exe tool_demo.py --live "查一下订单A1001的退款状态"
```

最多执行3轮工具请求，每轮最多4个调用，再用一轮禁止调用工具的请求收尾。在线模式使用非思考、非流式 Chat Completions，HTTP等待上限45秒，不自动重试。

本地验证：

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

测试覆盖参数与身份边界、离线消息链、多调用配对、异常ID和执行预算。未进行使用真实密钥的在线请求；测试不代表生产验收。真实系统需要由认证会话提供用户身份、接入后端，并控制日志中的业务数据。

## 退货申请的独立演示

```powershell
.\.venv\Scripts\python.exe return_demo.py
```

使用新虚构订单A3003：会员、非定制品、签收10天、尚未申请。先显示草稿和未确认提交的拒绝结果；输入“确认提交”才创建本地内存记录，其他输入取消。重复提交沿用同一草稿编号，返回相同申请编号，记录数量为1。记录随进程退出消失，不是持久化业务系统。

`prepare_return_application` 接受订单号和原因；`submit_return_application` 只接受草稿编号。确认函数不暴露为模型工具，演示用户身份由应用传入。提交会复查条件并检查5分钟有效期。在线查询主脚本没有自动注册这些写入工具；本例用固定工具请求说明业务状态流转。

新增测试覆盖未确认、错误身份、额外确认参数、过期、规则不符、条件变化和重复提交。完整测试仍使用上面的 `python -m unittest -v` 命令。
