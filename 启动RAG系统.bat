@echo off
chcp 65001 >nul
title RAG 系统启动器

echo ========================================
echo   RAG 智能知识问答系统
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 启动后端...
start "RAG-Backend" cmd /k "cd /d "%~dp0backend" && .\venv\Scripts\python.exe -m app.main"

echo [2/2] 启动前端...
start "RAG-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo   启动完成！
echo ========================================
echo   后端: http://localhost:8000
echo   前端: http://localhost:3000
echo   API文档: http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键打开浏览器访问...
pause >nul

start http://localhost:3000
