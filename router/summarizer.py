"""按类别选择 LLM 总结风格（prompt 骨架），调用 llm_client 生成结构化总结。

原则：
- inspiration（蓝图）类永不进 LLM——用户原创思考火花原样保留，AI 不重写。
- 其余类别按 SKILL_PROMPTS 给不同风格的总结指令。
- 是否真调 LLM 由路由层的 need_llm 决定，本模块只负责「要总结时怎么总结」。
"""

from .llm_client import call_llm

# 各类别总结风格的系统提示词(给大模型看的指令)骨架——保持轻量，不写死过多规则
SKILL_PROMPTS = {
    "todo": (
        "你是一个高效的待办整理助手。请把用户的零散输入整理为清晰的待办清单："
        "① 用 - [ ] 勾选框列出每条待办；② 合并重复项；③ 若有明确时间/人物，标注在条目后；"
        "④ 不要新增用户没说的事。只输出清单，不解释。"
    ),
    "existing_project": (
        "你是一个项目复盘助手。请把用户的项目片段整理为结构化复盘："
        "【进展】/【卡点】/【下一步】三段，每段用要点列出。不虚构信息，只归纳用户已说内容。"
    ),
    "life_talk": (
        "你是一个思考梳理助手。请把用户的困惑/探讨整理为结构化思考："
        "【核心困惑】/【已有想法】/【待想清的问题】三段。保持用户原意，不替他下结论。"
    ),
    "essay": (
        "你是一个随笔提炼助手。请提炼用户随笔的主题与金句："
        "【主题】一句话 /【金句】摘录 1-3 句原话 /【情绪基调】。不重写，只提炼。"
    ),
}


def summarize(text, skill, api_key=None, base_url=None, model=None, use_mock=None):
    """对一段内容按类别做 LLM 总结，返回总结文本；inspiration 返回 None（不总结）。

    base_url / model 透传给 llm_client，方便在网页里改动接口地址或模型而不改代码。
    """
    if skill == "inspiration":
        return None  # 蓝图永不重写——这是用户原创火花
    prompt = SKILL_PROMPTS.get(skill)
    if not prompt:
        # other 等无模板类别：退化为通用整理
        prompt = "请把以下内容清晰、结构化地整理一遍，不虚构、不新增信息。"
    return call_llm(prompt, text, api_key=api_key, base_url=base_url,
                    model=model, use_mock=use_mock)
