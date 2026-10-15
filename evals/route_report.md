# JEV 路由验证报告

- 模式：REAL (真实 JEV API)
- 样本数：16
- 类别准确率：15/16 = 93.8%
- need_llm 准确率：15/16 = 93.8%
- 平均延迟：1069.7 ms
- 累计 token：in=10340, out=1374

## 逐条结果

| # | 输入(截断) | 预期类别 | 预测类别 | 置信度 | 兜底 | 预期LLM | 预测LLM | LLM分 | 延迟ms |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 明天要记得给张总发项目报价单，还有把周报填了… | todo | todo | 1.0 | False | True | True | 0.89 | 1078.1 |
| 2 | 这周要做的事：约供应商看样品、把 Kimmy… | todo | todo | 1.0 | False | True | True | 0.83 | 1142.5 |
| 3 | 把昨天会议录音转成文字，然后整理成待办清单发… | todo | todo | 1.0 | False | True | True | 0.91 | 946.1 |
| 4 | 店感 MVP 这周上线了 K11 试点，但扫… | existing_project | existing_project | 0.97 | False | True | True | 0.82 | 1317.3 |
| 5 | 小满 RAG 集成到一半，KnowYours… | existing_project | existing_project | 0.99 | False | True | True | 0.72 | 920.3 |
| 6 | 下周要交付店感试点报告，已经写完初稿，今晚再… | existing_project | existing_project | 0.42 | False | True | False | 0.61 | 1167.6 |
| 7 | 我有个蓝图：做一个面向出海小团队的 AI 周… | blueprint | blueprint | 1.0 | False | False | False | 0.69 | 846.5 |
| 8 | 设想一个硬件订阅服务：用户月付租毛绒玩具，坏… | blueprint | blueprint | 0.95 | False | False | False | 0.44 | 853.1 |
| 9 | 想做一个记录灵感的小工具，但又不希望 AI … | blueprint | blueprint | 0.98 | False | False | False | 0.27 | 871.5 |
| 10 | 今天深圳下雨，坐在咖啡店看窗外人来人往，突然… | essay | essay | 0.51 | False | False | False | 0.29 | 1104.0 |
| 11 | 随笔：凌晨三点睡不着，想到我妈以前说的话，关… | essay | essay | 0.99 | False | False | False | 0.33 | 1211.5 |
| 12 | 随笔：今天又被投资人问商业化路径，其实我自己… | essay | essay | 0.98 | False | False | False | 0.4 | 923.2 |
| 13 | 最近一直在想，人活着到底图什么，钱赚到了然后… | life_talk | life_talk | 1.0 | False | False | False | 0.31 | 1245.8 |
| 14 | 我对成功的定义越来越模糊了，到底是社会定义的… | life_talk | life_talk | 1.0 | False | False | False | 0.33 | 1549.9 |
| 15 | 刚才那个 bug 又出现了 | other | existing_project | 0.41 | False | False | False | 0.5 | 991.7 |
| 16 | 不知道，累了 | other | other | 0.94 | False | False | False | 0.17 | 946.9 |

## 说明

- 本报告由 `run_eval.py` 自动生成。
- 当前为真实 JEV API 模式，数字反映 JEV 在此样本上的真实表现。
- 样本说明：示例验证样本集——模拟安泽彬真实思考片段的风格，用于跑通 JEV 路由评估流程。待替换为真实片段后再做真实验证。expected_skill / expected_need_llm 为人工标注的「应得结果」，用于算准确率。