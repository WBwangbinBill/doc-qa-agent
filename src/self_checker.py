"""答案自检模块 — 依据检查 / 幻觉检测 / 拒答判断"""
import logging
from dataclasses import dataclass, field

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


class SelfChecker:
    """答案质量自检器"""

    def __init__(self, config: dict):
        sc_cfg = config.get("self_check", {})
        self.enabled = sc_cfg.get("enabled", True)
        self.min_evidence_length = sc_cfg.get("min_evidence_length", 10)
        self.hallucination_threshold = sc_cfg.get("hallucination_threshold", 0.2)

    def check(self, answer: Answer, retrieved: list[RetrievedChunk]) -> CheckResult:
        """自检答案质量"""
        if not self.enabled:
            return CheckResult(
                has_evidence=True, possible_hallucination=False,
                should_refuse=False, confidence=1.0, reason="自检已禁用"
            )

        answer_text = answer.answer
        has_retrieved = len(retrieved) > 0

        # 1. 拒答检测
        refuse_phrases = [
            "未找到相关信息", "没有相关信息", "无法找到",
            "文档中未找到", "未提及", "没有提到",
        ]
        answer_refused = any(p in answer_text for p in refuse_phrases)
        avg_score = sum(r.score for r in retrieved) / len(retrieved) if retrieved else 0

        if not has_retrieved:
            return CheckResult(
                has_evidence=False, possible_hallucination=False,
                should_refuse=True, confidence=0.0,
                reason="检索无结果"
            )

        # 2. 是否拒答——仅当整句拒答且无检索片段匹配时
        if answer_refused and (not has_retrieved or avg_score < self.hallucination_threshold):
            return CheckResult(
                has_evidence=False, possible_hallucination=False,
                should_refuse=True, confidence=0.5,
                reason="答案明确表示未找到相关信息且检索分数过低"
            )

        # 3. 依据检查
        # 检查答案中的关键实体是否在检索结果中出现
        answer_words = set(answer_text)
        retrieval_text = " ".join(r.content for r in retrieved)
        retrieval_words = set(retrieval_text)

        if len(answer_words) == 0:
            return CheckResult(
                has_evidence=False, possible_hallucination=True,
                should_refuse=False, confidence=0.0,
                reason="答案为空"
            )

        # 字符级重叠率
        overlap = len(answer_words & retrieval_words) / len(answer_words) if answer_words else 0

        # 4. 综合判断
        has_evidence = overlap > 0.3 or avg_score > 0.4
        possible_hallucination = overlap < self.hallucination_threshold and avg_score < 0.3
        should_refuse = not has_evidence and avg_score < self.hallucination_threshold

        # 置信度
        confidence = min(overlap, avg_score * 2, 1.0)

        # 构建理由
        reasons = []
        if has_evidence:
            reasons.append(f"答案与检索内容重叠率 {overlap:.0%}")
        if possible_hallucination:
            reasons.append(f"可能幻觉: 重叠率仅 {overlap:.0%}, 检索均分 {avg_score:.2f}")
        if should_refuse:
            reasons.append("建议拒答")
        if not reasons:
            reasons.append("自检通过")

        return CheckResult(
            has_evidence=has_evidence,
            possible_hallucination=possible_hallucination,
            should_refuse=should_refuse,
            confidence=round(confidence, 2),
            reason="; ".join(reasons),
        )
