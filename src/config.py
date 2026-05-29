"""配置加载模块"""
import os
import re
import yaml
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置，展开环境变量引用 ${VAR:-default}。"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"配置文件 {config_path} 不存在。"
            f"请复制 config.example.yaml 为 config.yaml 并填入配置。"
        )

    with open(path) as f:
        raw = f.read()

    def _env(m):
        var = m.group(1)
        default = m.group(2) if m.lastindex >= 2 else ""
        return os.environ.get(var, default)

    raw = re.sub(r'\$\{(\w+)(?::-([^}]*))?\}', _env, raw)
    config = yaml.safe_load(raw) or {}

    # 校验必填字段
    api_key = config.get("llm", {}).get("api_key", "")
    if not api_key or api_key.startswith("${"):
        raise ValueError(
            "LLM API Key 未配置。请设置环境变量 DEEPSEEK_API_KEY "
            "或在 config.yaml 中填写 api_key。"
        )

    return config
