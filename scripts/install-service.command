#!/usr/bin/env bash
# Character · 注册为「开机自启 + 崩溃自动重启」的常驻服务（免密码、免 sudo）
# 通用版：不写死用户名，双击时自动定位工程目录并动态生成 plist。
set -u

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1) 找到 Character 工程目录（与桌面 .app 同样的逻辑）
PROJ_DIR=""
for cand in "$SELF_DIR/.." "$HOME/Desktop/Character" "$HOME/Downloads/Character" "$HOME/Documents/Character"; do
  if [ -f "$cand/web/server.py" ]; then PROJ_DIR="$(cd "$cand" && pwd)"; break; fi
done
if [ -z "$PROJ_DIR" ]; then
  echo "✗ 找不到 Character（web/server.py）。"
  echo "  请把本文件放在 Character 工程内的 scripts/ 目录，或放到桌面后重跑。"
  read -r -p "按回车退出…" _
  exit 1
fi

WEB="$PROJ_DIR/web"
PL="$HOME/Library/LaunchAgents/local.character.server.plist"
LOG="$PROJ_DIR/character-server.log"
mkdir -p "$(dirname "$PL")"

# 2) 动态生成 plist（不写死用户名路径）
cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.character.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$WEB/server.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$WEB</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$LOG</string>
</dict>
</plist>
PLIST

# 3) 注册为 LaunchAgent（用户级，免密码、免 sudo）
launchctl bootout "gui/$(id -u)/local.character.server" 2>/dev/null || true

echo "==========================================="
echo "  Character · 注册为常驻服务"
echo "==========================================="
echo ""

if launchctl bootstrap "gui/$(id -u)" "$PL" 2>&1; then
  sleep 3
  if launchctl list | grep -q local.character.server; then
    echo "✅ 注册成功！Character 现在会："
    echo "   · 开机自动启动"
    echo "   · 中途崩溃会自动重启"
    echo "   · 永远在 http://localhost:8787/app ，不再需要手动开启"
    echo ""
    if lsof -ti :8787 >/dev/null 2>&1; then
      echo "   ✓ 服务已运行 → http://localhost:8787/app"
    else
      echo "   ⚠️ 守护已装上，服务稍等几秒，或手动打开 http://localhost:8787/app"
    fi
  else
    echo "⚠️ 命令执行了，但列表里没找到守护进程，可稍后重跑本文件。"
  fi
else
  echo "❌ 注册失败。请在终端手动执行："
  echo "  launchctl bootstrap gui/\$(id -u) \"$PL\""
fi

echo ""
read -r -p "按回车关闭窗口…" _
