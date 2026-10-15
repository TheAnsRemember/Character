# Character 桌面快捷方式生成器（Windows）
# 由 setup.py 调用：powershell -ExecutionPolicy Bypass -File build-windows.ps1 -ProjectDir <项目根目录> -IconPath <ico路径>
# 作用：
#   1. 在项目目录生成 character-launch.bat（检测端口 -> 起 web/server.py -> 开浏览器）
#   2. 在用户桌面创建带阴阳鱼图标的 Character.lnk 快捷方式

param(
    [Parameter(Mandatory=$true)][string]$ProjectDir,
    [Parameter(Mandatory=$true)][string]$IconPath
)

$ErrorActionPreference = "Stop"

$web = Join-Path $ProjectDir "web"
$bat = Join-Path $ProjectDir "character-launch.bat"
$log = Join-Path $ProjectDir "character-server.log"
$port = 8787
$url  = "http://localhost:$port/app"

# ---- 1) 写启动器 bat（把路径烘焙进去）----
$batContent = @"
@echo off
set PORT=$port
set URL=$url
set PROJ="$web"
set LOG="$log"

REM 端口已占用（服务已在跑）就直接开网页
powershell -NoProfile -Command "(Test-NetConnection -ComputerName localhost -Port %PORT%).TcpTestSucceeded" | findstr /i "True" >nul
if "%errorlevel%"=="0" goto OPEN

:START
cd /d "%PROJ%"
where python >nul 2>nul
if "%errorlevel%"=="0" (set PY=python) else (set PY=py)
start "" %PY% server.py >"%LOG%" 2>&1

:WAIT
timeout /t 1 >nul
powershell -NoProfile -Command "(Test-NetConnection -ComputerName localhost -Port %PORT%).TcpTestSucceeded" | findstr /i "True" >nul
if not "%errorlevel%"=="0" goto WAIT

:OPEN
start "" "%URL%"
exit /b
"@
Set-Content -Path $bat -Value $batContent -Encoding ASCII
Write-Host "启动器 -> $bat"

# ---- 2) 在桌面创建快捷方式 ----
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Character.lnk"

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = $bat
$sc.IconLocation = "$IconPath,0"
$sc.Description = "Character - 本地写作 + AI 整理"
$sc.WorkingDirectory = $web
$sc.Save()
Write-Host "桌面快捷方式 -> $lnk"
Write-Host "完成。双击桌面 Character 即可打开网页使用。"
