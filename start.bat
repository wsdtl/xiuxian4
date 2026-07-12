@echo off
setlocal
chcp 65001 >nul

rem 始终从脚本所在的项目根目录启动，避免相对路径配置失效。
cd /d "%~dp0"
set "PYTHON_BIN=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_BIN%" (
    echo [错误] 项目虚拟环境不存在。
    echo 请先运行: python -m venv .venv
    exit /b 1
)

"%PYTHON_BIN%" main.py
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
