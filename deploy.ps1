# 部署脚本 - Windows版本
# 使用方法: powershell -ExecutionPolicy Bypass -File deploy.ps1

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "    羿射旭阻尼器设计工具集 - 部署脚本"
Write-Host "=========================================="
Write-Host ""

# 检查Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "错误: Python 未安装" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python 已安装" -ForegroundColor Green

# 检查Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "错误: Node.js 未安装" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Node.js 已安装" -ForegroundColor Green

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "=========================================="
Write-Host "    1. 构建前端"
Write-Host "=========================================="

Set-Location "$ScriptDir\web-app"

# 安装前端依赖（如果node_modules不存在）
if (-not (Test-Path "node_modules")) {
    Write-Host "安装前端依赖..."
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 前端依赖安装失败" -ForegroundColor Red
        exit 1
    }
}

# 构建生产版本
Write-Host "构建生产版本..."
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 前端构建失败" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 前端构建完成" -ForegroundColor Green

Write-Host ""
Write-Host "=========================================="
Write-Host "    2. 安装后端依赖"
Write-Host "=========================================="

Set-Location "$ScriptDir\backend"

# 创建虚拟环境（如果不存在）
if (-not (Test-Path "venv")) {
    Write-Host "创建Python虚拟环境..."
    python -m venv venv
}

# 安装依赖
Write-Host "安装后端依赖..."
& "$ScriptDir\backend\venv\Scripts\pip.exe" install -r requirements.txt

Write-Host "✓ 后端依赖安装完成" -ForegroundColor Green

Write-Host ""
Write-Host "=========================================="
Write-Host "    3. 部署完成"
Write-Host "=========================================="
Write-Host ""
Write-Host "启动命令："
Write-Host "  后端: $ScriptDir\backend\venv\Scripts\python.exe app.py"
Write-Host ""
Write-Host "✓ 部署成功！" -ForegroundColor Green
