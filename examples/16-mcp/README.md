# 第16篇：MCP售后服务示例

使用Python 3.12。固定官方SDK `mcp==1.26.0` 和配置依赖 `pydantic-settings==2.12.0`，本例协商的协议版本为2025-11-25。官方SDK已有2.x接口；请按本文固定环境运行，不混用不同版本的代码。

所有数据都是虚构教学资料。服务仅绑定本机127.0.0.1，身份固定为演示用户，没有真实登录、订单、退货申请或支付功能。没有在线模型请求，不需要模型密钥。

## 文件用途

| 文件 | 用途 |
| --- | --- |
| server.py | 一个工具、一个固定资源、一个资源模板、一个提示模板 |
| client.py | 通过stdio启动服务，逐项检查各种能力 |
| http_client.py | 连接已经运行的HTTP服务，重复相同检查 |
| bridge_demo.py | 工具格式转换、固定请求转发、模型调用ID回填 |
| test_protocol.py | 使用实际子进程和本机HTTP的协议检查 |

## 安装与本地运行

在当前目录打开PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe client.py
.\.venv\Scripts\python.exe bridge_demo.py
```

客户端会自动启动旁边的server.py，退出时关闭子进程。不要提前单独启动stdio服务；不要在服务的标准输出中打印普通日志。

应看到工具get_refund_status、政策概览和客户类型资源模板、提示explain_refund。A1001返回“审核中”；A2002没有可访问记录，业务结果ok=false；bad-id的工具执行isError=true。

## HTTP运行

终端一：

```powershell
.\.venv\Scripts\python.exe server.py --transport streamable-http
```

终端二（同一目录）：

```powershell
.\.venv\Scripts\python.exe http_client.py
```

地址是http://127.0.0.1:8765/mcp。结束后在终端一按Ctrl+C关闭服务。服务没有远程认证，不应直接作为公网业务服务部署。

## 验证

先关闭8765端口的演示服务，再运行：

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

8项测试覆盖真实stdio和HTTP连接、发现与参数规则、资源、模板、查询与错误、桥接转发和调用ID。没有远程部署或在线模型调用测试。

桥接示例只处理文本内容。接入真实模型还需要消息历史、模型请求、调用预算、最终回答和权限策略；读资源和获取提示也不会自动将它们加入模型上下文。
