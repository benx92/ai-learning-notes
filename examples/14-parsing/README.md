# 第14章：独立解析实验

这里保存第14章正文中的实验，便于逐段对照。基础RAG程序仍使用[13-rag/loader.py](../13-rag/loader.py)。这些脚本只打印结果，没有自动替换加载器或重新入库。

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
| `pdf_demo.py` | 当前目录的`refund-policy.pdf`，可从[第13章样例](../13-rag/refund-policy.pdf)复制 | `read_pdf_page()`默认读取文字层，保留两页输出 |
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

正文末尾的`_docx()`替换片段用于说明接口适配：独立实验产生记录字典，现有加载器分支则要提供“正文、位置元数据”二元组。接入改进后先运行`rag.py extract`核对，再重新入库；单独运行这里的脚本不会更新已有索引。
