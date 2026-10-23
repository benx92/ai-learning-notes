# 第 13 篇配套：最小文档 RAG

对应文章：[RAG 实战：从文档到问答系统](https://github.com/benx92/ai-learning-notes/blob/main/13-RAG%E5%AE%9E%E6%88%98%E4%BB%8E%E6%96%87%E6%A1%A3%E5%88%B0%E9%97%AE%E7%AD%94%E7%B3%BB%E7%BB%9F.md)。

单用户、本地多格式文档示例，支持只解析、文件入库、仅检索和调用生成接口问答。PDF 与 Markdown 中的售后政策均为虚构制度。

`loader.py` 返回带原始位置的 `DocumentUnit`；`rag.py` 在每个单元内切分，让位置经过索引、候选、上下文一直进入最终 `evidence`。第13章重点是这条可检查的完整流程；复杂版面、OCR 和格式恢复留给后续文档解析章节。

正文先比较给模型资料前后的判断依据，区分嵌入模型、生成模型与普通程序，再用`refund-policy.md`跑通文本问答；Top K等概念直接沿用前文。结尾留下`DocumentUnit(text, metadata)`接口，再由[文档解析工具链](../../14-文档解析工具链网页PDFWordPPTExcel怎么进知识库.md)扩展PDF、网页、Office与图文内容转换。当前程序只接入文本向量检索，未实现直接多模态检索、混合检索、RRF或重排。

## 连续演示入口

`demo_text.py`直接复用`loader.py`与`rag.py`，默认使用脚本旁的`refund-policy.md`和`text_demo`，从其他工作目录启动也不会误选文件。完成下方依赖安装后运行：

```powershell
.\.venv\Scripts\python.exe demo_text.py --extract-only
.\.venv\Scripts\python.exe demo_text.py --output text-run.json
# 先按下方说明设置生成凭证；只有显式开启才请求生成服务。
.\.venv\Scripts\python.exe demo_text.py --generate
```

`--extract-only`不加载模型或向量库；默认完整演示使用真实编码器和Chroma，输出解析、入库、候选与实际上下文，尚不生成回答。`--generate`调用真实接口，返回`result`中的回答与证据。演示每次都重新入库；实际使用可按下方分阶段命令分别触发。

`run_demo()`也供第14章导入，允许传入改进加载器。测试才注入测试向量和替身生成器，命令行演示不会悄悄使用替身。

## 运行

文件新增或更新时运行 `ingest`；每次提问运行 `query`。两者可以在不同进程、不同时间执行，连接它们的是同一个数据库目录。示例没有上传界面，直接接收本地文件路径。

以下命令在本目录执行，使用 Python 3.12 和 PowerShell。先安装环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

文件新增或更新时，检查解析并入库；入库完成后可以退出程序：

```powershell
.\.venv\Scripts\python.exe rag.py extract --path refund-policy.md
.\.venv\Scripts\python.exe rag.py --db ./text_demo ingest --path refund-policy.md
```

稍后提问时打开同一个数据库。下面先用 `retrieve`观察候选，它是调试入口；正常问答直接用 `query`，不需要先手动运行 `retrieve`：

```powershell
.\.venv\Scripts\python.exe rag.py --db ./text_demo retrieve -q "会员买的非定制商品，签收10天后还能申请退货吗？"

# 先按下方“准备DeepSeek API”配置当前终端的Key和模型名。
.\.venv\Scripts\python.exe rag.py --db ./text_demo query -q "会员买的非定制商品，签收10天后还能申请退货吗？"
```

换问题时只替换 `query`的 `-q`内容；不会重新解析、切分或编码文档。模型或切分配置变化需要重新入库，不能继续混用旧索引。

首次加载嵌入模型需要联网下载权重。使用已经下载的完整模型目录时，在入库前设置：

```powershell
$env:RAG_EMBEDDING_MODEL = "D:/models/paraphrase-multilingual-MiniLM-L12-v2"
```

入库和查询必须使用相同的模型配置。默认模型是 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`。切分按该模型的 Tokenizer 计数，目标块长 80、重叠 12；编码前还会检查包含特殊 Token 的长度。

生成接口固定为 DeepSeek 官方 HTTPS 端点。模型名应按当前 [官方文档](https://api-docs.deepseek.com/) 与账户权限填写。脚本读取进程环境变量，不自动加载 `.env`。`extract` 不加载模型、不调用生成服务；`ingest` 和 `retrieve` 不需要生成接口密钥；`query` 会把问题和选入的参考资料发送给该接口。

## 准备DeepSeek API：账号、余额与Key

本例只有有证据时的`query`与显式`--generate`才请求DeepSeek；解析、入库、检索和默认演示都不需要DeepSeek Key。MiniLM在本地编码，首次使用可能下载权重。

1. 打开[DeepSeek开放平台](https://platform.deepseek.com/)，注册或登录，完成平台当时要求的验证。聊天网页能使用，不等于API已经配置好。
2. 查看API可用余额。接口按输入、输出Token用量扣费；有可用赠金时可以先用，没有可用余额则到[充值页面](https://platform.deepseek.com/top_up)按页面要求充值。Key不是购买的调用额度；不要求先买月度会员，也不保证注册就有赠金。金额、支付方式及当前单价以控制台和[官方计费页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)为准。
3. 在[API keys](https://platform.deepseek.com/api_keys)创建练习用Key，例如命名`rag-learning`，复制并妥善保存完整密钥，不要提交到仓库；泄露后撤销并重建。
4. 在随后运行Python的同一个PowerShell里配置，粘贴时不回显Key：

```powershell
$ragDemoSecret = Read-Host "粘贴自己的DeepSeek API Key" -AsSecureString
$env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new("", $ragDemoSecret).Password
Remove-Variable ragDemoSecret
$env:RAG_CHAT_MODEL = "deepseek-flash"
```

模型名根据2026年10月20日[官方首次调用说明](https://api-docs.deepseek.com/zh-cn/)填写；后续如有变化，以文档和账户可用模型为准。示例固定请求`https://api.deepseek.com/chat/completions`，不需要设置Base URL，也不能直接换成其他平台的Key。

环境变量对当前终端及其启动的Python生效，新开终端需要重新配置；脚本不自动读取`.env`。准备完成后运行`query`或`demo_text.py --generate`，核对答案、证据和`usage`即可。

账号与接口异常参见[官方错误码说明](https://api-docs.deepseek.com/zh-cn/quick_start/error_codes/)，准备过程见[第13章正文](../../13-RAG实战从文档到问答系统.md)。

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

`refund-policy.md`是正文使用的纯文本样例，加载时形成一个全文单元，块数以实际切分结果为准。`refund-policy.pdf`保留为解析篇与历史检索验证使用的两页样例，两种文件包含相同业务规则。`build_sample.py` 可重建它，只有重建时额外需要 ReportLab：

```powershell
.\.venv\Scripts\python.exe -m pip install reportlab
.\.venv\Scripts\python.exe build_sample.py
```

`verify_pdf.py`仍固定使用PDF，与正文Markdown演练分开；它使用真实模型与临时数据库重跑四道问题，只验证解析和检索，写出 `verification-retrieval.json`，不会调用生成接口。记录中的路径已简化为文件名，路径相关块 ID 已去除。

该验证脚本与已保存记录保留较早的问法“会员买的普通商品，签收10天后还能退吗？”，其中“普通商品”指非定制商品。正文与上面的运行命令使用Markdown和“非定制商品”问法；文件格式、切分或问法改变后，旧PDF分数不能直接当成当前演练的实测结果。

## 调试命令

```powershell
# 默认阈值 -1 用于观察候选；下面的 0.4 仅用于实验，不是建议生产值。
.\.venv\Scripts\python.exe rag.py --db ./text_demo retrieve -q "定制商品签收3天后能无理由退货吗？" --threshold 0.4

# 检索到了文本但上下文预算容不下时，不应发起生成请求。
.\.venv\Scripts\python.exe rag.py --db ./text_demo query -q "会员买的非定制商品，签收10天后还能申请退货吗？" --context-chars 1

# 选择一个尚未入库的新目录，应返回资料不足。
.\.venv\Scripts\python.exe rag.py --db ./empty_demo query -q "会员买的非定制商品，签收10天后还能申请退货吗？"
```

`--db` 是全局参数，放在子命令前。默认数据库目录相对当前工作目录解析；从其他目录运行时请显式指定同一个数据库位置。

对同一文件重复执行入库，会覆盖相同 ID，清理该来源的过期块，保留其他来源。文件移动后视作新来源；文件删除不会自动同步。入库只接受单文件，不支持把目录传给 `--path`。

索引签名已升级为 `units-v2`，旧示例用户需要重新入库；旧集合不会自动迁移或删除。默认 `top_k=5`。正文Markdown样例的块数以实际输出为准；历史PDF实测形成两个块，会取回全部块。这些小样例都不能证明大知识库的召回质量。

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
.\.venv\Scripts\python.exe -m unittest -v test_rag test_loader test_demo
.\.venv\Scripts\python.exe verify_pdf.py
```

在 Python 3.12、Chroma 1.5.9、langchain-text-splitters 1.1.3 和依赖文件固定的解析库下，原有十个回归用例通过：覆盖真实 PDF、DOCX、PPTX、XLSX、HTML、CSV、JSON、JSONL 解析，来源位置传递、重复入库、同文件更新、解析失败后保留旧索引、空库、非法参数、预算、证据编号和生成调用条件。生成请求结构、正常返回与未完整生成也通过模拟响应检查。

新增`test_demo.py`的两个用例检查纯文本入口、来源与上下文交接、重复运行和显式生成，共12个检查通过。上述回归测试使用测试向量和替身生成器，负责验证解析、存储与控制流。第14章另有两个接入检查，验证改进Word解析和CSV统一接口。

此外，已用真实多语言 MiniLM、PyTorch 2.6 CPU 与 Chroma 完成 PDF 入库和四道问题的检索，原始解析文本、分数、位置、上下文和选入证据见 `verification-retrieval.json`。运费问题没有依据却仍命中相关页面，默认阈值不能可靠拒答。

没有调用付费生成接口；文章中的预期回答是核验标准。只有两块语料的实测也不能证明多文档召回、复杂解析或生成质量已经达标。

仓库中的`13-rag-example.zip`现包含第13、14章正文、对应扩展说明、`13-rag`与`14-parsing`两个目录的配套文件。解压时保留目录关系，文件转换演示才能导入同一套RAG流程。下载包与仓库的同步维护方法见[示例总览](https://github.com/benx92/ai-learning-notes/blob/main/examples/README.md)。
