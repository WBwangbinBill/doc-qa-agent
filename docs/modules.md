# 模块说明

## 模块清单

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 1 | 配置加载 | `src/config.py` | 读取 config.yaml + 环境变量 |
| 2 | PDF 解析 | `src/pdf_parser.py` | 判断 PDF 类型 + PaddleOCR 识别 |
| 3 | 表格提取 | `src/table_extractor.py` | 检测表格区域 + 结构化输出 |
| 4 | 文本分块 | `src/chunker.py` | 按段落切分 + 保留页码/编号 |
| 5 | 向量化 | `src/embedder.py` | BGE Embedding 封装 |
| 6 | 检索 | `src/retriever.py` | ChromaDB 语义检索 + 页码溯源 |
| 7 | 问答生成 | `src/generator.py` | DeepSeek LLM 调用 + 来源引用 |
| 8 | 答案自检 | `src/self_checker.py` | 依据检查 / 幻觉检测 / 拒答判断 |

---

## 模块 1：配置加载 `src/config.py`

### 输入
- `config.yaml` 文件（本地，不进 git）
- 环境变量（如 `DEEPSEEK_API_KEY`）

### 输出
- 结构化的配置 dict

### 关键逻辑
```python
def load_config():
    # 1. 读取 config.yaml
    # 2. 展开 ${ENV_VAR} 占位符
    # 3. 校验必填字段
    # 4. 返回 config dict
```

### 依赖
- 无

---

## 模块 2：PDF 解析 `src/pdf_parser.py`

### 输入
- PDF 文件路径

### 输出
- `list[Page]`，每个 Page 包含：
  - `page_num`: 页码
  - `text_blocks`: 正文段落列表
  - `raw_text`: 整页原始文本
  - `has_table`: 是否检测到表格

### 关键逻辑
```python
def parse_pdf(filepath) -> list[Page]:
    # 1. 用 fitz/PyMuPDF 打开 PDF
    # 2. 判断是否扫描件（文本层是否为空）
    # 3. 如果是扫描件 → 逐页转图像 → PaddleOCR
    # 4. 如果有文本层 → 直接提取
    # 5. 返回 Page 列表
```

### 依赖
- PyMuPDF（PDF 操作）
- PaddleOCR（OCR 识别）

### 边界处理
- 空白页 → 跳过
- OCR 置信度低 → 标记 `low_confidence`
- 图片质量差 → 提示用户

---

## 模块 3：表格提取 `src/table_extractor.py`

### 输入
- Page 对象（包含图像路径）

### 输出
- `list[Table]`，每个 Table 包含：
  - `page_num`: 所在页码
  - `headers`: 表头行
  - `rows`: 数据行列表
  - `caption`: 表格标题（如有）
  - `raw_text`: 表格线文本

### 关键逻辑
```python
def extract_tables(page_image, page_num) -> list[Table]:
    # 1. 用 PaddleOCR 的表格识别（或 table-ocr 子模块）
    # 2. 解析表格结构（行/列/单元格）
    # 3. 提取表头和数据
    # 4. 转为结构化 dict
```

### 依赖
- PaddleOCR（表格识别）
- opencv-python（图像预处理）

### 边界处理
- 无线框表格 → 尝试识别对齐的文本块
- 表格半页 → 标记 `partial_table`

---

## 模块 4：文本分块 `src/chunker.py`

### 输入
- `list[Page]` + `list[Table]`

### 输出
- `list[Chunk]`，每个 Chunk 包含：
  - `content`: 文本内容
  - `page_num`: 来源页码
  - `chunk_type`: "text" | "table" | "clause"
  - `section_id`: 条款编号（如 "5.2"）

### 关键逻辑
```python
def chunk_documents(pages, tables) -> list[Chunk]:
    # 1. 正文按段落分块（≤500字）
    # 2. 表格单独成块（保留表格文本 + 页码）
    # 3. 条款编号识别（正则匹配 "1.2.3" 模式）
    # 4. 每块 metadata 包含来源页码
```

### 依赖
- 无外部依赖

---

## 模块 5：向量化 `src/embedder.py`

### 输入
- `list[str]` 文本列表

### 输出
- `list[list[float]]` 向量列表（1024 维）

### 关键逻辑
```python
class Embedder:
    def __init__(self, config):
        # 初始化 BGE 模型或使用 API

    def embed(self, texts: list[str]) -> list[list[float]]:
        # 批量向量化
```

### 依赖
- BGE 模型（本地）或 OpenAI Embedding API

---

## 模块 6：检索 `src/retriever.py`

### 输入
- 用户问题（str）
- top_k（int）
- score_threshold（float）

### 输出
- `list[RetrievedChunk]`，包含：
  - `content`: 片段文本
  - `score`: 相似度
  - `page_num`: 来源页码
  - `chunk_type`: 正文/表格/条款

### 关键逻辑
```python
def retrieve(query, top_k=5, threshold=0.3) -> list[RetrievedChunk]:
    # 1. query → embedding
    # 2. ChromaDB 相似度检索
    # 3. 过滤低于阈值的
    # 4. 返回 top_k 条 + metadata
```

### 依赖
- ChromaDB
- Embedder

---

## 模块 7：问答生成 `src/generator.py`

### 输入
- 用户问题（str）
- 检索结果（list[RetrievedChunk]）

### 输出
- `Answer`：
  - `answer`: 答案文本
  - `sources`: 来源列表 `[{page_num, content_snippet}]`

### 关键逻辑
```python
def generate(query, retrieved) -> Answer:
    # 1. 构建 prompt（含检索片段 + 页码）
    # 2. 调用 DeepSeek API
    # 3. 解析来源引用
    # 4. 返回 Answer 对象
```

### Prompt 模板
```
根据以下文档内容回答问题。如果文档中没有相关信息，请明确说"文档中未找到相关信息"。
回答时请引用来源页码。

文档内容：
[片段1] (第X页) ...
[片段2] (第Y页) ...

问题：{query}

回答（请引用页码）：
```

### 依赖
- DeepSeek API（openai 兼容 SDK）

---

## 模块 8：答案自检 `src/self_checker.py`

### 输入
- Answer 对象
- 检索结果

### 输出
- `CheckResult`：
  - `has_evidence`: bool — 是否有检索依据
  - `possible_hallucination`: bool — 是否可能幻觉
  - `should_refuse`: bool — 是否应该拒答
  - `confidence`: float — 置信度
  - `reason`: str — 判断理由

### 关键逻辑
```python
def check(answer, retrieved) -> CheckResult:
    # 1. 检查 answer 中引用的页码是否在 retrieved 中
    # 2. 检查 answer 中的关键实体是否在 retrieved 中出现
    # 3. 如果检索相关度 < 阈值 → 可能幻觉
    # 4. 如果检索结果为空 → 建议拒答
```

### 依赖
- 无（纯规则 + 启发式）

### 判断规则
| 条件 | 结论 |
|------|------|
| 检索结果为空 | 应拒答 |
| 答案实体不在检索片段中 | 可能幻觉 |
| 答案长度 < 10 字符 | 低置信度 |
| 检索分数 > 0.5 + 实体匹配 | 有依据 |
