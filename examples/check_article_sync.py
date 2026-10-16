"""检查文章摘录、配套源码和第13章下载包；仅使用标准库，不调用模型。"""

import argparse
import ast
import io
import json
from pathlib import Path
import re
import sys
import textwrap
import tokenize
import zipfile


ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^```(python|json)\n(.*?)^```", re.M | re.S)
MARKER = re.compile(r"<!-- example-(source|json|kind): ([^\n]+?) -->\s*$")


def code_tokens(code):
    ignored = {tokenize.ENCODING, tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
               tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
    return [(token.type, token.string) for token in
            tokenize.generate_tokens(io.StringIO(textwrap.dedent(code)).readline)
            if token.type not in ignored]


def is_excerpt(code, source):
    excerpt, whole = code_tokens(code), code_tokens(source)
    return bool(excerpt) and any(whole[i:i + len(excerpt)] == excerpt
                                 for i in range(len(whole) - len(excerpt) + 1))


def archive_files(root=ROOT):
    article = next(root.glob("13-*.md"))
    files = [article, root / "supplements/13-实现细节与运行排查.md"]
    files.extend(path for path in (root / "examples/13-rag").iterdir()
                 if path.is_file() and (path.suffix in {".py", ".md", ".txt", ".pdf", ".json"}
                                        or path.name in {".gitignore", ".gitattributes"}))
    return sorted(files)


def normalized(data, path):
    return data if path.endswith(".pdf") else data.replace(b"\r\n", b"\n")


def check(root=ROOT):
    errors, excerpts, illustrations = [], 0, 0
    documents = sorted([path for path in root.glob("[0-9][0-9]-*.md")
                        if 13 <= int(path.name[:2]) <= 19] + list((root / "supplements").glob("*.md")))
    for path in documents:
        body = path.read_text(encoding="utf-8-sig")
        for block in FENCE.finditer(body):
            line = body[:block.start()].count("\n") + 1
            label = f"{path.relative_to(root)}:{line}"
            marker = MARKER.search(body[:block.start()])
            try:
                if block[1] == "python":
                    ast.parse(textwrap.dedent(block[2]))
                else:
                    json.loads(block[2])
                if marker is None:
                    raise ValueError("缺少摘录来源或独立示意标记")
                kind, target = marker.groups()
                if kind == "kind":
                    if target not in {"usage", "illustration", "adaptation"}:
                        raise ValueError(f"未知片段类型：{target}")
                    illustrations += 1
                    continue
                if kind == "source":
                    source = (root / target).read_text(encoding="utf-8-sig")
                    if not is_excerpt(block[2], source):
                        raise ValueError(f"摘录与 {target} 不一致")
                else:
                    filename, variable = target.split("#", 1)
                    tree = ast.parse((root / filename).read_text(encoding="utf-8-sig"))
                    name, index = variable.split(".")
                    value = next(ast.literal_eval(node.value) for node in tree.body
                                 if isinstance(node, ast.Assign) and any(
                                     isinstance(item, ast.Name) and item.id == name for item in node.targets))
                    if json.loads(block[2]) != value[int(index)]:
                        raise ValueError(f"JSON与 {target} 不一致")
                excerpts += 1
            except (SyntaxError, ValueError, OSError, StopIteration, tokenize.TokenError) as exc:
                errors.append(f"{label}: {exc}")
    # 归档包应包含正文、扩展说明和完整示例，且每份内容与当前文件一致。
    expected = {path.relative_to(root).as_posix(): path for path in archive_files(root)}
    try:
        with zipfile.ZipFile(root / "examples/13-rag-example.zip") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected):
                errors.append("第13章下载包文件清单与当前配套文件不一致")
            for name in set(names) & set(expected):
                if normalized(archive.read(name), name) != normalized(expected[name].read_bytes(), name):
                    errors.append(f"第13章下载包内容过时：{name}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"第13章下载包不可读：{exc}")
    return errors, excerpts, illustrations


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-archive", action="store_true", help="先从当前文件重建第13章下载包")
    options = parser.parse_args()
    if options.rebuild_archive:
        with zipfile.ZipFile(ROOT / "examples/13-rag-example.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in archive_files():
                archive.write(path, path.relative_to(ROOT).as_posix())
    problems, excerpts, illustrations = check()
    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    print(f"同步检查通过：{excerpts}段源码/JSON摘录，{illustrations}段调用/示意/适配，下载包一致。")
