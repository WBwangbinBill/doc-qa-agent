"""PDF 解析模块 — 判断扫描件 + tesseract OCR 识别"""
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """文本块"""
    text: str
    page_num: int
    bbox: tuple | None = None  # (x0, y0, x1, y1)
    confidence: float = 0.0


@dataclass
class Page:
    """PDF 页面"""
    page_num: int
    text_blocks: list[TextBlock] = field(default_factory=list)
    raw_text: str = ""
    has_table: bool = False
    is_scanned: bool = False

    @property
    def full_text(self) -> str:
        return "\n".join(b.text for b in self.text_blocks)


def is_scanned_pdf(filepath: str) -> bool:
    """判断 PDF 是否为扫描件（无文本层）。"""
    import fitz
    doc = fitz.open(filepath)
    total_chars = 0
    for page in doc:
        total_chars += len(page.get_text().strip())
    doc.close()
    # 如果整份文档提取的文本少于 100 字符，认为是扫描件
    return total_chars < 100


def parse_pdf(filepath: str, config: dict) -> list[Page]:
    """
    解析 PDF，返回 Page 列表。
    - 文字版 PDF：直接提取文本
    - 扫描件 PDF：OCR 识别
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {filepath}")

    scanned = is_scanned_pdf(filepath)
    logger.info(f"PDF 类型: {'扫描件' if scanned else '文字版'}")

    if scanned:
        return _parse_scanned(filepath, config)
    else:
        return _parse_text(filepath)


def _parse_text(filepath: str) -> list[Page]:
    """文字版 PDF：直接提取文本层"""
    import fitz
    doc = fitz.open(filepath)
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        blocks = []
        # 按段落分块
        for block in page.get_text("blocks"):
            block_text = block[4].strip() if len(block) > 4 else ""
            if block_text:
                blocks.append(TextBlock(
                    text=block_text,
                    page_num=i + 1,
                    bbox=block[:4] if len(block) >= 4 else None,
                ))

        pages.append(Page(
            page_num=i + 1,
            text_blocks=blocks,
            raw_text=text,
            is_scanned=False,
        ))

    doc.close()
    logger.info(f"文字版 PDF 解析完成，共 {len(pages)} 页")
    return pages


def _parse_scanned(filepath: str, config: dict) -> list[Page]:
    """扫描件 PDF：tesseract OCR 识别"""
    import fitz
    import pytesseract
    from PIL import Image
    import io

    ocr_cfg = config.get("ocr", {})
    lang = ocr_cfg.get("lang", "chi_sim")

    logger.info(f"使用 tesseract OCR (lang={lang})...")

    doc = fitz.open(filepath)
    pages = []

    for i, page in enumerate(doc):
        logger.info(f"OCR 识别第 {i+1}/{len(doc)} 页...")

        # PDF 页 → 图像
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        try:
            # tesseract OCR
            text = pytesseract.image_to_string(img, lang=lang)
            blocks = []

            if text.strip():
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        blocks.append(TextBlock(
                            text=line,
                            page_num=i + 1,
                            confidence=0.0,  # tesseract 批量模式不返回逐行置信度
                        ))

            pages.append(Page(
                page_num=i + 1,
                text_blocks=blocks,
                raw_text=text.strip(),
                is_scanned=True,
            ))
        except Exception as e:
            logger.warning(f"第 {i+1} 页 OCR 失败: {e}")
            pages.append(Page(page_num=i + 1, is_scanned=True))

    doc.close()
    logger.info(f"扫描件 OCR 完成，共 {len(pages)} 页")
    return pages
