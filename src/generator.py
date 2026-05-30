"""问答生成模块 — DeepSeek LLM + 来源引用"""
import logging
import json
from dataclasses import dataclass, field
from openai import OpenAI

from src.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class Answer:
    """问答结果"""
    question: str
    answer: str
    sources: list[dict] = field(default_factory=list)
    # sources: [{"page": int, "content": str, "score": float}]


class Generator:
    """基于 LLM 的答案生成器"""

    PROMPT_TEMPLATE = """根据以下文档内容回答问题。请仔细阅读所有片段后再判断。

规则：
1. 仔细检查每个片段，文档中只要有一个片段包含相关信息就应回答
2. 只有所有片段都不包含相关信息时，才说"文档中未找到相关信息"
3. 回答时引用具体内容和来源页码，不要编造
4. 回答简洁准确

文档内容：
{context}

问题：{question}

回答（请引用来源页码）："""

    def __init__(self, config: dict):
        llm_cfg = config.get("llm", {})
        self.client = OpenAI(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
        )
        self.model = llm_cfg.get("model", "deepseek-chat")
        self.temperature = llm_cfg.get("temperature", 0.1)
        self.max_tokens = llm_cfg.get("max_tokens", 1024)

    def generate(self, question: str, retrieved: list[RetrievedChunk]) -> Answer:
        """根据检索结果生成答案"""
        if not retrieved:
            return Answer(
                question=question,
                answer="文档中未找到相关信息。",
                sources=[],
            )

        # 构建 context：按页码排序，帮助 LLM 理解文档逻辑
        top_chunks = sorted(retrieved, key=lambda c: (c.page_num, c.score))
        context_parts = []
        for i, chunk in enumerate(top_chunks):
            context_parts.append(
                f"[片段{i+1}] (第{chunk.page_num}页, 相关度{chunk.score:.2f})\n{chunk.content}"
            )

        context = "\n\n".join(context_parts)
        prompt = self.PROMPT_TEMPLATE.format(context=context, question=question)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            answer_text = response.choices[0].message.content.strip()

            # 构建来源列表（所有检索结果，不只是 top 3）
            sources = []
            for chunk in retrieved:
                sources.append({
                    "page": chunk.page_num,
                    "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    "score": chunk.score,
                    "type": chunk.chunk_type,
                })

            return Answer(question=question, answer=answer_text, sources=sources)

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return Answer(
                question=question,
                answer=f"生成答案时出错: {str(e)}",
                sources=[{"page": c.page_num, "content": c.content[:100], "score": c.score} for c in retrieved],
            )
