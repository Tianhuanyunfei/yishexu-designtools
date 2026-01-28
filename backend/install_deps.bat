@echo off
cd /d "%~dp0"
echo 正在安装依赖包...
.venv\Scripts\pip.exe install flask-jwt-extended flask-sqlalchemy
echo 依赖包安装完成
pause
