"""LLM 总结客户端：OpenAI 兼容 /v1/chat/completions 封装，支持 mock。

设计要点（贴合「怎样快怎样来」+ 零第三方依赖）：
- 只用标准库 urllib，不引 requests / openai SDK，内存占用最小。
- 默认走 OpenAI 官方接口，但本质是「OpenAI 兼容」协议：任何实现了
  /v1/chat/completions 的服务（OpenAI、Azure OpenAI、DeepSeek、智谱 GLM、
  StepFun、本地 Ollama/vLLM 等）都能直接用，只改 LLM_BASE_URL / LLM_MODEL 即可。
- 无 key 时自动降级 mock，只跑通逻辑，不代表真实总结质量。
"""

import json
import os
import time
import urllib.error
import urllib.request

# 默认走 OpenAI 官方接口。因为协议是 OpenAI 兼容的，换供应商只改这两个默认值、
# 或用环境变量 LLM_BASE_URL / LLM_MODEL 覆盖即可（如 DeepSeek: https://api.deepseek.com/v1）。
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
MAX_RETRIES = 3


def call_llm(system_prompt, user_text, api_key=None, base_url=None,
             model=None, use_mock=None):
    """调用 OpenAI 兼容接口，返回 assistant(助手) 文本。

    - use_mock=True 或没有 api_key 时走 mock（占位，仅跑通逻辑）。
    - 真实模式对 429/529 做指数退避重试；401/422 直接抛错不重试。
    """
    if use_mock is None:
        use_mock = os.environ.get("LLM_MOCK", "true").lower() in ("1", "true", "yes")
    if not use_mock:
        if api_key is None:
            api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            use_mock = True  # 没 key 自动降级 mock，保证逻辑可跑

    if use_mock:
        return _mock_llm(system_prompt, user_text)

    base = (base_url or LLM_BASE_URL).rstrip("/")
    model = model or LLM_MODEL
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.3,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                js = json.loads(resp.read().decode("utf-8"))
                return js["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 529) and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise  # 401 / 422 等不重试
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_err


def _mock_llm(system_prompt, user_text):
    """占位总结——明确标注 MOCK，便于和真总结区分，绝不代表真实质量。"""
    return (
        "【MOCK 总结占位，非真实 LLM 输出】\n"
        "（真实模式需配置 LLM_API_KEY + LLM_BASE_URL，并按类别 prompt 生成结构化总结）\n"
        f"原始内容长度：{len(user_text)} 字"
    )
