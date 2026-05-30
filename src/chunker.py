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


_SECTION_RE = re.compile(
    r'^\s*(第[一二三四五六七八九十\d]+[章节条]|\d+(?:\.\d+)*)\s+\S'
)


def chunk_documents(pages: list[Page], tables: list[Table], config: dict) -> list[Chunk]:
    """
    将解析后的页面和表格分块。

    策略：
    - 正文：先按双换行→单换行→硬切 逐级切分
    - 超长段落在 max_chunk_size 处硬切分
    - 表格：独立成块
    - 条款编号：正则匹配保留
    """
    chunk_cfg = config.get("chunking", {})
    max_size = chunk_cfg.get("max_chunk_size", 300)
    overlap = chunk_cfg.get("overlap", 80)

    chunks = []

    for page in pages:
        text = page.full_text
        if not text.strip():
            continue

        # 逐级切分段落
        paragraphs = _split_text(text, max_size)

        current_chunk = ""
        current_start_page = page.page_num

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            clause_id = _extract_clause_id(para)

            if len(current_chunk) + len(para) > max_size and current_chunk:
                chunks.append(Chunk(
                    content=f"[第{current_start_page}页] {current_chunk.strip()}",
                    page_num=current_start_page,
                    chunk_type="text",
                    section_id=_extract_clause_id(current_chunk),
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
                content=f"[第{current_start_page}页] {current_chunk.strip()}",
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

    text_count = sum(1 for c in chunks if c.chunk_type != "table")
    table_count = sum(1 for c in chunks if c.chunk_type == "table")
    logger.info(f"分块完成，共 {len(chunks)} 块 (正文 {text_count} + 表格 {table_count})")
    return chunks


def _split_text(text: str, max_size: int) -> list[str]:
    """逐级切分文本为段落列表：先双换行→单换行→硬切"""
    # 1. 尝试双换行
    parts = re.split(r'\n\s*\n', text)
    if all(len(p) <= max_size for p in parts):
        return parts

    # 2. 对超长段落进一步用单换行切分
    result = []
    for part in parts:
        if len(part) <= max_size:
            result.append(part)
        else:
            lines = part.split('\n')
            result.extend(_merge_lines(lines, max_size))
    return result


def _merge_lines(lines: list[str], max_size: int) -> list[str]:
    """将行合并为 ≤ max_size 的块，在章节标题处强制切分"""
    result = []
    current = ""
    for line in lines:
        line = line.strip()
        if not line:
            if current:
                result.append(current)
                current = ""
            continue

        # 遇到章节标题 → 结束当前 chunk，开启新 chunk
        if _is_section_header(line) and current:
            result.append(current)
            current = line
            continue

        if len(current) + len(line) > max_size:
            if current:
                result.append(current)
            # 单行超长：硬切分
            if len(line) > max_size:
                for i in range(0, len(line), max_size - 40):
                    result.append(line[i:i + max_size - 40])
            else:
                current = line
        else:
            current = current + "\n" + line if current else line

    if current:
        result.append(current)
    return result


def _is_section_header(text: str) -> bool:
    """判断是否为章节标题行，如 '3 技术要求' '4.1 基本规则' '第5条'"""
    return bool(_SECTION_RE.match(text))


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
