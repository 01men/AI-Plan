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
python -c "import fastapi,uvicorn,cryptography,qrcode,multipart,openpyxl,xlrd" >nul 2>&1
if errorlevel 1 (
  echo  首次运行正在安装依赖，请保持网络畅通...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo  依赖安装失败，请执行：python -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)
where pdftotext >nul 2>&1
if errorlevel 1 (
  echo  [提示] 未检测到 pdftotext（poppler），PDF 知识文档解析将不可用；
  echo         请安装 poppler 并将 bin 目录加入 PATH 后重启本脚本。其他功能不受影响。
  echo.
)
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo  [错误] 8000 端口已被占用，请先关闭占用进程或已运行的平台实例。
  pause
  exit /b 1
)
rem 启动前检查模型 Key（库不存在则跳过）：未配置仅提示，不阻断启动
if exist data\platform.db (
  python -c "import sqlite3,sys;c=sqlite3.connect('data/platform.db');sys.exit(0 if c.execute('SELECT COUNT(*) FROM model_providers WHERE length(api_key)>0 AND enabled=1').fetchone()[0] else 1)" >nul 2>&1
  if errorlevel 1 (
    echo  [提示] 未配置模型 Key：数字员工对话将为演示回复，请在 数字员工→模型 中配置
    echo.
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
