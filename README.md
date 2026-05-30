# 智能文档问答 Agent

基于扫描 PDF 的文档理解 + RAG 检索 + 自检验证原型系统。

Agent 开发工程师（大模型方向）技术笔试作业。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp config.example.yaml config.yaml
export DEEPSEEK_API_KEY="your-key"
# 编辑 config.yaml（如需修改模型或 OCR 参数）

# 3. 准备 PDF
# 将 GBT 1568-2008 键 技术条件.pdf 放入 data/ 目录

# 4. 运行
python main.py

# 5. 测试
python -m pytest tests/test_qa.py -v
```

## 架构概览

```
扫描PDF → tesseract OCR → 结构化文本(含页码+表格)
                              ↓
                       分块 + BGE Embedding
                              ↓
                      内存向量索引 + BM25
                              ↓
用户问题 → 条件混合检索 → Ollama/DeepSeek LLM → 答案自检 → 返回(答案+来源+自检)
```

> 检索策略：max_emb ≥ 0.45 时纯语义检索，低分时自动启用 BM25 关键词兜底（解决纯数值查询等场景）。详见[测试报告](docs/测试报告-test-report.md)。

## 模块清单

| 模块 | 说明 |
|------|------|
| `src/config.py` | 配置加载（YAML + 环境变量） |
| `src/pdf_parser.py` | PDF 类型判断 + tesseract OCR |
| `src/table_extractor.py` | 表格区域检测与结构化提取 |
| `src/chunker.py` | 文本分块（保留页码/条款编号） |
| `src/embedder.py` | Sentence-Transformers 向量化(支持 BGE/MiniLM 等) |
| `src/retriever.py` | 内存语义检索 + BM25 条件混合 + 来源溯源 |
| `src/generator.py` | LLM 问答生成（OpenAI 兼容接口，支持 Ollama/DeepSeek） |
| `src/self_checker.py` | 答案自检（LLM判断 依据/幻觉/拒答） |
| `tests/test_qa.py` | 11 个测试用例 |

## 设计文档

详见 [docs/](docs/) 目录：
- [作业说明](docs/作业说明-assignment.md) — 题目要求、测试用例、评估维度、提交清单
- [架构设计](docs/架构设计-design.md) — 架构、数据流、取舍
- [模块说明](docs/模块说明-modules.md) — 每个模块的输入/输出/逻辑
- [测试计划](docs/测试计划-test-plan.md) — 测试用例 + 评估指标
- [测试报告](docs/测试报告-test-report.md) — 优化前后对比 + 作业符合性验证
- [AI 使用说明](docs/AI使用说明-ai-usage.md) — AI 辅助方式 + 校验方法
- [演示脚本](docs/演示脚本-demo-script.md) — 演示视频录制指南

## 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| OCR | tesseract | 轻量、brew 安装、中文支持 |
| 向量检索 | 内存余弦相似度 + BM25 | 无外部依赖、条件混合策略 |
| Embedding | BGE-large-zh-v1.5 (可配) | 1024维，中文最优；也可用 MiniLM |
| LLM | Ollama/DeepSeek (OpenAI兼容) | 支持任意 OpenAI 兼容 API |
| PDF 操作 | PyMuPDF | 轻量高性能 |
|------|------|
| OCR | PaddleOCR |
| 向量库 | ChromaDB |
| Embedding | BGE-large-zh-v1.5 |
| LLM | DeepSeek API |
| PDF 操作 | PyMuPDF |

## 目录结构

```
doc-qa-agent/
├── README.md
├── config.example.yaml
├── requirements.txt
├── .gitignore
├── main.py
├── src/
│   ├── config.py
│   ├── pdf_parser.py
│   ├── table_extractor.py
│   ├── chunker.py
│   ├── embedder.py
│   ├── retriever.py
│   ├── generator.py
│   └── self_checker.py
├── tests/
│   └── test_qa.py
├── docs/
│   ├── README.md
│   ├── 作业说明-assignment.md
│   ├── 架构设计-design.md
│   ├── 模块说明-modules.md
│   ├── 测试计划-test-plan.md
│   ├── 测试报告-test-report.md
│   ├── AI使用说明-ai-usage.md
│   └── 演示脚本-demo-script.md
└── data/
    └── GBT 1568-2008 键 技术条件.pdf
```
