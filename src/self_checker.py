"""答案自检模块 — LLM 二次判断"""
import json
import logging
from dataclasses import dataclass
from openai import OpenAI

from src.generator import Answer
from src.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """自检结果"""
    has_evidence: bool
    possible_hallucination: bool
    should_refuse: bool
    confidence: float
    reason: str


CHECK_PROMPT = """你是一个答案质量检查器。判断以下答案是否基于给出的文档内容。

规则：
- has_evidence: 答案中的关键事实是否能在文档内容中找到依据？
- possible_hallucination: 答案中是否包含文档内容中没有的信息？
- should_refuse: 答案是否应该被拒答（完全没有找到相关信息）？
- confidence: 你对这个判断的置信度(0.0-1.0)

返回纯 JSON，不要包含其他文字：
{"has_evidence": true/false, "possible_hallucination": true/false, "should_refuse": true/false, "confidence": 0.0-1.0, "reason": "简短理由(20字内)"}

文档内容：
{context}

用户问题：{question}

待检查的答案：
{answer}"""


class SelfChecker:
    """基于 LLM 的答案自检器"""

    def __init__(self, config: dict):
        sc_cfg = config.get("self_check", {})
        self.enabled = sc_cfg.get("enabled", True)

        llm_cfg = config.get("llm", {})
        self.client = OpenAI(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
        )
        self.model = llm_cfg.get("model", "deepseek-chat")

    def check(self, question: str, answer: Answer, retrieved: list[RetrievedChunk]) -> CheckResult:
        """LLM 自检答案质量"""
        if not self.enabled:
            return CheckResult(
                has_evidence=True, possible_hallucination=False,
                should_refuse=False, confidence=1.0, reason="自检已禁用"
            )

        answer_text = answer.answer

        # 快速路径：检索无结果
        if not retrieved:
            return CheckResult(
                has_evidence=False, possible_hallucination=False,
                should_refuse=True, confidence=0.1,
                reason="检索无结果"
            )

        # 快速路径：答案含拒答短语
        refuse_phrases = [
            "未找到相关信息", "没有相关信息", "无法找到",
            "文档中未找到", "未提及", "没有提到",
        ]
        if any(p in answer_text for p in refuse_phrases):
            return CheckResult(
                has_evidence=False, possible_hallucination=False,
                should_refuse=True, confidence=0.9,
                reason="答案明确表示未找到相关信息"
            )

        # LLM 判断
        try:
            context = "\n\n".join(
                f"[来源{i+1}/第{r.page_num}页] {r.content[:400]}"
                for i, r in enumerate(retrieved[:3])
            )
            # 用 replace 避免 .format() 因答案/文档中的 {} 字符抛 KeyError
            prompt = CHECK_PROMPT.replace("{context}", context).replace(
                "{question}", question).replace("{answer}", answer_text)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            raw = response.choices[0].message.content.strip()

            # 提取 JSON
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]

            data = json.loads(raw)
            return CheckResult(
                has_evidence=bool(data.get("has_evidence", False)),
                possible_hallucination=bool(data.get("possible_hallucination", False)),
                should_refuse=bool(data.get("should_refuse", False)),
                confidence=round(float(data.get("confidence", 0.5)), 2),
                reason=str(data.get("reason", "LLM判断完成")),
            )
        except Exception as e:
            logger.warning(f"自检 LLM 调用失败，使用降级规则: {e}")
            return self._fallback_check(answer_text, retrieved)

    def _fallback_check(self, answer_text: str, retrieved: list[RetrievedChunk]) -> CheckResult:
        """降级规则：字符重叠 + 检索分"""
        avg_score = sum(r.score for r in retrieved) / len(retrieved) if retrieved else 0
        retrieval_text = " ".join(r.content for r in retrieved)
        answer_chars = set(answer_text)
        retrieval_chars = set(retrieval_text)

        if len(answer_chars) == 0:
            return CheckResult(False, False, True, 0.0, "答案为空")

        overlap = len(answer_chars & retrieval_chars) / len(answer_chars)
        has_evidence = overlap > 0.3 or avg_score > 0.45
        possible_hallucination = overlap < 0.2 and avg_score < 0.35
        confidence = round(min(overlap, avg_score * 2, 1.0), 2)

        return CheckResult(
            has_evidence=has_evidence,
            possible_hallucination=possible_hallucination,
            should_refuse=not has_evidence and avg_score < 0.3,
            confidence=confidence,
            reason=f"降级规则(LLM失败): 重叠率{overlap:.0%}, 检索均分{avg_score:.2f}",
        )
