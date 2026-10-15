"""JEV (TypeSafe System One 模型) 调用封装。

System One 模型只做结构化判断、不生成文字，正好做我们 agent 的「路由分类」。
本模块封装 POST https://api.typesafe.ai/v1/systemone 调用，并支持 mock 模式：
没有 API key 时返回启发式占位答案，仅用于跑通整套逻辑，不代表 JEV 真实判断。
"""

import json
import os
import time
import urllib.error
import urllib.request

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
MAX_RETRIES = 3


def call_jev(state, questions, api_key=None, model=JEV_MODEL, use_mock=None):
    """调用 JEV，返回 {model, answers, usage}。

    - use_mock=True 或没有 api_key 时走 mock（启发式占位）。
    - 真实模式下对 429/529 做指数退避重试；401/422 直接抛错不重试。
    """
    if use_mock is None:
        use_mock = os.environ.get("JEV_MOCK", "true").lower() in ("1", "true", "yes")
    if not use_mock:
        if api_key is None:
            api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            use_mock = True  # 没 key 自动降级 mock，保证逻辑可跑

    if use_mock:
        return _mock_jev(state, questions)

    payload = {"state": state, "model": model, "questions": questions}
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                JEV_ENDPOINT, data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 529) and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise  # 401 / 422 等不重试
        except Exception as e:  # 网络异常等
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_err


def _mock_jev(state, questions):
    """启发式占位答案——仅用于跑通逻辑，绝不代表 JEV 真实判断。"""
    text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    answers = {}
    for qid, q in questions.items():
        qtype = q.get("type")
        if qtype == "choice":
            choice, probs = _mock_choice(text, q.get("criteria", {}))
            conf = max(probs.values()) if probs else 1.0
            answers[qid] = {
                "type": "choice",
                "choice": choice,
                "probabilities": probs,
                "confidence": conf,
            }
        elif qtype == "noul":
            answers[qid] = {"type": "noul", "noul": _mock_noul(text)}
        else:
            answers[qid] = {"type": qtype}
    return {
        "model": "jev-mock",
        "answers": answers,
        "usage": {"input_tokens": max(1, len(text) // 4), "output_tokens": 10},
        "mock": True,
    }


def _mock_choice(text, criteria):
    keywords = {
        "todo": ["要做", "计划", "任务", "安排", "待办", "记得", "今天得", "明天要", "清单", "周报"],
        "existing_project": ["项目", "进展", "卡点", "下一步", "复盘", "迭代", "上线", "联调", "集成"],
        "inspiration": ["蓝图", "规划", "设想", "方案", "雏形", "打算做", "想做一个", "想法"],
        "essay": ["随笔", "今天", "感觉", "生活", "心情", "随手", "记录一下", "睡不着"],
        "life_talk": ["人生", "意义", "价值", "困惑", "迷茫", "想要", "活着", "为什么", "成功"],
    }
    scores = {}
    for cat, kws in keywords.items():
        if cat in criteria:
            scores[cat] = sum(1 for k in kws if k in text)
    if "other" in criteria:
        scores.setdefault("other", 0)
    if not scores or max(scores.values()) == 0:
        choice = "other" if "other" in criteria else (next(iter(criteria), "other"))
        probs = {c: (1.0 if c == choice else 0.0) for c in criteria}
        return choice, probs
    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    probs = {c: round(scores.get(c, 0) / total, 4) for c in criteria}
    return best, probs


def _mock_noul(text):
    """火花类（蓝图/随笔/人生探讨）→ 保守判 false（不调 LLM）。"""
    spark = ["蓝图", "规划", "设想", "方案", "雏形", "随笔", "今天", "感觉", "生活",
             "心情", "人生", "意义", "价值", "困惑", "迷茫", "活着", "成功", "睡不着"]
    if any(k in text for k in spark):
        return 0.15
    return 0.9
