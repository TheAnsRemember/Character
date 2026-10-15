# Character 桌面按钮安装包（给 AI Agent 看的自描述清单）

> 这是一个**自描述**的安装包：任何能运行命令的 AI Agent（WorkBuddy、ChatGPT、Claude Code、Cursor 等）
> 只要读到这个文件夹，就知道该怎么帮用户在**桌面**上装出一个叫 **Character** 的按钮。

---

## 这个包是干嘛的

Character 是一个本地写作 + AI 分类/总结的小工具，本体是一个网页（`http://localhost:8787/app`），
由 `web/server.py` 在用户自己电脑上起一个本地服务来提供。

本包的目标：**在用户的桌面上生成一个名为「Character」的按钮**，让用户以后双击就能用，
不用自己敲命令。

- **macOS**：生成一个 `Character.app`（双击即启动本地服务并打开浏览器）。
- **Windows**：在桌面生成一个 `Character.lnk` 快捷方式（同样会自动起服务、开浏览器）。

按钮的图标统一用本包的 **`icon.png`**（阴阳鱼 logo，就是 Character 的品牌图标）。

点击按钮后的行为：
1. 检查本机 `8787` 端口是否已经起来了（服务已在跑就跳过）。
2. 没跑就启动 `web/server.py`（本地写作服务）。
3. 等服务就绪后，自动打开默认浏览器访问 `http://localhost:8787/app`。

---

## AI Agent 该怎么做（执行步骤）

1. **找到 Character 项目根目录**：也就是包含 `web/server.py` 的那个文件夹。
   - 用户通常是把 GitHub 下载的 `Character/` 解压到了某处（桌面、下载、文档等）。
   - 如果找不到，直接问用户："Character 文件夹放在哪里了？" 不要瞎猜路径。
2. **运行安装器**（在本包的 `desktop-button/` 目录下执行，把项目根目录作为参数传进去）：
   - macOS / Linux：`python3 setup.py <Character项目根目录>`
   - Windows：`python setup.py <Character项目根目录>`
   - 不传参数也行，安装器会自己猜几个常见位置（桌面、下载、当前目录的上级）。
3. 安装器会自动在**桌面**生成 Character 按钮，并在终端打印结果。
4. **告诉用户**：桌面上已经多了一个 Character 图标，以后双击它就能打开 Character 网页使用。

---

## 前置条件（先确认，不满足就提示用户）

- 用户电脑已安装 **Python 3**：
  - macOS 自带 `python3`，一般无需额外装。
  - Windows 需要自己去装（https://www.python.org ），安装时勾选「Add Python to PATH」。
- Character 项目文件夹里确实有 `web/server.py`（这是本地服务入口，缺了就跑不起来）。

---

## 包内文件说明

| 文件 | 作用 |
|------|------|
| `AGENT.md` | 就是本文件，给 AI Agent 看的自描述说明 |
| `icon.png` | 阴阳鱼 logo，按钮图标来源（1024×1024） |
| `setup.py` | 跨平台安装器（纯 Python 标准库，零依赖），Mac 建 .app、Windows 建 .lnk |
| `build-windows.ps1` | Windows 专用：由 `setup.py` 调用，负责建桌面快捷方式和启动器 |

---

## 注意事项

- 不要把 `web/local_config.json`（里面是你的 AI 模型密钥）提交到任何公开仓库。
- 安装器只会在**用户自己的桌面**和 **Character 项目目录**里写文件，不会动系统目录。
- 如果用户想重装 / 换位置，直接再跑一次 `setup.py <新项目路径>` 即可，会覆盖旧按钮。
