#!/usr/bin/env python3
"""智能文档问答 Agent — Web 界面"""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from src.config import load_config
from main import DocQAAgent

# 全局 agent 实例
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        config = load_config("config.yaml")
        data_dir = Path(config.get("pdf", {}).get("input_dir", "data"))
        pdfs = list(data_dir.glob("*.pdf"))
        if not pdfs:
            raise FileNotFoundError("未找到 PDF 文件")
        _agent = DocQAAgent(config)
        stats = _agent.build_knowledge_base(str(pdfs[0]))
        print(f"知识库就绪: {stats}")
    return _agent


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>智能文档问答 Agent</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }
.header { background: #1a1a2e; color: #fff; padding: 20px 30px; display: flex; align-items: center; gap: 15px; }
.header h1 { font-size: 20px; font-weight: 600; }
.header .badge { background: #16213e; padding: 4px 12px; border-radius: 12px; font-size: 12px; color: #7ec8e3; }
.container { max-width: 900px; margin: 0 auto; padding: 20px; }
.input-area { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 20px; }
.input-area textarea { width: 100%; border: 2px solid #e0e0e0; border-radius: 8px; padding: 14px; font-size: 15px; resize: vertical; min-height: 60px; font-family: inherit; transition: border-color 0.2s; }
.input-area textarea:focus { outline: none; border-color: #1a73e8; }
.input-area .actions { display: flex; gap: 10px; margin-top: 12px; align-items: center; }
.input-area button { background: #1a73e8; color: #fff; border: none; border-radius: 8px; padding: 10px 24px; font-size: 15px; cursor: pointer; font-weight: 500; transition: background 0.2s; }
.input-area button:hover { background: #1557b0; }
.input-area button:disabled { background: #ccc; cursor: not-allowed; }
.input-area .presets { display: flex; gap: 8px; flex-wrap: wrap; }
.input-area .preset { background: #e8f0fe; color: #1a73e8; border: none; border-radius: 16px; padding: 6px 14px; font-size: 13px; cursor: pointer; transition: background 0.2s; }
.input-area .preset:hover { background: #d2e3fc; }
.result { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 16px; display: none; }
.result.show { display: block; }
.result .question-label { font-size: 13px; color: #888; margin-bottom: 4px; }
.result .question-text { font-size: 17px; font-weight: 600; color: #1a1a2e; margin-bottom: 20px; }
.answer-box { background: #f8fafc; border-left: 4px solid #1a73e8; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-bottom: 20px; font-size: 15px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.meta { display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 16px; }
.meta-item { background: #f0f0f0; padding: 8px 14px; border-radius: 8px; font-size: 13px; }
.meta-item .label { color: #888; }
.meta-item .value { font-weight: 600; color: #333; }
.meta-item.warn .value { color: #e67e22; }
.meta-item.ok .value { color: #27ae60; }
.meta-item.bad .value { color: #e74c3c; }
.sources { border-top: 1px solid #eee; padding-top: 16px; }
.sources h3 { font-size: 14px; color: #888; margin-bottom: 10px; }
.source-item { background: #fafafa; padding: 12px; border-radius: 8px; margin-bottom: 8px; font-size: 13px; }
.source-item .src-page { color: #1a73e8; font-weight: 600; }
.source-item .src-score { color: #888; }
.source-item .src-text { color: #555; margin-top: 4px; line-height: 1.5; }
.loading { text-align: center; padding: 30px; color: #888; display: none; }
.loading.show { display: block; }
.spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid #e0e0e0; border-top-color: #1a73e8; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="header">
  <h1>📄 智能文档问答 Agent</h1>
  <span class="badge">GBT 1568-2008 键 技术条件</span>
</div>
<div class="container">
  <div class="input-area">
    <textarea id="question" placeholder="输入你的问题，例如：键的材料要求是什么？" rows="2"></textarea>
    <div class="actions">
      <button id="askBtn" onclick="ask()">🔍 提问</button>
    </div>
    <div class="presets" style="margin-top:12px">
      <button class="preset" onclick="setPreset('键的材料要求是什么')">键的材料要求</button>
      <button class="preset" onclick="setPreset('键的尺寸公差是多少')">键的尺寸公差</button>
      <button class="preset" onclick="setPreset('第5条规定了什么')">第5条规定了什么</button>
      <button class="preset" onclick="setPreset('这份标准里有没有提到钛合金键')">钛合金键(无答案)</button>
      <button class="preset" onclick="setPreset('健的技术条件')">OCR容错</button>
      <button class="preset" onclick="setPreset('键的表面处理要求')">表面处理要求</button>
    </div>
  </div>
  <div class="loading" id="loading"><span class="spinner"></span>正在检索和分析...</div>
  <div class="result" id="result">
    <div class="question-label">问题</div>
    <div class="question-text" id="qText"></div>
    <div class="answer-box" id="answer"></div>
    <div class="meta">
      <div class="meta-item" id="metaConf"><span class="label">置信度 </span><span class="value"></span></div>
      <div class="meta-item" id="metaRetrieved"><span class="label">检索结果 </span><span class="value"></span></div>
      <div class="meta-item" id="metaEvidence"><span class="label">依据 </span><span class="value"></span></div>
      <div class="meta-item" id="metaRefuse"><span class="label">拒答 </span><span class="value"></span></div>
      <div class="meta-item" id="metaHallu"><span class="label">幻觉风险 </span><span class="value"></span></div>
    </div>
    <div class="sources" id="sources"></div>
  </div>
</div>
<script>
function setPreset(q) { document.getElementById('question').value = q; ask(); }
function $(id) { return document.getElementById(id); }

async function ask() {
  const q = $('question').value.trim();
  if (!q) return;

  $('result').classList.remove('show');
  $('loading').classList.add('show');
  $('askBtn').disabled = true;

  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });
    const data = await resp.json();

    $('qText').textContent = data.question;
    $('answer').textContent = data.answer || '(空)';

    const sc = data.self_check || {};
    const conf = (sc.confidence || 0) * 100;

    $('metaConf').querySelector('.value').textContent = conf.toFixed(0) + '%';
    $('metaRetrieved').querySelector('.value').textContent = data.retrieved_count + ' 条';
    $('metaEvidence').querySelector('.value').textContent = sc.has_evidence ? '有依据' : '无依据';
    $('metaRefuse').querySelector('.value').textContent = sc.should_refuse ? '是' : '否';
    $('metaHallu').querySelector('.value').textContent = sc.possible_hallucination ? '⚠ 有风险' : '无风险';

    // 样式
    ['metaConf','metaRetrieved','metaEvidence','metaRefuse','metaHallu'].forEach(id => {
      $(id).classList.remove('ok','warn','bad');
    });
    $('metaConf').classList.add(conf >= 80 ? 'ok' : conf >= 50 ? 'warn' : 'bad');
    $('metaEvidence').classList.add(sc.has_evidence ? 'ok' : 'bad');
    $('metaRefuse').classList.add(sc.should_refuse ? 'warn' : 'ok');
    $('metaHallu').classList.add(sc.possible_hallucination ? 'bad' : 'ok');

    // 来源
    let srcHtml = '<h3>📎 来源引用</h3>';
    if (data.sources && data.sources.length > 0) {
      data.sources.forEach(s => {
        srcHtml += `<div class="source-item">
          <span class="src-page">第${s.page}页</span>
          <span class="src-score">相关度: ${(s.score*100).toFixed(0)}%</span>
          <div class="src-text">${s.content.substring(0, 150)}...</div>
        </div>`;
      });
    } else {
      srcHtml += '<div class="source-item" style="color:#888">无检索结果</div>';
    }
    $('sources').innerHTML = srcHtml;

    $('result').classList.add('show');
  } catch (e) {
    $('answer').textContent = '请求失败: ' + e.message;
    $('result').classList.add('show');
  } finally {
    $('loading').classList.remove('show');
    $('askBtn').disabled = false;
  }
}

document.getElementById('question').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
});
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/ask":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            question = data.get("question", "").strip()

            if not question:
                result = {"error": "请输入问题"}
            else:
                agent = get_agent()
                result = agent.ask(question)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 关闭访问日志


def main():
    port = 9527
    print(f"\n  智能文档问答 Agent Web 界面")
    print(f"  打开浏览器访问: http://localhost:{port}\n")
    get_agent()  # 预热
    server = HTTPServer(("0.0.0.0", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
