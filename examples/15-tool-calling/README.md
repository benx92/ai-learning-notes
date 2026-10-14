# 第15篇：退款状态工具调用示例

这是文章《Function Calling 和 ToolCall：让模型从回答走向行动》的完整脚本。文章中的 Python 代码块按顺序连接，与 `tool_demo.py` 一致。

使用 Python 3.10 或更新版本，仅依赖标准库。默认离线，不读取密钥，不请求外部服务。两个订单都是虚构教学数据；没有真实登录、退款或申请提交功能。

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
$env:DEEPSEEK_MODEL = "deepseek-flash"
.\.venv\Scripts\python.exe tool_demo.py --live "查一下订单A1001的退款状态"
```

最多执行3轮工具请求，每轮最多4个调用，再用一轮禁止调用工具的请求收尾。在线模式使用非思考、非流式 Chat Completions，HTTP等待上限45秒，不自动重试。

本地验证：

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

测试覆盖参数与身份边界、离线消息链、多调用配对、异常ID和执行预算。未进行使用真实密钥的在线请求；测试不代表生产验收。真实系统需要由认证会话提供用户身份、接入后端，并控制日志中的业务数据。
