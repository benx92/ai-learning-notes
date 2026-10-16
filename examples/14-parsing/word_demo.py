import re
from pathlib import Path
from docx import Document
from docx.table import Table


def read_word_units(path):
    source = str(Path(path).resolve())
    headings = {}
    for number, block in enumerate(Document(path).iter_inner_content(), 1):
        rows = []
        if isinstance(block, Table):
            if not block.rows:
                continue
            headers = [cell.text.strip() for cell in block.rows[0].cells]
            for row_number, row in enumerate(block.rows[1:], 2):
                pairs = []
                for i, (name, cell) in enumerate(zip(headers, row.cells), 1):
                    value = cell.text.strip()
                    if value:
                        field = name or f"列{i}"
                        pairs.append(f"{field}={value}")
                if pairs:
                    rows.append(("；".join(pairs), {"row": row_number}))
        else:
            text = block.text.strip()
            match = re.fullmatch(r"Heading ([1-9])", block.style.name)
            if match:
                level = int(match.group(1))
                headings = {k: v for k, v in headings.items() if k < level}
                headings[level] = text
                continue
            if text:
                rows.append((text, {}))
        title = " > ".join(headings[k] for k in sorted(headings))
        for text, position in rows:
            yield {"text": f"{title}\n{text}" if title else text,
                   "metadata": {"source": source, "block": number,
                                "title_path": title, **position}}


if __name__ == "__main__":
    for unit in read_word_units("policy.docx"):
        print(unit)
