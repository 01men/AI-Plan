@echo off
chcp 65001 >nul
title 榕器 · Agent 人机协作平台
cd /d "%~dp0"
echo ============================================
echo   榕器 · Agent 人机协作平台
echo   金华聚杰电器 AI 数智化行动方案支撑底座
echo ============================================
echo.
echo  正在检查运行依赖...
python -c "import fastapi,uvicorn,cryptography,qrcode,multipart" >nul 2>&1
if errorlevel 1 (
  echo  首次运行正在安装依赖，请保持网络畅通...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo  依赖安装失败，请执行：python -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)
echo  正在启动服务，请稍候...
echo  浏览器将自动打开 http://localhost:8000
echo  关闭本窗口即停止平台服务。
echo.
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:8000"
python -m uvicorn app.main:app --port 8000
echo.
echo 服务已停止。如启动失败，请确认已安装 Python 并执行过：pip install -r requirements.txt
pause
