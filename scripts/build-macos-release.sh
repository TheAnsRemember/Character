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

# 启动壳：优先相对定位（.app 同级就是 web/），绝对路径只作最后兜底。
cat > "$APP/Contents/MacOS/character" <<'LAUNCHER'
#!/usr/bin/env bash
# Character 桌面壳：双击启动本地服务并自动打开浏览器（相对定位版，可自由分发）
set -u
SELF_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$(cd "$SELF_DIR/.." && pwd)"      # .app 所在目录
PROJ_DIR=""
for cand in "$APP_DIR" "$APP_DIR/../Character" "$HOME/Desktop/Character"; do
  if [ -f "$cand/web/server.py" ]; then PROJ_DIR="$(cd "$cand" && pwd)"; break; fi
done
if [ -z "$PROJ_DIR" ]; then
  osascript -e 'display dialog "找不到 Character 代码（web/server.py）。请确认 Character.app 和 Character 文件夹在一起。" buttons {"好"} default button 1' >/dev/null 2>&1
  exit 1
fi
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
echo "用户使用：下载 → 解压 → 双击 Character 文件夹里的 Character.app 即可打开服务。"
echo "（首次若被 macOS 拦，右键 → 打开 确认一次即可）"
