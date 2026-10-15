"""JEV 路由验证脚本：遍历 samples，对比预期算准确率，生成 evals/route_report.md。

默认 MOCK 模式（无 key 也能跑通逻辑）；要真实验证：
  export TYPESAFE_API_KEY=你的key
  export JEV_MOCK=false
  python run_eval.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from router.route import route

HERE = os.path.dirname(__file__)


def load_samples():
    with open(os.path.join(HERE, "samples", "samples.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["samples"], data.get("meta", "")


def main():
    samples, meta = load_samples()
    use_mock = os.environ.get("JEV_MOCK", "true").lower() in ("1", "true", "yes")
    api_key = os.environ.get("TYPESAFE_API_KEY")
    mode = "MOCK (启发式占位，不代表 JEV 真实判断)" if use_mock else "REAL (真实 JEV API)"

    rows = []
    skill_correct = 0
    llm_correct = 0
    total = len(samples)
    latencies = []
    total_in = 0
    total_out = 0

    for s in samples:
        t0 = time.time()
        r = route(s["text"], api_key=api_key, use_mock=use_mock)
        dt = time.time() - t0
        latencies.append(dt)
        usage = r["usage"]
        total_in += usage.get("input_tokens", 0)
        total_out += usage.get("output_tokens", 0)

        pred_skill = r["final_skill"]
        pred_needs = r["needs_llm"]
        exp_skill = s["expected_skill"]
        exp_needs = s["expected_need_llm"]

        skill_correct += (pred_skill == exp_skill)
        llm_correct += (pred_needs == exp_needs)

        rows.append({
            "id": s["id"],
            "text": s["text"],
            "exp_skill": exp_skill,
            "pred_skill": pred_skill,
            "conf": round(r["skill_confidence"], 3),
            "fallback": r["fallback"],
            "exp_llm": exp_needs,
            "pred_llm": pred_needs,
            "llm_score": round(r["need_llm_score"], 3),
            "latency_ms": round(dt * 1000, 1),
        })

    skill_acc = skill_correct / total if total else 0
    llm_acc = llm_correct / total if total else 0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0

    report = []
    report.append("# JEV 路由验证报告\n")
    report.append(f"- 模式：{mode}")
    report.append(f"- 样本数：{total}")
    report.append(f"- 类别准确率：{skill_correct}/{total} = {skill_acc:.1%}")
    report.append(f"- need_llm 准确率：{llm_correct}/{total} = {llm_acc:.1%}")
    report.append(f"- 平均延迟：{avg_lat * 1000:.1f} ms")
    report.append(f"- 累计 token：in={total_in}, out={total_out}")
    report.append("")
    report.append("## 逐条结果\n")
    report.append("| # | 输入(截断) | 预期类别 | 预测类别 | 置信度 | 兜底 | 预期LLM | 预测LLM | LLM分 | 延迟ms |")
    report.append("|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        txt = row["text"][:22] + ("…" if len(row["text"]) > 22 else "")
        report.append(
            f"| {row['id']} | {txt} | {row['exp_skill']} | {row['pred_skill']} | "
            f"{row['conf']} | {row['fallback']} | {row['exp_llm']} | {row['pred_llm']} | "
            f"{row['llm_score']} | {row['latency_ms']} |"
        )
    report.append("")
    report.append("## 说明\n")
    report.append("- 本报告由 `run_eval.py` 自动生成。")
    if use_mock:
        report.append(
            "- **当前为 MOCK 模式**：类别与 need_llm 判断来自本地关键词启发式占位，仅用于跑通评估流程，**不代表 JEV 真实准确率**。要得到真实数字，设置 `TYPESAFE_API_KEY` 并将 `JEV_MOCK` 设为 false 后重跑。"
        )
    else:
        report.append("- 当前为真实 JEV API 模式，数字反映 JEV 在此样本上的真实表现。")
    report.append(f"- 样本说明：{meta}")

    out_path = os.path.join(HERE, "evals", "route_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"[{mode}]")
    print(f"类别准确率: {skill_acc:.1%}   need_llm准确率: {llm_acc:.1%}   平均延迟: {avg_lat * 1000:.1f}ms")
    print(f"报告已写入: {out_path}")


if __name__ == "__main__":
    main()
