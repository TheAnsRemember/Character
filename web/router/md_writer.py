"""把 route 结果 + 原始内容生成标准 md 文件（frontmatter + 正文），落盘到 outputs/。

frontmatter 字段（全类统一，供下游办公 agent 解析）：
  type            类别（todo / existing_project / inspiration / essay / life_talk / other）
  need_llm        是否判定需要 LLM 总结（来自 JEV 的 need_llm_summary 判断）
  llm_summarized  是否实际经过 LLM 总结（传入 summary 时为 true）
  date            处理日期
  tags（可选）    JEV 轻量提取的主标签（仅不进 LLM 的内容有，P3 填充）

正文规则：
- 进 LLM 总结的内容：正文 = 「## 总结」(LLM 结构化输出) + 「## 原文」(用户原话，不丢)。
- 判定要 LLM 但本次没跑（如 mock 阶段）：保留原样 + 一行待办标注。
- 不进 LLM 的火花内容：原样保留用户原话，AI 不篡改，只在 frontmatter 加标签。
"""

import os
from datetime import date as _date, datetime


def generate_md(state, route_result, summary=None, extra_fields=None, date=None, project=None):
    final_skill = route_result["final_skill"]
    needs_llm = route_result["needs_llm"]
    d = date or _date.today().isoformat()
    # 有 summary 才算真正做过 LLM 总结
    llm_summarized = bool(summary)

    fm = [
        "---",
        f"type: {final_skill}",
        f"need_llm: {str(needs_llm).lower()}",
        f"llm_summarized: {str(llm_summarized).lower()}",
        f"date: {d}",
    ]
    # P3：把 JEV 轻量提取的字段写进 frontmatter，便于下游解析
    if extra_fields:
        for k, v in extra_fields.items():
            if isinstance(v, list):
                fm.append(f"{k}: [{', '.join(repr(x) for x in v)}]")
            else:
                fm.append(f"{k}: {v}")
    if project:
        fm.append(f"project: {project}")
    fm.append("---")
    fm.append("")

    if summary:
        # 进 LLM：总结在前、原文在后，二者都留着
        body = "## 总结\n\n" + summary + "\n\n## 原文\n\n" + state
    elif needs_llm and not llm_summarized and final_skill != "inspiration":
        # 判定需要 LLM 总结，但本次没跑（如 mock 阶段）——保留原样并标注
        body = (
            "<!-- 待 LLM 总结：JEV 判定此内容需要结构化整理 -->\n\n" + state
        )
    else:
        # 原样保留用户思考火花，AI 不篡改
        body = state

    return "\n".join(fm) + body + "\n"


def save_md(state, route_result, out_dir="outputs", idx=None,
            summary=None, extra_fields=None, project=None):
    d = _date.today().isoformat()
    skill = route_result["final_skill"]
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{d}_{skill}_{idx if idx is not None else 'x'}.md"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_md(state, route_result, summary=summary,
                            extra_fields=extra_fields, date=d, project=project))
    return path


def generate_raw_md(state, project=None, date=None):
    """纯原文 md（存档用）：只留 frontmatter + 原文，不写总结/标签/待办标注。"""
    d = date or _date.today().isoformat()
    fm = ["---", "type: raw", f"date: {d}"]
    if project:
        fm.append(f"project: {project}")
    fm.append("---")
    fm.append("")
    return "\n".join(fm) + state + "\n"


def save_raw_md(state, out_dir="outputs", project=None, ts=None):
    """先存档：把原始内容落盘成纯原文 md，不依赖 JEV/LLM。"""
    d = _date.today().isoformat()
    os.makedirs(out_dir, exist_ok=True)
    if ts is None:
        ts = datetime.now().strftime("%H%M%S")
    fname = f"{d}_raw_{ts}.md"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_raw_md(state, project=project, date=d))
    return path
