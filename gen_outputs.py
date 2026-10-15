"""全链路跑通：route(分类+是否LLM) → 分流 → md_writer 落盘。

分流逻辑（P2/P3）：
- needs_llm=True  → 走 summarizer 生成 LLM 结构化总结，md 标 llm_summarized=true
- needs_llm=False → 走 extractor 用 JEV 打主标签，写进 frontmatter tags，正文原样保留

默认 MOCK 模式（route + extract 用 JEV mock，summarize 用 LLM mock）；
真实验证设 JEV_MOCK=false + TYPESAFE_API_KEY（及 LLM_* 配置）后重跑即可。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from router.route import route, needs_summary
from router.md_writer import save_md
from router.summarizer import summarize
from router.extractor import extract_fields

HERE = os.path.dirname(__file__)


def main():
    with open(os.path.join(HERE, "samples", "samples.json"), encoding="utf-8") as f:
        data = json.load(f)
    samples = data["samples"]
    use_mock = os.environ.get("JEV_MOCK", "true").lower() in ("1", "true", "yes")
    api_key = os.environ.get("TYPESAFE_API_KEY")
    out_dir = os.path.join(HERE, "outputs")
    paths = []
    for i, s in enumerate(samples, 1):
        r = route(s["text"], api_key=api_key, use_mock=use_mock)
        summary = None
        extra_fields = None
        if needs_summary(r):
            # P2：需要 LLM 总结的内容（蓝图类已排除）。LLM 用独立 LLM_API_KEY/env 解析，
            # 不把 JEV key 传进去（两者是不同服务）；没设 LLM key 自动降级 mock。
            summary = summarize(s["text"], r["final_skill"], use_mock=None)
        else:
            # P3：不进 LLM 的火花内容（含蓝图），用 JEV 打轻量标签（JEV key 正确传入）
            extra_fields = extract_fields(s["text"], api_key=api_key, use_mock=use_mock)
        p = save_md(s["text"], r, out_dir=out_dir, idx=i,
                    summary=summary, extra_fields=extra_fields)
        paths.append((i, r["final_skill"], r["needs_llm"], bool(summary), p))
    print(f"[{'MOCK' if use_mock else 'REAL'}] 已生成 {len(paths)} 个 md 到 {out_dir}")
    for i, skill, needs, did_sum, p in paths:
        tag = "LLM总结" if did_sum else ("JEV标签" if not needs else "待总结")
        print(f"  #{i:>2}  skill={skill:<16} need_llm={str(needs):<5} [{tag}] -> {os.path.basename(p)}")


if __name__ == "__main__":
    main()
