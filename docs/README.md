# 智能文档问答 Agent — 文档目录

> Agent 开发工程师（大模型方向）技术笔试作业

---

## 项目文档

| 文档 | 说明 |
|------|------|
| [项目 README](../README.md) | 快速开始、架构概览、模块清单 |
| [作业说明](作业说明-assignment.md) | 完整原始题目、测试用例、评估维度、提交清单 |
| [架构设计](架构设计-design.md) | 整体架构、数据流、技术选型与取舍 |
| [模块说明](模块说明-modules.md) | 8 个模块的详细设计（输入/输出/依赖） |
| [测试计划](测试计划-test-plan.md) | 测试用例、评估指标、边界条件覆盖 |
| [测试报告](测试报告-test-report.md) | 优化前后对比、BM25混合检索、作业符合性验证 |
| [AI 工具使用说明](AI使用说明-ai-usage.md) | AI 辅助开发的方式、校验方法、经验总结 |
| [演示脚本](演示脚本-demo-script.md) | 演示视频录制指南 |

## 配置文件

| 文件 | 说明 |
|------|------|
| [config.example.yaml](../config.example.yaml) | 配置模板（可提交到 git） |

## 代码结构

```
doc-qa-agent/
├── README.md                  # 项目主文档
├── config.example.yaml        # 配置模板
├── requirements.txt           # 依赖清单
├── .gitignore
├── main.py                    # 入口
├── src/
│   ├── __init__.py
│   ├── config.py              # 配置加载
│   ├── pdf_parser.py          # PDF 解析 + tesseract OCR
│   ├── table_extractor.py     # 表格提取
│   ├── chunker.py             # 文本分块
│   ├── embedder.py            # 向量化
│   ├── retriever.py           # 语义+BM25混合检索
│   ├── generator.py           # LLM 问答
│   └── self_checker.py        # LLM自检
├── tests/
│   ├── __init__.py
│   └── test_qa.py             # 11 个测试用例
├── docs/                      # 设计文档
│   ├── README.md              # 本文件
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

---

> 共 8 篇文档 + 1 个配置模板，覆盖题目、设计、模块、测试、AI 使用、演示六个维度。
