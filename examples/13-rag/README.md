# 第 13 篇配套：最小文档 RAG

对应文章：[RAG 实战：从文档到问答系统](https://github.com/benx92/ai-learning-notes/blob/main/13-RAG%E5%AE%9E%E6%88%98%E4%BB%8E%E6%96%87%E6%A1%A3%E5%88%B0%E9%97%AE%E7%AD%94%E7%B3%BB%E7%BB%9F.md)。

单用户、本地 Markdown/TXT 示例，支持文件入库、仅检索和调用生成接口问答。示例数据为虚构制度。

## 运行

以下命令在本目录执行，使用 Python 3.12 和 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe rag.py ingest --path refund-policy.md
.\.venv\Scripts\python.exe rag.py retrieve -q "会员买的普通商品，签收10天后还能退吗？"

$env:DEEPSEEK_API_KEY = "替换为你自己的密钥"
$env:RAG_CHAT_MODEL = "deepseek-flash"
.\.venv\Scripts\python.exe rag.py query -q "会员买的普通商品，签收10天后还能退吗？"
```

首次加载嵌入模型需要联网下载权重。使用已经下载的完整模型目录时，在入库前设置：

```powershell
$env:RAG_EMBEDDING_MODEL = "D:/models/paraphrase-multilingual-MiniLM-L12-v2"
```

入库和查询必须使用相同的模型配置。默认模型是 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`。切分按该模型的 Tokenizer 计数，目标块长 80、重叠 12；编码前还会检查包含特殊 Token 的长度。

生成接口固定为 DeepSeek 官方 HTTPS 端点。模型名应按当前 [官方文档](https://api-docs.deepseek.com/) 与账户权限填写；`deepseek-flash` 是写作时的文档示例。脚本读取进程环境变量，不自动加载 `.env`。`ingest` 和 `retrieve` 不需要生成接口密钥；`query` 会把问题和选入的参考资料发送给该接口。

## 调试命令

```powershell
# 默认阈值 -1 用于观察候选；下面的 0.4 仅用于实验，不是建议生产值。
.\.venv\Scripts\python.exe rag.py retrieve -q "定制商品签收3天后能无理由退货吗？" --threshold 0.4

# 检索到了文本但上下文预算容不下时，不应发起生成请求。
.\.venv\Scripts\python.exe rag.py query -q "会员买的普通商品，签收10天后还能退吗？" --context-chars 1

# 选择一个尚未入库的新目录，应返回资料不足。
.\.venv\Scripts\python.exe rag.py --db ./empty_demo query -q "会员买的普通商品，签收10天后还能退吗？"
```

`--db` 是全局参数，放在子命令前。默认数据库目录相对当前工作目录解析；从其他目录运行时请显式指定同一个数据库位置。

对同一文件重复执行入库，会覆盖相同 ID，清理该来源的过期块，保留其他来源。文件移动后视作新来源；文件删除不会自动同步。入库只接受单文件，不支持把目录传给 `--path`。

## 输出与限制

- `evidence` 仅列出实际放进 Prompt 的文本块，不代表逐句引用已经核验。
- `generated_pending_verification` 表示生成完成，答案仍需对照原文验证。
- 默认检索阈值 -1 不判断是否可回答；弱相关资料可能进入生成阶段。
- 6000 字符是证据软预算，不是生成模型的精确 Token 预算。
- 同文件更新由多次存储操作完成，不是原子事务。中断时重新完整入库；不支持并发写入。
- 全量文件编码适合小文档；生产环境需要流式加载与分批编码。
- 集合名包含模型标识和切分配置签名，但不会检测同名模型权重被替换；实际项目应固定模型版本。
- 示例无权限隔离、引用语义核验、重排或可靠的无答案分类，不作为生产服务。

示例固定了五项直接依赖的版本；上面的命令先安装 CPU 版 PyTorch，适合本地练习。它还不是包含全部间接依赖的锁文件，准备长期复现时，应在本机成功运行后保存完整依赖清单。

Sentence Transformers 5.1.2 的[官方依赖声明](https://github.com/huggingface/sentence-transformers/blob/v5.1.2/pyproject.toml)要求 Transformers 低于 5；这里固定为 4.57.1。不要只把其中一项升级到新主版本。此次检查中，更宽的版本范围曾解析到在 PyTorch 2.6 CPU 环境下导入失败的组合。

## 已做的验证

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_rag
```

在 Python 3.12、Chroma 1.5.9、langchain-text-splitters 1.1.3 下，三个回归用例通过，覆盖重复入库、同文件更新与旧块清理、保留其他文档、重新取得集合、空库、非法检索参数、上下文预算、证据编号和生成调用条件。生成请求的消息结构、正常返回与未完整生成也通过了模拟响应检查。

测试使用真实 Chroma 和切分器，但使用确定性的测试向量以及替身生成器，不下载真实嵌入模型、不调用付费模型接口。这些结果验证存储和控制流，不代表中文语义检索效果或真实接口调用已经通过。真实模型加载、分词长度检查、语义召回与最终问答效果仍需按上面的运行步骤实测。

本次优化另行尝试了真实模型：固定版本后 `SentenceTransformer` 已能导入并启动权重下载，但权重下载未完成，未取得真实语义检索结果，也未调用付费生成接口。因此正文的数据组装示例与预期回答明确标为讲解示意。
