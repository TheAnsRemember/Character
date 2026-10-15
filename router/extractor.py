"""P3：对「不进 LLM 总结」的内容做 JEV 轻量字段提取（主标签），写入 frontmatter extra_fields。

原则：只提取少量结构化字段，绝不改写正文。蓝图/随笔/人生探讨这类火花内容靠这个打标签，
下游办公 agent 就能按标签检索归档，而不需要 AI 去动原话。

为什么用 JEV 而不是 LLM：JEV 只做结构化判断、不生成文字、又快又便宜，
给火花类内容打标签属于「判断」而非「创作」，正好契合它的定位。
"""

from .jev_client import call_jev

# 轻量标签体系（JEV Choice 候选）——够下游检索用即可，不铺太大
TAG_TAXONOMY = {
    "work": "工作 / 业务 / 项目相关",
    "product": "产品 / 创业 / 硬件相关",
    "personal": "个人情绪 / 生活记录",
    "philosophy": "价值观 / 人生思考",
    "relation": "人际 / 家庭 / 情感",
    "other": "以上都不明显",
}

QUESTIONS = {
    "primary_tag": {
        "type": "choice",
        "instructions": "这段用户内容主要属于哪个主题标签？",
        "criteria": TAG_TAXONOMY,
    }
}


def extract_fields(text, api_key=None, use_mock=None):
    """返回 {'tags': [主标签]}。mock 走启发式占位，仅供跑通逻辑。"""
    resp = call_jev(text, QUESTIONS, api_key=api_key, use_mock=use_mock)
    ans = resp.get("answers", {}).get("primary_tag", {})
    tag = ans.get("choice", "other")
    return {"tags": [tag]}
