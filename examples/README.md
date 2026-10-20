# 文章与配套代码对照

正文解释流程，下面的目录保存实际实现。标为源码摘录的片段保留源码中的函数名、参数、检查与返回字段；调用实验直接导入已有实现。设计示意和可选改进会在对应段落说明，不代表主程序已经具备该能力。

| 章节 | 配套位置 | 对照入口与范围 |
| --- | --- | --- |
| 13 RAG实战 | [13-rag](13-rag/README.md) | `demo_text.py`用`refund-policy.md`连续演示；`loader.py`输出知识单元，`Pipeline`入库与检索，`pack_context`组装，`ask`连接生成 |
| 14 文档解析 | [13-rag](13-rag/README.md)、[14-parsing](14-parsing/README.md) | `knowledge_loader.py`接入Word标题继承；`demo_ingest.py`复用第13章流程，另保留各格式独立实验 |
| 15 工具调用 | [15-tool-calling](15-tool-calling/README.md) | `tool_demo.py`查询循环；`return_demo.py`草稿、确认与本地申请记录 |
| 16 MCP | [16-mcp](16-mcp/README.md) | `server.py`提供能力；`client.py`和`http_client.py`通信；`bridge_demo.py`演示固定请求桥接 |
| 17 Agent | [15-tool-calling](15-tool-calling/README.md) | 复用查询循环和申请业务服务；详情查询、追问状态和完整在线申请Agent仍是设计说明 |
| 18 安全护栏 | [18-guardrails](18-guardrails/README.md)、[15-tool-calling](15-tool-calling/README.md) | 独立包装实验与真实本地申请检查；未实现完整持久审批Agent |
| 19 LangChain | [19-langchain](19-langchain/README.md) | `reading_demo.py`消息；`components_demo.py`工具；`agent_demo.py`的`build_agent`组织循环并设置限额 |
| 20—24 | 尚无配套实现 | 当前正文文件只有待写提纲 |

各目录的依赖、工作目录和环境变量分别见对应README。第15章用`DEEPSEEK_MODEL`，第13章用`RAG_CHAT_MODEL`，第19章用`LC_CHAT_MODEL`；它们是各脚本自己的配置名。

`refund_status`是第15、16章查询工具的结果字段；第19章工具返回`status`。这几个示例属于不同接口，正文分别沿用实际字段，跨脚本接入时要明确转换。

## 维护时检查同步

在仓库根目录使用Python 3.12运行，无需安装第三方依赖：

```powershell
py -3.12 examples/check_article_sync.py
```

修改第13、14章正文、扩展说明或示例后，用 `py -3.12 examples/check_article_sync.py --rebuild-archive` 重建下载包并检查；不带参数时只检查，不修改文件。下载包现在同时包含第13、14章正文、对应扩展说明以及两个示例目录，保留目录关系后可直接使用共享演示流程。

检查覆盖第13—19章及扩展说明中的Python和JSON片段，以及第13章下载包。源码摘录在代码块前用HTML注释`example-source`记录仓库相对路径；检查会忽略缩进、换行和注释，对照连续代码标记，因此变量名、参数、返回字段或执行检查的变化会报错。JSON工具声明另外与源码中的`TOOLS[0]`比较。

调用示例、数据结构示意和接入改写分别使用`example-kind: usage`、`illustration`、`adaptation`标记；只检查语法，不把它们宣称为已经实现的源码。HTML注释不在正文渲染结果中显示，读者所需的文件与用途说明仍写在代码附近。

这个检查不验证自然语言解释、检索效果、在线模型表现或OCR准确率。源码逻辑变动后，仍需复核对应段落与运行结果。
