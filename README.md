# Character

本地写作 + AI 分类 / 总结的桌面小工具。前端纯静态、后端仅用 Python 标准库（零第三方依赖）。

## 它能达到什么效果

- **随手书写**：在网页里写任何内容，支持书法字体（隶书 / 行书 / 楷书 / 草书）渲染。
- **自动分类**：接入 JEV 模型后，把内容识别为「灵感 / 随笔 / 待办 / 已有项目 / 生活闲谈 / 其它」等类别；**灵感类原样保留、不重写**。
- **AI 总结 / 改写**：接入 GLM（智谱）等 OpenAI 兼容大模型后，对非灵感类内容生成摘要。
  - **没连大模型时，总结会退化为「原文复制」**，并在面板里明确告诉你是原文复制、不是 AI 总结。
- **一键存档**：把内容（含分类、摘要）写成 Markdown，存到 `outputs/`。
- **桌面端（macOS）**：双击 `Character.app` 即可用，自动在后台起本地服务并打开浏览器，图标为阴阳鱼 logo。

## 本地运行（不打包，最简单）

1. 需要 Python 3（macOS 自带即可，无需 pip 安装任何东西）。
2. 复制配置并填入你的 key：
   ```bash
   cp web/local_config.example.json web/local_config.json
   # 编辑 web/local_config.json，填入 jev_key 与 openai_key
   # 也可以不填，直接在网页「设置 → 模型」里填
   ```
3. 启动：
   ```bash
   cd web && python3 server.py
   ```
   浏览器打开 http://localhost:8787/app 即可。

## 桌面端（macOS）

仓库不含二进制 `.app`。克隆后运行下面脚本会在桌面重建 `Character.app`（含图标与启动壳）：

```bash
bash scripts/build-macos-app.sh
```

脚本会：生成阴阳鱼图标（纯标准库，无需联网）→ 写入 `Info.plist` 与启动壳 → 放到 `~/Desktop/Character.app`。双击即用。

## 目录结构

- `web/app.html` `web/app.js` `web/app.css` —— 前端界面
- `web/server.py` —— 本地调试 / 桌面端使用的 HTTP 服务（端口 8787）
- `web/router/` —— 后端管线：`route`(分类) / `summarizer`(总结) / `extractor`(抽取) / `md_writer`(写 MD)
- `outputs/` —— 本地存档目录（不进版本库）
- `scripts/` —— 开发者用的桌面端重建脚本
- `desktop-button/` —— **给别人装桌面按钮的自描述安装包**（见下一节）
- `web/local_config.json` —— 本机 key 配置（不进版本库，用 `local_config.example.json` 当模板）

## 给别人装桌面按钮（拖进 AI Agent）

如果你想把 Character 发给朋友 / 同事，让他们也能「双击桌面按钮就用」，不用教他们敲命令：

1. 把仓库里的 **`desktop-button/`** 这个文件夹交给对方的 AI Agent（WorkBuddy、Claude Code、Cursor 等都可以）。
   - 在 WorkBuddy 里直接把这个文件夹拖进对话、或说「帮我装 Character 桌面按钮」即可。
2. AI Agent 会读 `desktop-button/AGENT.md`，自动找到 Character 项目，然后在**对方桌面**生成：
   - **macOS**：`Character.app`（阴阳鱼图标，双击启动本地服务并开浏览器）
   - **Windows**：桌面 `Character.lnk` 快捷方式（同样自动起服务、开浏览器）
3. 对方以后双击桌面上的 Character 就能打开 `http://localhost:8787/app` 使用。

> 前提：对方电脑装了 Python 3（macOS 自带；Windows 需自行安装并勾选加入 PATH）。
> 按钮图标统一用 `desktop-button/icon.png`（阴阳鱼 logo）。安装器零第三方依赖，纯标准库。
