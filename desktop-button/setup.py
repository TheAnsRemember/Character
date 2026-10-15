#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character 桌面按钮安装器（跨平台，纯标准库，零第三方依赖）。

由 AI Agent 在用户机器上运行，在桌面生成一个名为「Character」的启动按钮：
  - macOS  : ~/Desktop/Character.app  （双击启动本地服务并打开浏览器）
  - Windows: 桌面 Character.lnk 快捷方式（同样自动起服务、开浏览器）

按钮图标用同目录的 icon.png（阴阳鱼 logo）。

用法：
    python3 setup.py [CHARACTER项目根目录]
不传参数时，会自动猜测几个常见位置（桌面 / 下载 / 当前目录的上级）。
"""
import os
import sys
import struct
import zlib
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PNG = os.path.join(HERE, "icon.png")
PORT = 8787
URL = "http://localhost:%d/app" % PORT


# --------------------------------------------------------------------------
# 图标：把 PNG 打包成 macOS .icns / Windows .ico（纯标准库）
# --------------------------------------------------------------------------
def make_icns(png_path, icns_path):
    with open(png_path, "rb") as f:
        png = f.read()
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "icon.png 不是合法的 PNG"
    # 现代 macOS 接受直接内嵌 PNG 的条目类型
    TYPES = [b"ic08", b"ic09", b"ic10", b"ic14"]
    entries = b""
    for t in TYPES:
        entries += t + struct.pack(">I", len(png) + 8) + png
    icns = b"icns" + struct.pack(">I", len(entries) + 8) + entries
    with open(icns_path, "wb") as f:
        f.write(icns)
    print("ICNS ->", icns_path)


def make_ico(png_path, ico_path):
    with open(png_path, "rb") as f:
        png = f.read()
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "icon.png 不是合法的 PNG"
    # ICO：单图，PNG 格式（Windows Vista+ 支持 PNG-in-ICO，会自动缩放）
    header = struct.pack("<HHH", 0, 1, 1)
    # 宽/高字节最大 255，0 表示 256
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    with open(ico_path, "wb") as f:
        f.write(header + entry + png)
    print("ICO  ->", ico_path)


# --------------------------------------------------------------------------
# 定位 Character 项目根目录（需含 web/server.py）
# --------------------------------------------------------------------------
def _has_server(candidate):
    return os.path.isfile(os.path.join(candidate, "web", "server.py"))


def find_project(arg):
    if arg:
        p = os.path.abspath(arg)
        if _has_server(p):
            return p
        # 也许传进来的是 web 目录本身
        if os.path.basename(p) == "web" and os.path.isfile(os.path.join(p, "server.py")):
            return os.path.dirname(p)
        # 也许是 server.py 文件
        if os.path.basename(p) == "server.py" and os.path.isfile(p):
            return os.path.dirname(os.path.dirname(p))
    home = os.path.expanduser("~")
    candidates = [
        os.getcwd(),
        os.path.join(home, "Desktop", "Character"),
        os.path.join(home, "Downloads", "Character"),
        os.path.join(home, "Documents", "Character"),
        os.path.dirname(os.path.dirname(HERE)),   # 若本包在 Character/desktop-button
    ]
    for c in candidates:
        c = os.path.abspath(c)
        if _has_server(c):
            return c
        # 再往上级找一层
        up = os.path.abspath(os.path.join(c, ".."))
        if _has_server(up):
            return up
    return None


# --------------------------------------------------------------------------
# macOS：构建 ~/Desktop/Character.app
# --------------------------------------------------------------------------
def build_mac(project, icon_in_project):
    app = os.path.join(os.path.expanduser("~"), "Desktop", "Character.app")
    macos = os.path.join(app, "Contents", "MacOS")
    res = os.path.join(app, "Contents", "Resources")
    os.makedirs(macos, exist_ok=True)
    os.makedirs(res, exist_ok=True)

    make_icns(ICON_PNG, os.path.join(res, "appicon.icns"))

    plist = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Character</string>
  <key>CFBundleDisplayName</key><string>Character</string>
  <key>CFBundleIdentifier</key><string>com.character.app</string>
  <key>CFBundleExecutable</key><string>character</string>
  <key>CFBundleIconFile</key><string>appicon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>10.12</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
'''
    with open(os.path.join(app, "Contents", "Info.plist"), "w") as f:
        f.write(plist)

    # 启动壳：烘焙 PROJ_DIR（绝对路径），并保留兜底探测
    launcher = '''#!/usr/bin/env bash
# Character 桌面壳：双击启动本地服务并自动打开浏览器
set -u
PROJ_DIR="__PROJ_DIR__"
if [ ! -f "$PROJ_DIR/web/server.py" ]; then
  SELF_DIR="$(cd "$(dirname "$0")/.." && pwd)"
  if [ -f "$SELF_DIR/../web/server.py" ]; then
    PROJ_DIR="$(cd "$SELF_DIR/.." && pwd)"
  elif [ -f "$SELF_DIR/../Character/web/server.py" ]; then
    PROJ_DIR="$(cd "$SELF_DIR/../Character" && pwd)"
  else
    PROJ_DIR="$HOME/Desktop/Character"
  fi
fi
WEB_DIR="$PROJ_DIR/web"
PORT=__PORT__
URL="http://localhost:$PORT/app"
LOG="$PROJ_DIR/character-server.log"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif [ -x /usr/bin/python3 ]; then
  PY=/usr/bin/python3
else
  osascript -e 'display dialog "找不到 python3，无法启动 Character。请先安装 Python 3 后再试。" buttons {"好"} default button 1' >/dev/null 2>&1
  exit 1
fi
if lsof -ti :$PORT >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi
cd "$WEB_DIR" || exit 1
nohup "$PY" server.py >"$LOG" 2>&1 &
for i in $(seq 1 20); do
  if lsof -ti :$PORT >/dev/null 2>&1; then break; fi
  sleep 0.5
done
sleep 0.5
open "$URL"
exit 0
'''
    launcher = launcher.replace("__PROJ_DIR__", project).replace("__PORT__", str(PORT))
    launcher_path = os.path.join(macos, "character")
    with open(launcher_path, "w") as f:
        f.write(launcher)
    os.chmod(launcher_path, 0o755)
    print("已生成桌面应用：", app)
    print("双击即可启动（首次若被拦截，右键 -> 打开）。")


# --------------------------------------------------------------------------
# Windows：调用 build-windows.ps1 建桌面快捷方式
# --------------------------------------------------------------------------
def build_windows(project, icon_in_project):
    ico = os.path.join(project, "character-icon.ico")
    make_ico(ICON_PNG, ico)
    ps1 = os.path.join(HERE, "build-windows.ps1")
    if not os.path.isfile(ps1):
        print("缺少 build-windows.ps1，无法在 Windows 上创建快捷方式。")
        sys.exit(3)
    try:
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps1,
             "-ProjectDir", project, "-IconPath", ico],
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("调用 PowerShell 失败：", e)
        sys.exit(3)


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def main():
    if not os.path.isfile(ICON_PNG):
        print("缺少 icon.png，无法继续。")
        sys.exit(2)

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    project = find_project(arg)
    if not project:
        print("错误：找不到 Character 项目（需要包含 web/server.py 的文件夹）。")
        print("请把 Character 文件夹路径传给安装器，例如：")
        print("  python3 setup.py C:\\Users\\你\\Downloads\\Character")
        print("或者先把 Character 文件夹放到桌面 / 下载，再重跑本脚本。")
        sys.exit(2)

    print("Character 项目根目录：", project)

    # 把图标稳定地放到项目目录里，按钮引用它更不容易丢
    icon_in_project = os.path.join(project, "character-icon.png")
    shutil.copyfile(ICON_PNG, icon_in_project)

    plat = sys.platform
    if plat == "darwin":
        build_mac(project, icon_in_project)
    elif plat.startswith("win"):
        build_windows(project, icon_in_project)
    else:
        print("暂不支持的操作系统：", plat, "（目前只支持 macOS 和 Windows）")
        sys.exit(3)

    print("完成 ✓ 桌面上已出现 Character 按钮，双击即可打开网页使用。")


if __name__ == "__main__":
    main()
