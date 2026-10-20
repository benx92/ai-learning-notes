# 第14章：解析实验与入库演示

这里保存第14章正文中的实验，便于逐段对照。基础RAG程序仍使用[13-rag/loader.py](../13-rag/loader.py)。格式小实验仍只打印结果；`knowledge_loader.py`已接入Word标题继承，`demo_ingest.py`负责把转换结果送回第13章同一个入库与问答流程。

建议先用第13章的`refund-policy.md`接通文本问答，再沿本章“统一知识单元接口 → PDF基础读取与扫描问题 → 网页 → Word → PPT → Excel → 结构化记录”的顺序扩展入口。解析结果核对通过并接回加载器后，继续复用原来的切分、编码与问答流程。

使用Python 3.12，在本目录打开PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe html_demo.py
.\.venv\Scripts\python.exe records_demo.py
```

依赖版本与第13章解析器保持一致。按需准备以下文件，再运行对应脚本：

| 脚本 | 输入 | 观察内容 |
| --- | --- | --- |
| `html_demo.py` | 内置HTML字符串 | 只选择`article`正文，排除导航 |
| `pdf_demo.py` | 当前目录的`refund-policy.pdf`，可从[共享配套PDF](../13-rag/refund-policy.pdf)复制 | `read_pdf_page()`默认读取文字层，保留两页输出 |
| `word_demo.py` | 当前目录的`policy.docx`，使用标题1、标题2和简单表格 | `read_word_units()`继承标题，按正文顺序输出 |
| `ppt_demo.py` | 当前目录的`policy.pptx` | `read_slide_texts()`与`read_slide_notes()`分别读取画面文字和备注 |
| `excel_demo.py` | 当前目录的`policy.xlsx`，工作表“退货规定”，第1行为表头 | `read_excel_units()`按指定表头生成字段和值，保留零值 |
| `formula_demo.py` | 同上，观察B2 | 对照公式或原值与文件已有缓存，不重新计算 |
| `records_demo.py` | 内置CSV、JSON、JSONL、XML字符串 | 记录边界、字段配对与物理行号 |

例如：

```powershell
.\.venv\Scripts\python.exe word_demo.py
.\.venv\Scripts\python.exe ppt_demo.py
.\.venv\Scripts\python.exe excel_demo.py
```

OCR分支需要额外安装Tesseract及简体中文、英语语言数据，并对确认需要识别的页面选择`use_ocr=True`；当前默认运行不会启用OCR，未验证识别效果。复杂标题、合并表头、图表和多栏版式不在这些简单实验的完整覆盖范围内。

## 从解析接回知识库

以下命令在本目录执行，使用第13章已安装完整依赖的虚拟环境：

```powershell
..\13-rag\.venv\Scripts\python.exe build_sample.py
..\13-rag\.venv\Scripts\python.exe demo_ingest.py --path policy.docx --extract-only
..\13-rag\.venv\Scripts\python.exe demo_ingest.py --path policy.docx --output word-run.json
# 生成凭证与第13章相同；默认不生成，显式开启才调用接口。
..\13-rag\.venv\Scripts\python.exe demo_ingest.py --path policy.docx --generate
```

`build_sample.py`创建同一组虚构规则的Word样例，拒绝覆盖已有文件；可用`--output`指定其他文件名。已有`policy.docx`时直接跳过创建。

`KnowledgeLoader`继承基础加载器，复用`read_word_units()`，将标题继承结果适配为“正文、位置元数据”，再由`load()`生成`DocumentUnit`。演示把这个加载器交给`run_demo()`，实际执行的仍是第13章`Pipeline`。默认库为脚本旁的`format_demo`，`--db`可以另行指定。

`--extract-only`只打印转换结果，不加载模型；默认演示真实入库、检索和组装证据；`--generate`另行调用真实生成服务。输出`parsed`、`hits`、`context`、`evidence`可逐层核对，生成结果在`result`中。

已附`policy.csv`，无需先准备Office文件就能检查统一入口：

```powershell
.\.venv\Scripts\python.exe demo_ingest.py --extract-only
```

不传`--path`默认使用这份CSV。其他格式继续使用基础解析分支；正文区域选择、PPT备注、指定Excel表头、OCR等独立实验尚未全部接入。旧`rag.py extract`仍走基础加载器，不能用它检查这个Word子类是否生效。

## 接入检查

```powershell
..\13-rag\.venv\Scripts\python.exe -m unittest -v test_demo
```

两个检查通过：使用真实Word解析和Chroma检查标题、正文、来源与位置经过入库传到最终证据；另检查CSV统一入口与只解析模式。测试向量使用替身，不代表真实语义检索或在线生成效果；没有请求付费生成服务。

共享下载包`../13-rag-example.zip`包含两章正文、扩展说明和这两个示例目录，解压后保留同级目录关系。
