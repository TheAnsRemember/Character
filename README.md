# Character

本地写作 + AI 分类 / 总结的桌面小工具。前端纯静态，后端仅用 Python 标准库（零第三方依赖）。

## 它能达到什么效果

- **随手书写**：网页里直接写，支持书法字体（隶书 / 行书 / 楷书 / 草书）渲染。
- **自动分类**：接入 JEV 模型后识别为「灵感 / 随笔 / 待办 / 已有项目 / 生活闲谈 / 其它」；**灵感类原样保留、不重写**。
- **AI 总结**：接入 GLM（智谱）等 OpenAI 兼容大模型后对非灵感类生成摘要；**没连大模型时退化为原文复制**，面板会明确标注。
- **一键存档**：内容（含分类、摘要）写成 Markdown 存到 `outputs/`。
- **桌面按钮**：双击桌面 Character（Mac 为 `Character.app`，Windows 为快捷方式）即用——自动启动本地服务并打开浏览器，阴阳鱼图标。

## 快速开始

需要 Python 3（macOS 自带；Windows 需安装并勾选加入 PATH）。

```bash
# 1. 配置密钥（也可以不填，直接在网页「设置 → 模型」里填）
cp web/local_config.example.json web/local_config.json
#    编辑 web/local_config.json：
#    jev_key —— 分类模型的 key
#    openai_key —— API 密钥（GLM 等 OpenAI 兼容服务）

# 2. 启动
cd web && python3 server.py
# 浏览器打开 http://localhost:8787/app
```

## 桌面按钮

双击桌面 Character 即可使用，不用敲命令。两种装法任选其一：

- **拖进 AI Agent（推荐，Mac / Windows 通用）**：把 `desktop-button/` 文件夹交给 AI Agent（WorkBuddy、ChatGPT、Claude Code、Cursor 等都可以），说「帮我装 Character 桌面按钮」。Agent 会读 `desktop-button/AGENT.md`，自动在你桌面生成带阴阳鱼图标的按钮。
- **命令行（仅 Mac）**：`bash scripts/build-macos-app.sh`

## 目录结构

- `web/` —— 前端界面（`app.html / app.js / app.css`）、本地服务（`server.py`，端口 8787）、书法字体
- `router/` —— 后端管线：分类 / 总结 / 抽取 / 写 MD
- `desktop-button/` —— 跨平台桌面按钮安装包（含给 AI Agent 看的 `AGENT.md`）
- `scripts/` —— 开发者用的 Mac 桌面端重建脚本
- `outputs/` —— 本地存档（不进版本库）
- `web/local_config.json` —— 本机密钥配置（不进版本库，用 `local_config.example.json` 当模板）
