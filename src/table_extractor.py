"""表格提取模块 — 检测表格区域 + 结构化输出"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Table:
    """提取的表格"""
    page_num: int
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    caption: str = ""
    raw_text: str = ""

    def to_text(self) -> str:
        """将表格转为可读文本"""
        lines = []
        if self.caption:
            lines.append(f"表格标题: {self.caption}")
        if self.headers:
            lines.append(" | ".join(self.headers))
            lines.append("-" * len(lines[-1]))
        for row in self.rows:
            lines.append(" | ".join(row))
        return f"(第{self.page_num}页)\n" + "\n".join(lines)


def extract_tables_from_page(page_image_path: str, page_num: int) -> list[Table]:
    """
    从单页图像提取表格。

    使用 PaddleOCR 的表格识别功能。
    如果 PaddleOCR 版本不支持 table-ocr，回退到基于文本布局的启发式检测。
    """
    import cv2
    import numpy as np

    img = cv2.imread(page_image_path)
    if img is None:
        logger.warning(f"无法读取图像: {page_image_path}")
        return []

    tables = []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 二值化
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # 检测水平线和垂直线（表格特征）
    horizontal = _detect_lines(binary, horizontal=True)
    vertical = _detect_lines(binary, horizontal=False)

    # 计算交点密度来判断表格区域
    if horizontal is not None and vertical is not None:
        table_mask = cv2.bitwise_and(horizontal, vertical)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        large_contours = [c for c in contours if cv2.contourArea(c) > 1000]
        if large_contours:
            logger.info(f"第 {page_num} 页检测到 {len(large_contours)} 个表格区域")
            # 标记该页含表格
            tables.append(Table(
                page_num=page_num,
                caption=f"第{page_num}页检测到的表格",
                raw_text=f"[表格区域，位于第{page_num}页]",
            ))

    return tables


def _detect_lines(binary, horizontal=True):
    """检测水平或垂直线条"""
    import cv2
    import numpy as np

    if horizontal:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    else:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

    eroded = cv2.erode(binary, kernel, iterations=1)
    dilated = cv2.dilate(eroded, kernel, iterations=1)
    return dilated


def extract_tables_with_ocr(page_image_path: str, page_num: int) -> list[Table]:
    """
    PaddleOCR 表格识别（需要 paddleocr 的 table 功能）。
    如果不可用，回退到 extract_tables_from_page。
    """
    try:
        from paddleocr import PPStructure
        engine = PPStructure(layout=False, show_log=False)
        result = engine(page_image_path)
        tables = []
        for item in result:
            if item.get("type") == "table":
                tables.append(Table(
                    page_num=page_num,
                    raw_text=item.get("res", ""),
                    caption=f"第{page_num}页表格",
                ))
        return tables
    except ImportError:
        logger.info("PPStructure 不可用，使用布局检测")
        return extract_tables_from_page(page_image_path, page_num)
    except Exception as e:
        logger.warning(f"表格 OCR 失败: {e}")
        return extract_tables_from_page(page_image_path, page_num)
