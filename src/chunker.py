"""文本分块模块 — 按段落切分 + 保留页码/编号"""
import re
import logging
from dataclasses import dataclass, field

from src.pdf_parser import Page
from src.table_extractor import Table

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """文档块"""
    content: str
    page_num: int
    chunk_type: str  # "text" | "table" | "clause"
    section_id: str = ""
    metadata: dict = field(default_factory=dict)


def chunk_documents(pages: list[Page], tables: list[Table], config: dict) -> list[Chunk]:
    """
    将解析后的页面和表格分块。

    策略：
    - 正文：按段落切分，每块 ≤ max_chunk_size
    - 表格：独立成块
    - 条款编号：正则匹配保留
    """
    chunk_cfg = config.get("chunking", {})
    max_size = chunk_cfg.get("max_chunk_size", 500)
    overlap = chunk_cfg.get("overlap", 50)

    chunks = []

    # 正文分块
    for page in pages:
        text = page.full_text
        if not text.strip():
            continue

        # 按双换行分段落
        paragraphs = re.split(r'\n\s*\n', text)
        current_chunk = ""
        current_start_page = page.page_num

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 提取条款编号
            clause_id = _extract_clause_id(para)

            if len(current_chunk) + len(para) > max_size and current_chunk:
                chunks.append(Chunk(
                    content=current_chunk.strip(),
                    page_num=current_start_page,
                    chunk_type="clause" if clause_id else "text",
                    section_id=clause_id,
                    metadata={"page": current_start_page},
                ))
                # overlap: 保留最后 overlap 字
                if overlap > 0 and len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + "\n" + para
                else:
                    current_chunk = para
                current_start_page = page.page_num
            else:
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para

        # 最后一块
        if current_chunk.strip():
            chunks.append(Chunk(
                content=current_chunk.strip(),
                page_num=current_start_page,
                chunk_type="text",
                metadata={"page": current_start_page},
            ))

    # 表格分块
    for table in tables:
        chunks.append(Chunk(
            content=table.to_text(),
            page_num=table.page_num,
            chunk_type="table",
            metadata={"page": table.page_num, "type": "table"},
        ))

    logger.info(f"分块完成，共 {len(chunks)} 块 (正文 {len([c for c in chunks if c.chunk_type != 'table'])} + 表格 {len([c for c in chunks if c.chunk_type == 'table'])})")
    return chunks


def _extract_clause_id(text: str) -> str:
    """提取条款编号，如 '5.1.2' 或 '第5条'"""
    # 数字编号: 5.1.2, 5.1, 5.
    m = re.match(r'^(\d+(?:\.\d+)*)\s', text)
    if m:
        return m.group(1)
    # 中文编号: 第5条, 第3章
    m = re.match(r'^(第[一二三四五六七八九十\d]+[章节条])', text)
    if m:
        return m.group(1)
    return ""
