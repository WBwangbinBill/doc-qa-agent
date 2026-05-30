# 模块说明

## 模块清单

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 1 | 配置加载 | `src/config.py` | 读取 config.yaml + 环境变量 |
| 2 | PDF 解析 | `src/pdf_parser.py` | 判断 PDF 类型 + tesseract OCR |
| 3 | 表格提取 | `src/table_extractor.py` | 检测表格区域 + 结构化输出 |
| 4 | 文本分块 | `src/chunker.py` | 章节切分 + 保留页码/编号 |
| 5 | 向量化 | `src/embedder.py` | Sentence-Transformers 封装 |
| 6 | 检索 | `src/retriever.py` | 语义+BM25 条件混合检索 |
| 7 | 问答生成 | `src/generator.py` | OpenAI 兼容 LLM + 来源引用 |
| 8 | 答案自检 | `src/self_checker.py` | LLM 二次判断 依据/幻觉/拒答 |

---

## 模块 1：配置加载 `src/config.py`

### 输入
- `config.yaml` 文件（本地，不进 git）
- 环境变量（`${VAR:-default}` 展开）

### 输出
- 结构化的配置 dict

### 关键逻辑
```python
def load_config(config_path="config.yaml") -> dict:
    # 1. 读取 YAML 文件
    # 2. 正则展开 ${ENV_VAR:-default} 占位符
    # 3. 校验必填字段（llm.api_key）
    # 4. 返回 config dict
```

### 依赖
- pyyaml

---

## 模块 2：PDF 解析 `src/pdf_parser.py`

### 输入
- PDF 文件路径

### 输出
- `list[Page]`，每个 Page 包含：
  - `page_num`: 页码
  - `text_blocks`: `list[TextBlock]` 正文段落
  - `raw_text`: 整页原始文本
  - `is_scanned`: 是否扫描件

### 关键逻辑
```python
def parse_pdf(filepath, config) -> list[Page]:
    # 1. is_scanned_pdf() 检测文本层字符数
    #    → <100 字符判定为扫描件
    # 2. 扫描件 → _parse_scanned() → tesseract OCR (300 DPI)
    # 3. 文字版 → _parse_text() → fitz 直接提取
    # 4. 返回 Page 列表
```

### 依赖
- PyMuPDF (fitz)
- pytesseract + Pillow

### 边界处理
- PDF 无法打开 → `FileNotFoundError`
- OCR 失败 → 记录 warning，返回空 Page
- 空白页 → 跳过

---

## 模块 3：表格提取 `src/table_extractor.py`

### 输入
- 页面图像路径 + 页码

### 输出
- `list[Table]`，每个 Table 包含：
  - `page_num`, `headers`, `rows`, `caption`, `raw_text`
  - `to_text()` 方法：转为可读文本

### 关键逻辑
```python
def extract_tables_from_page(page_image_path, page_num) -> list[Table]:
    # 1. cv2 读取图像 → 灰度 → 二值化
    # 2. 检测水平线/垂直线 → 交点密度判断表格区域
    # 3. 轮廓面积 > 1000 判定为表格

def extract_tables_with_ocr(page_image_path, page_num) -> list[Table]:
    # 1. 尝试 PPStructure 表格识别
    # 2. 不可用时回退到 extract_tables_from_page()
```

### 依赖
- opencv-python（图像预处理）

> 当前表格提取仅检测区域，未完成结构化数据抽取（opencv 版本冲突），待后续优化。

---

## 模块 4：文本分块 `src/chunker.py`

### 输入
- `list[Page]` + `list[Table]`

### 输出
- `list[Chunk]`，每个 Chunk 包含：
  - `content`: `[第X页] 文本内容`
  - `page_num`, `chunk_type`, `section_id`

### 关键逻辑
```python
def chunk_documents(pages, tables, config) -> list[Chunk]:
    # 1. 逐级切分：双换行 → 单换行 → 硬切(max_chunk_size=300)
    # 2. 章节标题检测：正则匹配 "3 技术要求" "4.1 基本规则" 等
    #    → 遇到标题强制开启新 chunk
    # 3. overlap=80 保证边界平滑过渡
    # 4. 表格独立成块
```

### 依赖
- 无外部依赖（正则+字符串操作）

---

## 模块 5：向量化 `src/embedder.py`

### 输入
- `list[str]` 文本列表

### 输出
- `list[list[float]]` 向量列表（维度取决于模型，BGE=1024）

### 关键逻辑
```python
class Embedder:
    def __init__(self, config):
        # 加载 sentence-transformers 模型
        # 默认 paraphrase-multilingual-MiniLM-L12-v2 (384维)
        # 可配置为 BAAI/bge-large-zh-v1.5 (1024维)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # 批量向量化，normalize_embeddings=True

    def embed_query(self, text: str) -> list[float]:
        # 单条查询向量化
```

### 依赖
- sentence-transformers

---

## 模块 6：检索 `src/retriever.py`

### 输入
- 用户问题（str）

### 输出
- `list[RetrievedChunk]`:
  - `content`, `score`, `page_num`, `chunk_type`

### 关键逻辑
```python
def retrieve(self, query: str) -> list[RetrievedChunk]:
    # 1. query → embedding 向量
    # 2. 计算与所有 chunk 的余弦相似度
    # 3. 条件混合策略：
    #    max_emb ≥ 0.45 → 纯语义排名 (embedding only)
    #    max_emb < 0.45 → 0.7×emb + 0.3×BM25 混合兜底
    # 4. score_threshold=0.38 过滤低分
    # 5. 返回 top_k=5

def build_index(self, chunks):  # 构建语义+BM25双索引
def save/load(self, cache_dir, pdf_path):  # pickle 持久化
```

### 依赖
- jieba（BM25 分词）
- Embedder

### 设计说明
BM25 不全程启用，仅在语义分低时兜底（如纯数值"590 MPa"）。避免文档高频词"键"污染所有 chunk 的 BM25 得分。

---

## 模块 7：问答生成 `src/generator.py`

### 输入
- 用户问题（str）
- 检索结果（list[RetrievedChunk]）

### 输出
- `Answer`: `question`, `answer`, `sources[{page, content, score, type}]`

### Prompt 模板
```
根据以下文档内容回答问题。请仔细阅读所有片段后再判断。

规则：
1. 仔细检查每个片段，文档中只要有一个片段包含相关信息就应回答
2. 只有所有片段都不包含相关信息时，才说"文档中未找到相关信息"
3. 回答时引用具体内容和来源页码，不要编造
4. 回答简洁准确

文档内容：
{context}

问题：{question}

回答（请引用来源页码）：
```

### 关键设计
- Context 按页码排序（非相关度），帮助 LLM 理解文档逻辑结构
- 来源列表返回所有检索结果（非仅无 context 的 top chunks）

### 依赖
- openai SDK（兼容 Ollama/DeepSeek 等任意 OpenAI 兼容接口）

---

## 模块 8：答案自检 `src/self_checker.py`

### 输入
- `question` (str) — 用户问题
- `Answer` 对象
- 检索结果

### 输出
- `CheckResult`:
  - `has_evidence`: bool — 是否有检索依据
  - `possible_hallucination`: bool — 是否可能幻觉
  - `should_refuse`: bool — 是否应该拒答
  - `confidence`: float (0.0-1.0)
  - `reason`: str — 判断理由

### 关键逻辑
```python
def check(self, question, answer, retrieved) -> CheckResult:
    # 1. 检索无结果 → 直接拒答 (confidence=0.1)
    # 2. 答案含拒答短语 → 快速路径拒答 (confidence=0.9)
    #    短语: "未找到相关信息" "没有相关信息" "未提及" 等
    # 3. LLM 二次判断 → CHECK_PROMPT 让 LLM 评估
    # 4. LLM 失败 → 降级规则 (_fallback_check)
```

### 依赖
- openai SDK（复用 LLM 配置）

### 设计说明
从最初的字符级重叠率改为 LLM 二次判断后，拒答准确率从 ~20% 提升到 ~95%。快速路径处理明确的拒答短语，避免不必要的 LLM 调用。
