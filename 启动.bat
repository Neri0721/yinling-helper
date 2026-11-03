@echo off
chcp 65001 >nul
title 银龄核查助手
setlocal

rem ===== 以本文件所在目录为准，换电脑也能用 =====
set "APP=%~dp0"
if "%APP:~-1%"=="\" set "APP=%APP:~0,-1%"

echo ==========================================
echo    银龄核查助手 · 本地服务
echo ==========================================
echo.

rem ===== 1. 找一个可用的 Python =====
set "PY="
if exist "C:\Users\风又音理233\AI\venv\Scripts\python.exe" set "PY=C:\Users\风又音理233\AI\venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [错误] 没找到 Python。请先装 Python 3.9 以上。
  pause
  exit /b 1
)
echo [1/4] Python: %PY%

rem ===== 2. 启动 Ollama（没有它就降级为纯规则模式）=====
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
  echo [2/4] 启动 Ollama ...
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    timeout /t 6 /nobreak >nul
  ) else (
    echo       没装 Ollama，将使用纯规则模式（功能可用，口语理解稍弱）
  )
) else (
  echo [2/4] Ollama 已在运行
)

rem ===== 3. 启动核查服务 =====
echo [3/4] 检查 8765 端口 ...
powershell -NoProfile -Command "try{ Invoke-RestMethod 'http://127.0.0.1:8765/api/stats' -TimeoutSec 3 | Out-Null; exit 0 }catch{ exit 1 }"
if errorlevel 1 (
  echo       启动中 ...
  start "" /min %PY% "%APP%\server.py" 8765
  timeout /t 5 /nobreak >nul
) else (
  echo       服务已在运行
)

rem ===== 4. 打开浏览器 + 显示手机地址 =====
echo [4/4] 打开页面 ...
start "" "http://127.0.0.1:8765"

echo.
echo 电脑版: http://127.0.0.1:8765
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '26.*' } | ForEach-Object { Write-Host ('手机版: http://' + $_.IPAddress + ':8765/m') }"
echo.
echo 关掉这个窗口不影响服务；要停止服务请到任务管理器结束 python。
timeout /t 8 >nul
endlocal
