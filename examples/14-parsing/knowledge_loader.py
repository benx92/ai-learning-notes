"""第14章：把Word标题继承实验接回第13章统一加载接口。"""

import sys
from pathlib import Path


RAG_DIRECTORY = Path(__file__).resolve().parents[1] / "13-rag"
sys.path.append(str(RAG_DIRECTORY))
from loader import DocumentLoader


class KnowledgeLoader(DocumentLoader):
    @staticmethod
    def _docx(path):
        from word_demo import read_word_units

        for record in read_word_units(path):
            metadata = record["metadata"]
            location = f"Word 块 {metadata['block']}"
            if "row" in metadata:
                location += f"，表格第 {metadata['row']} 行"
            yield record["text"], {**metadata, "location": location}
