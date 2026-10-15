# Character

> **人和 LLM 之间的缓冲房间。**
> 你在这里写下自己的想法，先不急着交给 AI。AI 处理完之后，你随时可以回来，看看自己当时到底是怎么想的、走的是哪条思路——说不定能找到被 AI 的才华掩盖掉的另外一条好通路。

<p align="center"><i>Local-first · 零第三方依赖 · 纯本地 · 完全开源</i></p>

---

## 它到底是什么

Character 是一个**完全跑在你自己电脑上的本地写作 + AI 分类/总结小工具**——不是聊天框，是让你**先把想法写下来**，而不是直接丢给 AI。

- 你在下面那片"无限空间"里，尽情 type 出只属于你的想法。**所有数据完全本地化**，不上传任何服务器。
- 点「总结」，它把文字先交给 **JEV** 判断这是什么内容（TODO LIST？项目想法？工作内容？），**同时 JEV 再判断需不需要 LLM 出手**。
  - 需要 → 交给 LLM 整理；不需要 → 直接把 md 复制给 Agent 去处理。
- 每一次你都能回到 Character，看上次交给 Agent **之前**自己的原始思想是什么。

### 5 种字体
**隶书 / 行书 / 楷书 / 草书**，外加一种英文手写体（Dancing Script，切换英文界面时自动启用，好玩但我不记得全名了 😄）。

### 左侧：当前任务 & 空间
左边是当前任务和空间，**放入空间就会存起来**。

### 通用设置（General）
- **权限**：调整 Character 是否调用 AI 来处理这条笔记。
- **语言**：中 / 英双语切换。
- **外观**：Light / Dark / System（夜间模式）。

### 设置 → 模型（Models）
填入 **JEV 模型的 API key** 和 **LLM 模型的 API key**，Character 就有了它的完全满血功能。（放心，它完全是 localhost 的，不经过你的数据。）

---

<p align="center"><i>整个代码层只有 1.1mb，完全本地，大家可以放心使用。</i></p>

---

## 技术文档

本地写作 + AI 分类 / 总结。前端纯静态，后端仅用 Python 标准库（零第三方依赖）。

## 它能达到什么效果

- **随手书写**：网页里直接写，支持书法字体渲染——**隶书 / 行书 / 楷书 / 草书** 四种手选，另有 **Dancing Script** 英文手写体（切英文界面时自动启用），共 5 种。
- **自动分类**：接入 JEV 模型后识别为「灵感 / 随笔 / 待办 / 已有项目 / 生活闲谈 / 其它」；**灵感类原样保留、不重写**。
- **AI 总结**：接入 GLM（智谱）等 OpenAI 兼容大模型后对非灵感类生成摘要；**没连大模型时退化为原文复制**，面板会明确标注。
- **一键存档**：内容（含分类、摘要）写成 Markdown 存到 `outputs/`。
- **桌面按钮**：双击桌面 Character（Mac 为 `Character.app`，Windows 为快捷方式）即用——自动启动本地服务并打开浏览器，阴阳鱼图标。Mac 装好后可走 `http://character.test/app` 这种本地域名。

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
# 或（Mac 装过桌面按钮后）打开 http://character.test/app
```

## 桌面按钮

双击桌面 Character 即可使用，不用敲命令。两种装法任选其一：

- **拖进 AI Agent（推荐，Mac / Windows 通用）**：把 `desktop-button/` 文件夹交给一个**能在你电脑上执行命令**的 AI Agent（WorkBuddy、Claude Code、Cursor 等都可以，纯网页聊天版做不到），说「帮我装 Character 桌面按钮」。Agent 会读 `desktop-button/AGENT.md`，自动在你桌面生成带阴阳鱼图标的按钮。
  - **Mac 用户**安装时若愿意输一次开机密码，按钮会打开体面的 `http://character.test/app`（本地域名，无需看 `localhost` 和数字端口）；否则自动退回 `http://localhost:8787/app`。
- **命令行（仅 Mac）**：`bash scripts/build-macos-app.sh`

## 目录结构

- `web/` —— 前端界面（`app.html / app.js / app.css`）、本地服务（`server.py`，端口 8787）、书法字体
- `router/` —— 后端管线：分类 / 总结 / 抽取 / 写 MD
- `desktop-button/` —— 跨平台桌面按钮安装包（含给 AI Agent 看的 `AGENT.md`）
- `scripts/` —— 开发者用的 Mac 桌面端重建脚本
- `outputs/` —— 本地存档（不进版本库）
- `web/local_config.json` —— 本机密钥配置（不进版本库，用 `local_config.example.json` 当模板）

---

## 作者的话 · About Character

> 这就是 Character 了。在这里呢！大家就可以把自己想要和 Agent 聊的内容先写下来，而不是直接与 AI 产生思想碰撞。
>
> 同时，当你把在 Character 聊的内容 push 到你的 Claude、GPT、WorkBuddy 之后，可以在任意时刻都能回来看看你当时到底咋想的，是怎样的思路。说不定能找到被 AI 的才华掩盖掉的另外一条好的通路。
>
> 接下来我们可以详细带大家看看 Character 的细节。映入眼帘的这块区域呢，就是你的"无限空间"，在这里可以疯狂地 type 出只属于你的想法，所有数据呢，完全本地化。
>
> 点击总结，它就能够将你输入的这么些文字先经过 JEV 判断这些文字是什么内容——是 TODO LIST？还是项目想法？抑或是工作内容？同时 JEV 也要去判断需不需要 LLM 去做处理，如果需要则交由 LLM 处理，不需要就可以直接复制 md 文件到 Agent 去给 Agent 去处理。
>
> 同时就像我说的，你每一次都能够回到 Character 看上次你没给 Agent 文件前你的思想是怎样的。
>
> Character 有 5 种字体，隶行楷草以及一种 pretty mice 的 English characters types which i do not know, 但是也是蛮好玩的字体。
>
> 而左边呢，则是当前任务以及空间，放入空间则会存储起来。
>
> 在通用设置中呢，则有权限用来调整 Character 使用模型（其实它是完全 localhost 的，没必要担心），语言可切换中英双语，外观则能切换夜间模式，可以说应有尽有。
>
> 在设置——模型中，有我们需要写入的 JEV 模型的 api key、LLM 模型的 api key，填入后 Character 就有了它的完全满血功能。
>
> 以上就是 Character 的全部功能啦！整个代码层只有 1.1mb，同时完全本地大家可以放心使用！
>
> C character 将秉持完全开源，可以供大家尽情使用。如果在哪里需要改动，也可以将 Character 扔进 Agent 再去进行个性化修改。如果你有好的改动想法也一定要告诉我！
>
> 我们一起来共创 Character，让它真正成为人和 LLM 之间的那个属于人类个人思想的缓冲房间——不，缓冲 **pent house**。
>
> *that's all, thanks for your attention!*
>
> **By An · The Ans Remember**
