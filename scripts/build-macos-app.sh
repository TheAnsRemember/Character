#!/usr/bin/env bash
# 在 macOS 上重建 Character.app（桌面启动壳）。从仓库根目录运行： bash scripts/build-macos-app.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Desktop/Character.app"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# 1) 图标（纯标准库生成 PNG + 打包 icns）
python3 "$ROOT/scripts/build-icon.py" --icns "$APP/Contents/Resources/appicon.icns"

# 2) Info.plist
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Character</string>
  <key>CFBundleDisplayName</key>
  <string>Character</string>
  <key>CFBundleIdentifier</key>
  <string>com.analways1.character</string>
  <key>CFBundleExecutable</key>
  <string>character</string>
  <key>CFBundleIconFile</key>
  <string>appicon</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.12</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>LSBackgroundOnly</key>
  <false/>
</dict>
</plist>
EOF

# 3) 启动壳：双击启动本地服务并打开浏览器（兼容两种摆放：.app 在桌面 / 在 Character 内）
cat > "$APP/Contents/MacOS/character" <<'SH'
#!/usr/bin/env bash
# Character 轻量桌面壳：双击启动本地服务并自动打开浏览器
set -u
SELF_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$SELF_DIR/../web/server.py" ]; then
  PROJ_DIR="$(cd "$SELF_DIR/.." && pwd)"
elif [ -f "$SELF_DIR/../Character/web/server.py" ]; then
  PROJ_DIR="$(cd "$SELF_DIR/../Character" && pwd)"
else
  PROJ_DIR="$HOME/Desktop/Character"
fi
WEB_DIR="$PROJ_DIR/web"
PORT=8787
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
SH

chmod +x "$APP/Contents/MacOS/character"
echo "已生成桌面应用：$APP"
echo "双击即可启动（首次若被拦截，右键 -> 打开）。"
