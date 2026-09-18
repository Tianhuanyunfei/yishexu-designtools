@echo off
cd /d "%~dp0"
echo 正在安装依赖包...
.venv\Scripts\pip.exe install flask-jwt-extended flask-sqlalchemy
echo.
echo 正在启动后端服务器...
.venv\Scripts\python.exe app.py
pause
