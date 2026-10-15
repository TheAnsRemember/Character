"""JEV 双重判断路由：类别(Choice) + 是否需要 LLM(Noul)，再加 confidence 兜底。

这是我们 agent 的地基。代码不写死「哪类必须总结」的规则，完全由 JEV 动态决定：
- skill_route 决定内容属于哪一类（待办/已有项目/蓝图/随笔/人生探讨/其它）
- need_llm_summary 决定这份内容要不要调 LLM 总结
- confidence 过低（< CONFIDENCE_FLOOR）兜底归 other，不硬分
"""

from .jev_client import call_jev

CONFIDENCE_FLOOR = 0.4
NEED_LLM_THRESHOLD = 0.7

# 六类 skill 的 Choice criteria（描述要互相区分清楚，JEV 才能分对）
SKILL_CRITERIA = {
    "todo": "用户在整理待办事项、行动清单、任务安排",
    "existing_project": "用户在总结或复盘一个已存在、进行中的项目/工程",
    "inspiration": "用户在构思新项目的蓝图、规划、方案设想，只需结构化呈现、不需重新生成",
    "essay": "个人随笔、日记、随想、生活记录类内容",
    "life_talk": "人生探讨、价值观、困惑、深度思考类内容",
    "other": "以上都不合适，或意图不清",
}

# JEV 一次请求里的两个 question。静态配置，模块级常量只构造一次，
# 避免每次 route() 调用都重建嵌套 dict——省内存，也更贴合"配置即常量"的逻辑。
QUESTIONS = {
    "skill_route": {
        "type": "choice",
        "instructions": "这段用户内容应该用哪种处理方式总结？",
        "criteria": SKILL_CRITERIA,
    },
    "need_llm_summary": {
        "type": "noul",
        "instructions": "这份内容是否适合用 LLM 做总结整理（生成式提炼）？还是应保持原样、只存档？",
        "criteria": {
            "true": "内容适合被结构化整理（清单/复盘），LLM 能增值且不损失原创价值",
            "false": "内容是个人的创造性思考火花，应保持原样，不应被 LLM 重写或反馈",
        },
    },
}


def route(state, api_key=None, use_mock=None, need_llm_threshold=NEED_LLM_THRESHOLD):
    """对一段用户输入做双重判断，返回路由结果。

    返回字段：
      final_skill           最终类别（fallback 时归 other）
      skill_confidence      skill_route 的置信度
      skill_probabilities  各类概率分布
      need_llm_score       need_llm_summary 的 0~1 值
      needs_llm            是否要调 LLM（fallback 或 < 阈值则 False）
      fallback              是否因置信度低兜底
      usage                 JEV 返回的 token 用量（in/out），用于成本核算
    """
    resp = call_jev(state, QUESTIONS, api_key=api_key, use_mock=use_mock)
    answers = resp.get("answers", {})

    route_ans = answers.get("skill_route", {})
    noul_ans = answers.get("need_llm_summary", {})

    choice = route_ans.get("choice", "other")
    conf = route_ans.get("confidence", 0.0)
    probs = route_ans.get("probabilities", {})
    need_llm = noul_ans.get("noul", 0.5)
    usage = resp.get("usage", {})

    fallback = conf < CONFIDENCE_FLOOR
    final_skill = "other" if fallback else choice
    needs_llm = (not fallback) and (need_llm >= need_llm_threshold)

    return {
        "final_skill": final_skill,
        "skill_confidence": conf,
        "skill_probabilities": probs,
        "need_llm_score": need_llm,
        "needs_llm": needs_llm,
        "fallback": fallback,
        "usage": usage,
    }


def needs_summary(route_result):
    """是否实际走 LLM 总结。蓝图类永不进 LLM（用户原创火花原样保留），其余按 needs_llm 决定。

    集中这一判断，避免 gen_outputs 与 web 服务端两处分叉。
    """
    return bool(route_result["needs_llm"]) and route_result["final_skill"] != "inspiration"
