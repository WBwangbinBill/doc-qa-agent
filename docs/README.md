# 智能文档问答 Agent — 文档目录

> Agent 开发工程师（大模型方向）技术笔试作业

---

## 项目文档

| 文档 | 说明 |
|------|------|
| [项目 README](../README.md) | 快速开始、架构概览、模块清单 |
| [架构设计](design.md) | 整体架构、数据流、技术选型与取舍 |
| [模块说明](modules.md) | 8 个模块的详细设计（输入/输出/依赖） |
| [测试计划](test-plan.md) | 测试用例、评估指标、边界条件覆盖 |
| [AI 工具使用说明](ai-usage.md) | AI 辅助开发的方式、校验方法、经验总结 |

## 配置文件

| 文件 | 说明 |
|------|------|
| [config.example.yaml](../config.example.yaml) | 配置模板（可提交到 git） |

## 代码结构

```
doc-qa-agent/
├── README.md                  # 项目主文档
├── config.example.yaml        # 配置模板
├── config.yaml                # 本地配置（不提交）
├── requirements.txt           # 依赖清单
├── .gitignore
├── main.py                    # 入口
├── src/
│   ├── config.py              # 配置加载
│   ├── pdf_parser.py          # PDF 解析 + OCR
│   ├── table_extractor.py     # 表格提取
│   ├── chunker.py             # 文本分块
│   ├── embedder.py            # 向量化
│   ├── retriever.py           # 检索
│   ├── generator.py           # LLM 问答
│   └── self_checker.py        # 答案自检
├── tests/
│   └── test_qa.py             # 测试用例
├── docs/                      # 设计文档
│   ├── README.md              # 本文件
│   ├── design.md              # 架构设计
│   ├── modules.md             # 模块说明
│   ├── test-plan.md           # 测试计划
│   └── ai-usage.md            # AI 使用说明
└── data/
    └── GBT 1568-2008 键 技术条件.pdf
```

---

> 共 5 篇文档 + 1 个配置模板，覆盖设计、模块、测试、AI 使用四个维度。
