# 第 13 篇配套：最小文档 RAG

对应文章：[RAG 实战：从文档到问答系统](https://github.com/benx92/ai-learning-notes/blob/main/13-RAG%E5%AE%9E%E6%88%98%E4%BB%8E%E6%96%87%E6%A1%A3%E5%88%B0%E9%97%AE%E7%AD%94%E7%B3%BB%E7%BB%9F.md)。

单用户、本地多格式文档示例，支持只解析、文件入库、仅检索和调用生成接口问答。PDF 与 Markdown 中的售后政策均为虚构制度。

`loader.py` 返回带原始位置的 `DocumentUnit`；`rag.py` 在每个单元内切分，让位置经过索引、候选、上下文一直进入最终 `evidence`。第13章重点是这条可检查的完整流程；复杂版面、OCR 和格式恢复留给后续文档解析章节。

## 运行

以下命令在本目录执行，使用 Python 3.12 和 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe rag.py extract --path refund-policy.pdf
.\.venv\Scripts\python.exe rag.py --db ./pdf_demo ingest --path refund-policy.pdf
.\.venv\Scripts\python.exe rag.py --db ./pdf_demo retrieve -q "会员买的非定制商品，签收10天后还能申请退货吗？"

$env:DEEPSEEK_API_KEY = "替换为你自己的密钥"
$env:RAG_CHAT_MODEL = "填写账户可用的模型名"
.\.venv\Scripts\python.exe rag.py --db ./pdf_demo query -q "会员买的非定制商品，签收10天后还能申请退货吗？"
```

首次加载嵌入模型需要联网下载权重。使用已经下载的完整模型目录时，在入库前设置：

```powershell
$env:RAG_EMBEDDING_MODEL = "D:/models/paraphrase-multilingual-MiniLM-L12-v2"
```

入库和查询必须使用相同的模型配置。默认模型是 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`。切分按该模型的 Tokenizer 计数，目标块长 80、重叠 12；编码前还会检查包含特殊 Token 的长度。

生成接口固定为 DeepSeek 官方 HTTPS 端点。模型名应按当前 [官方文档](https://api-docs.deepseek.com/) 与账户权限填写。脚本读取进程环境变量，不自动加载 `.env`。`extract` 不加载模型、不调用生成服务；`ingest` 和 `retrieve` 不需要生成接口密钥；`query` 会把问题和选入的参考资料发送给该接口。

## 文件与解析范围

| 格式 | 文本单元与位置 | 限制 |
| --- | --- | --- |
| `.pdf` | 每页，`page` | 不做 OCR；任何空文本页报错；不恢复复杂版面或跨页表格 |
| `.docx` | 正文块、表格行，`block`、`row` | 不提供排版页码，不读取页眉页脚、图片和修订内容 |
| `.pptx` | 幻灯片，`slide` | 提取文本框、表格和组合形状；不读备注、图片及图表语义；空文本页跳过 |
| `.xlsx` | 表格行，`sheet`、`row` | 首个非空行视为表头；不处理合并表头；只读公式缓存结果 |
| `.html`、`.htm` | 本地正文 | 移除脚本与样式，不抓取 URL，不识别主内容区域 |
| `.csv` | 记录，`row` | 逐记录保留字段，不推断业务表头 |
| `.json`、`.jsonl` | 全文或 JSONL 行 | 校验 JSON；JSONL 保留物理行号 |
| `.md`、`.txt` | 全文 | 严格 UTF-8，兼容 BOM |

旧 `.doc`、`.ppt`、`.xls` 必须先转换为新版格式。每个单元只在内部切分；跨页句子与表格不会自动合并。当前只接收单文件。

`refund-policy.pdf` 是已打包的两页样例。`build_sample.py` 可重建它，只有重建时额外需要 ReportLab：

```powershell
.\.venv\Scripts\python.exe -m pip install reportlab
.\.venv\Scripts\python.exe build_sample.py
```

`verify_pdf.py` 使用真实模型与临时数据库重跑四道问题，只验证解析和检索，写出 `verification-retrieval.json`，不会调用生成接口。记录中的路径已简化为文件名，路径相关块 ID 已去除。

该验证脚本与已保存记录保留较早的问法“会员买的普通商品，签收10天后还能退吗？”，其中“普通商品”指非定制商品。正文与上面的运行命令已明确写为“非定制商品”；问法改变后，旧分数不能直接当成新问法的实测结果。

## 调试命令

```powershell
# 默认阈值 -1 用于观察候选；下面的 0.4 仅用于实验，不是建议生产值。
.\.venv\Scripts\python.exe rag.py --db ./pdf_demo retrieve -q "定制商品签收3天后能无理由退货吗？" --threshold 0.4

# 检索到了文本但上下文预算容不下时，不应发起生成请求。
.\.venv\Scripts\python.exe rag.py --db ./pdf_demo query -q "会员买的非定制商品，签收10天后还能申请退货吗？" --context-chars 1

# 选择一个尚未入库的新目录，应返回资料不足。
.\.venv\Scripts\python.exe rag.py --db ./empty_demo query -q "会员买的非定制商品，签收10天后还能申请退货吗？"
```

`--db` 是全局参数，放在子命令前。默认数据库目录相对当前工作目录解析；从其他目录运行时请显式指定同一个数据库位置。

对同一文件重复执行入库，会覆盖相同 ID，清理该来源的过期块，保留其他来源。文件移动后视作新来源；文件删除不会自动同步。入库只接受单文件，不支持把目录传给 `--path`。

索引签名已升级为 `units-v2`，旧示例用户需要重新入库；旧集合不会自动迁移或删除。默认 `top_k=5`，本次 PDF 只有两个块，所以会返回全部块，不能把这个结果当作大知识库的召回质量证明。

## 输出与限制

- `evidence` 仅列出实际放进 Prompt 的文本块，不代表逐句引用已经核验。
- `generated_pending_verification` 表示生成完成，答案仍需对照原文验证。
- 默认检索阈值 -1 不判断是否可回答；弱相关资料可能进入生成阶段。
- 6000 字符是证据软预算，不是生成模型的精确 Token 预算。
- 同文件更新由多次存储操作完成，不是原子事务。中断时重新完整入库；不支持并发写入。
- 全量文件编码适合小文档；生产环境需要流式加载与分批编码。
- 集合名包含模型标识和切分配置签名，但不会检测同名模型权重被替换；实际项目应固定模型版本。
- 示例无权限隔离、引用语义核验、重排或可靠的无答案分类，不作为生产服务。

示例固定了模型、向量库、切分器和解析库的直接版本；上面的命令先安装 CPU 版 PyTorch，适合本地练习。它还不是包含全部间接依赖的锁文件，准备长期复现时，应在本机成功运行后保存完整依赖清单。

Sentence Transformers 5.1.2 的[官方依赖声明](https://github.com/huggingface/sentence-transformers/blob/v5.1.2/pyproject.toml)要求 Transformers 低于 5；这里固定为 4.57.1。不要只把其中一项升级到新主版本。此次检查中，更宽的版本范围曾解析到在 PyTorch 2.6 CPU 环境下导入失败的组合。

## 已做的验证

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_rag test_loader
.\.venv\Scripts\python.exe verify_pdf.py
```

在 Python 3.12、Chroma 1.5.9、langchain-text-splitters 1.1.3 和依赖文件固定的解析库下，十个回归用例通过：覆盖真实 PDF、DOCX、PPTX、XLSX、HTML、CSV、JSON、JSONL 解析，来源位置传递、重复入库、同文件更新、解析失败后保留旧索引、空库、非法参数、预算、证据编号和生成调用条件。生成请求结构、正常返回与未完整生成也通过模拟响应检查。

上述回归测试使用测试向量和替身生成器，负责验证解析、存储与控制流。

此外，已用真实多语言 MiniLM、PyTorch 2.6 CPU 与 Chroma 完成 PDF 入库和四道问题的检索，原始解析文本、分数、位置、上下文和选入证据见 `verification-retrieval.json`。运费问题没有依据却仍命中相关页面，默认阈值不能可靠拒答。

没有调用付费生成接口；文章中的预期回答是核验标准。只有两块语料的实测也不能证明多文档召回、复杂解析或生成质量已经达标。
