#!/usr/bin/env python3
"""
智能文档问答 Agent — 入口文件

用法:
    python main.py                    # 交互模式
    python main.py --question "..."   # 单次问答
    python main.py --parse-only       # 仅解析 PDF 并建索引
"""

import argparse
import logging
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("doc_qa")

from src.config import load_config
from src.pdf_parser import parse_pdf
from src.table_extractor import extract_tables_from_page, extract_tables_with_ocr
from src.chunker import chunk_documents, Chunk
from src.embedder import Embedder
from src.retriever import Retriever
from src.generator import Generator
from src.self_checker import SelfChecker


class DocQAAgent:
    """智能文档问答 Agent"""

    def __init__(self, config: dict):
        self.config = config
        self.embedder = Embedder(config)
        self.retriever = Retriever(self.embedder, config)
        self.generator = Generator(config)
        self.checker = SelfChecker(config)
        self._ready = False

    def build_knowledge_base(self, pdf_path: str) -> dict:
        """解析 PDF 并构建知识库（优先使用缓存）"""
        cache_dir = self.config.get("pdf", {}).get("output_dir", "data/parsed")

        # 尝试从缓存加载
        if self.retriever.load(cache_dir, pdf_path):
            self._ready = True
            return {
                "pages": len(set(c.page_num for c in self.retriever._chunks)),
                "is_scanned": True,
                "chunks": len(self.retriever._chunks),
                "tables": sum(1 for c in self.retriever._chunks if c.chunk_type == "table"),
                "cached": True,
            }

        logger.info(f"开始解析 PDF: {pdf_path}")

        # 1. PDF 解析
        pages = parse_pdf(pdf_path, self.config)
        logger.info(f"解析完成: {len(pages)} 页, "
                    f"扫描件: {any(p.is_scanned for p in pages)}")

        # 2. 表格提取（可选，跳过不影响核心功能）
        tables = []
        try:
            import fitz
            doc = fitz.open(pdf_path)
            for page in pages:
                if page.is_scanned:
                    p = doc[page.page_num - 1]
                    pix = p.get_pixmap(dpi=200)
                    img_path = f"/tmp/doc_qa_table_{page.page_num}.png"
                    pix.save(img_path)
                    page_tables = extract_tables_with_ocr(img_path, page.page_num)
                    tables.extend(page_tables)
            doc.close()
        except Exception as e:
            logger.warning(f"表格提取跳过: {e}")

        # 3. 分块
        chunks = chunk_documents(pages, tables, self.config)
        logger.info(f"分块完成: {len(chunks)} 块")

        # 4. 建索引
        self.retriever.build_index(chunks)

        # 5. 缓存
        self.retriever.save(cache_dir, pdf_path)

        self._ready = True

        return {
            "pages": len(pages),
            "is_scanned": any(p.is_scanned for p in pages),
            "chunks": len(chunks),
            "tables": len(tables),
        }

    def ask(self, question: str) -> dict:
        """问答"""
        if not self._ready:
            return {"error": "知识库未构建，请先调用 build_knowledge_base()"}

        if not question.strip():
            return {"error": "请输入问题"}

        # 检索
        retrieved = self.retriever.retrieve(question)

        # 生成
        answer = self.generator.generate(question, retrieved)

        # 自检
        check = self.checker.check(question, answer, retrieved)

        return {
            "question": question,
            "answer": answer.answer,
            "sources": answer.sources,
            "self_check": {
                "has_evidence": check.has_evidence,
                "possible_hallucination": check.possible_hallucination,
                "should_refuse": check.should_refuse,
                "confidence": check.confidence,
                "reason": check.reason,
            },
            "retrieved_count": len(retrieved),
        }


def main():
    parser = argparse.ArgumentParser(description="智能文档问答 Agent")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--pdf", default="", help="PDF 文件路径")
    parser.add_argument("--question", "-q", default="", help="单次问答")
    parser.add_argument("--parse-only", action="store_true", help="仅解析建索引")
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    logger.info("配置加载完成")

    # 找 PDF
    pdf_path = args.pdf
    if not pdf_path:
        data_dir = Path(config.get("pdf", {}).get("input_dir", "data"))
        pdfs = list(data_dir.glob("*.pdf"))
        if not pdfs:
            logger.error(f"在 {data_dir} 下未找到 PDF 文件")
            sys.exit(1)
        pdf_path = str(pdfs[0])
        logger.info(f"自动选择 PDF: {pdf_path}")

    # 构建知识库
    agent = DocQAAgent(config)
    stats = agent.build_knowledge_base(pdf_path)
    logger.info(f"知识库构建完成: {stats}")

    if args.parse_only:
        logger.info("解析完成，退出")
        return

    # 问答
    if args.question:
        result = agent.ask(args.question)
        print("\n" + "=" * 60)
        print(f"问题: {result['question']}")
        print(f"答案: {result['answer']}")
        print(f"\n来源:")
        for s in result.get("sources", []):
            print(f"  第{s['page']}页 (相关度: {s['score']})")
        print(f"\n自检: {result['self_check']['reason']}")
        print(f"置信度: {result['self_check']['confidence']}")
        print("=" * 60)
    else:
        # 交互模式
        print("\n智能文档问答 Agent 已就绪")
        print(f"文档: {pdf_path} ({stats['pages']}页, {stats['chunks']}块)")
        print("输入问题或 /quit 退出\n")

        while True:
            try:
                q = input("> ").strip()
                if q.lower() in ("/quit", "/q", "exit"):
                    break
                if not q:
                    continue

                result = agent.ask(q)
                print(f"\n答案: {result['answer']}")
                if result.get("sources"):
                    pages = set(s["page"] for s in result["sources"])
                    print(f"来源: 第{','.join(map(str, sorted(pages)))}页")
                sc = result.get("self_check", {})
                print(f"自检: {sc.get('reason', '')} (置信度: {sc.get('confidence', 0):.0%})")
                print()

            except KeyboardInterrupt:
                print("\n再见!")
                break
            except Exception as e:
                logger.error(f"处理出错: {e}")
                print(f"错误: {e}")


if __name__ == "__main__":
    main()
