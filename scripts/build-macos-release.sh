#!/usr/bin/env bash
# 把 Character 打成「解压即用」的 macOS 分发包（纯标准库/纯 shell，零依赖）。
#
# 产物：dist/Character-mac-<日期>.zip
#   解压后目录里直接含 Character.app —— 双击即开服务，不用再拖给任何 Agent。
#
# 关键点：.app 启动壳用「相对定位优先」，不依赖任何绝对路径，
#        因此解压到任何位置、任何用户名下都能自己找到旁边的 web/ 代码。
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIST="$ROOT/dist"
STAGE="$ROOT/.pkgbuild-tmp"
DATE="$(date +%Y%m%d)"
ZIP="$DIST/Character-mac-$DATE.zip"

command -v python3 >/dev/null 2>&1 || { echo "需要 python3"; exit 1; }

echo "==> 清理旧产物"
rm -rf "$STAGE" "$ZIP"

echo "==> 准备暂存目录（只带运行必需的文件，不带 git/测试数据）"
mkdir -p "$STAGE/Character"
# 拷贝运行必需目录
for d in web router; do
  cp -R "$ROOT/$d" "$STAGE/Character/"
done
# 拷文档
cp "$ROOT/README.md" "$STAGE/Character/" 2>/dev/null || true
[ -f "$ROOT/安装说明.md" ] && cp "$ROOT/安装说明.md" "$STAGE/Character/"
# 排除不该分发的本机文件
find "$STAGE/Character" -name '.DS_Store' -delete 2>/dev/null || true
find "$STAGE/Character/web" -name 'local_config.json' -delete 2>/dev/null || true
find "$STAGE/Character/web" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "==> 生成 Character.app（相对定位启动壳）"
APP="$STAGE/Character/Character.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$ROOT/web/app-icon.png" "$APP/Contents/Resources/appicon.png" 2>/dev/null || true

# 启动壳：先用「记录的项目位置」，再相对定位，最后扫常见位置。
# 这样装完桌面按钮后，即使 Character 文件夹被挪走/改名，按钮照样能用。
cat > "$APP/Contents/MacOS/character" <<'LAUNCHER'
#!/usr/bin/env bash
# Character 桌面壳：双击启动本地服务并自动打开浏览器（可自由分发版）
set -u
SELF_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$(cd "$SELF_DIR/.." && pwd)"       # .app 所在目录
MEM="$HOME/Library/Application Support/Character/project.txt"

PROJ_DIR=""
# 1) 上次安装时记录的位置（最可靠：用户可能把文件夹挪走了）
if [ -f "$MEM" ]; then
  CAND="$(cat "$MEM" 2>/dev/null)"
  [ -f "$CAND/web/server.py" ] && PROJ_DIR="$CAND"
fi
# 2) 跟着 .app 走（.app 同级，或同级 Character/）
if [ -z "$PROJ_DIR" ]; then
  for cand in "$APP_DIR" "$APP_DIR/../Character" "$APP_DIR/.." "$SELF_DIR"; do
    if [ -f "$cand/web/server.py" ]; then PROJ_DIR="$(cd "$cand" && pwd)"; break; fi
  done
fi
# 3) 常见位置兜底（桌面/下载/文档）
if [ -z "$PROJ_DIR" ]; then
  for cand in "$HOME/Desktop/Character" "$HOME/Downloads/Character" "$HOME/Documents/Character"; do
    if [ -f "$cand/web/server.py" ]; then PROJ_DIR="$(cd "$cand" && pwd)"; break; fi
  done
fi
if [ -z "$PROJ_DIR" ]; then
  osascript -e 'display dialog "找不到 Character 代码（web/server.py）。\n\n请把 Character 文件夹放回桌面或下载目录，或重新运行一次文件夹里的「安装到桌面.command」。" buttons {"好"} default button 1' >/dev/null 2>&1
  exit 1
fi
# 顺手把找到的位置记下来，下次直接用
mkdir -p "$(dirname "$MEM")" 2>/dev/null && printf '%s' "$PROJ_DIR" > "$MEM" 2>/dev/null

WEB_DIR="$PROJ_DIR/web"
PORT=8787
URL="http://localhost:$PORT/app"
LOG="$PROJ_DIR/character-server.log"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif [ -x /usr/bin/python3 ]; then PY=/usr/bin/python3
else
  osascript -e 'display dialog "找不到 python3，无法启动。请先安装 Python 3。" buttons {"好"} default button 1' >/dev/null 2>&1
  exit 1
fi
if lsof -ti :$PORT >/dev/null 2>&1; then open "$URL"; exit 0; fi
cd "$WEB_DIR" || exit 1
nohup "$PY" server.py >"$LOG" 2>&1 &
for i in $(seq 1 20); do lsof -ti :$PORT >/dev/null 2>&1 && break; sleep 0.5; done
sleep 0.5
open "$URL"
exit 0
LAUNCHER
chmod +x "$APP/Contents/MacOS/character"

# 「安装到桌面.command」：用户双击它 → 桌面出现 Character 按钮（.command 双击即可运行）
echo "==> 生成「安装到桌面.command」"
INSTALL_CMD="$STAGE/Character/安装到桌面.command"
cat > "$INSTALL_CMD" <<'INSTALL'
#!/usr/bin/env bash
# 双击本文件即可把 Character 按钮装到桌面，并记录项目位置。
set -u
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DESK="$HOME/Desktop/Character.app"

if [ ! -f "$SRC_DIR/web/server.py" ]; then
  osascript -e 'display dialog "请在解压出来的 Character 文件夹里运行本文件。" buttons {"好"} default button 1' >/dev/null 2>&1
  exit 1
fi

# 复制 .app 到桌面（连同图标与启动壳）
rm -rf "$DESK"
cp -R "$SRC_DIR/Character.app" "$DESK"

# 记录项目位置，让桌面按钮即使在别处也能找到代码
MEM="$HOME/Library/Application Support/Character/project.txt"
mkdir -p "$(dirname "$MEM")"
printf '%s' "$SRC_DIR" > "$MEM"

osascript <<'EOS'
display dialog "✅ 装好了！\n\n桌面上已出现 Character 图标，以后双击它就能打开 Character。\n\n（首次若被 macOS 拦，右键 → 打开 确认一次即可）" buttons {"好"} default button 1 with title "Character 安装完成"
EOS
exit 0
INSTALL
chmod +x "$INSTALL_CMD"

# Info.plist（用 png ico，macOS 会自动缩放；更稳妥的做法是 icns，但 png 也能显示）
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Character</string>
  <key>CFBundleDisplayName</key><string>Character</string>
  <key>CFBundleIdentifier</key><string>local.character.app</string>
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
PLIST

echo "==> 打包成 zip"
mkdir -p "$DIST"
cd "$STAGE"
zip -qr "$ZIP" "Character"
cd "$ROOT"
rm -rf "$STAGE"

SIZE="$(du -h "$ZIP" | cut -f1)"
echo ""
echo "✅ 打包完成：$ZIP  ($SIZE)"
echo ""
echo "用户使用：下载 → 解压 → 双击文件夹里的「安装到桌面.command」"
echo "        → 桌面出现 Character 按钮 → 以后双击按钮即用。"
echo "（首次若被 macOS 拦，右键 → 打开 确认一次即可）"
