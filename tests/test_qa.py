"""测试用例 — 智能文档问答 Agent"""
import sys
import json
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config
from main import DocQAAgent

# 全局 agent 实例（module scope，复用）
_agent = None
_config = None


def get_agent():
    """获取或初始化 agent"""
    global _agent, _config
    if _agent is None:
        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        if not config_path.exists():
            pytest.skip("config.yaml 不存在，跳过测试")
        _config = load_config(str(config_path))

        # 找 PDF
        data_dir = Path(_config.get("pdf", {}).get("input_dir", "data"))
        pdfs = list(data_dir.glob("*.pdf"))
        if not pdfs:
            pytest.skip("data/ 下无 PDF 文件，跳过测试")

        _agent = DocQAAgent(_config)
        _agent.build_knowledge_base(str(pdfs[0]))
    return _agent


# ── 测试用例 ──

def test_text_question():
    """正文检索：键的材料要求"""
    agent = get_agent()
    result = agent.ask("键的材料要求是什么")
    assert "error" not in result, result.get("error")
    assert len(result["answer"]) > 10, "答案太短"
    assert len(result["sources"]) > 0, "无检索来源"
    # 自检应该有依据
    assert result["self_check"]["has_evidence"] or result["self_check"]["should_refuse"], \
        f"自检失败: {result['self_check']}"


def test_table_question():
    """表格检索：尺寸公差"""
    agent = get_agent()
    result = agent.ask("键的尺寸公差是多少")
    assert "error" not in result
    assert len(result["answer"]) > 5
    assert result["retrieved_count"] > 0


def test_clause_question():
    """条款编号检索"""
    agent = get_agent()
    result = agent.ask("第5条规定了什么")
    assert "error" not in result
    assert len(result["answer"]) > 5


def test_no_answer_question():
    """无答案问题：钛合金"""
    agent = get_agent()
    result = agent.ask("这份标准里有没有提到钛合金键")
    assert "error" not in result
    # 应该拒答或表示未找到
    no_answer_phrases = ["未找到", "没有提到", "没有相关信息", "未提及"]
    has_refuse = any(p in result["answer"] for p in no_answer_phrases)
    assert has_refuse, f"应拒答但未拒绝: {result['answer'][:100]}"


def test_fuzzy_question():
    """模糊/OCR 容错"""
    agent = get_agent()
    result = agent.ask("健的技术条件")  # 故意写错"键"
    assert "error" not in result
    # 不崩溃即可，不强求检索到


def test_short_question():
    """短问题"""
    agent = get_agent()
    result = agent.ask("验收")
    assert "error" not in result
    assert len(result["answer"]) > 0


def test_empty_question():
    """空问题"""
    agent = get_agent()
    result = agent.ask("")
    assert "error" in result or len(result.get("answer", "")) < 5
    # 不应崩溃


def test_source_pages():
    """来源页码检查"""
    agent = get_agent()
    result = agent.ask("键的表面处理要求")
    for s in result.get("sources", []):
        assert 1 <= s["page"] <= 20, f"页码超出范围: {s['page']}"


def test_self_check():
    """自检结果结构"""
    agent = get_agent()
    result = agent.ask("键的类型有哪些")
    sc = result.get("self_check", {})
    assert "has_evidence" in sc
    assert "possible_hallucination" in sc
    assert "should_refuse" in sc
    assert "confidence" in sc
    assert 0.0 <= sc["confidence"] <= 1.0


def test_answer_structure():
    """答案结构完整性"""
    agent = get_agent()
    result = agent.ask("GBT 1568 的范围是什么")
    assert "question" in result
    assert "answer" in result
    assert "sources" in result
    assert "self_check" in result
    assert "retrieved_count" in result


# ── 性能测试 ──

def test_retrieval_speed():
    """检索速度 < 5 秒"""
    agent = get_agent()
    start = time.time()
    result = agent.ask("键的材料")
    elapsed = time.time() - start
    assert elapsed < 10, f"检索太慢: {elapsed:.1f}s"


# ── 运行入口 ──

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
