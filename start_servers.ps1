<#
Start前后端服务器的PowerShell脚本
Author: CAD-change
Date: 2026-01-09
#>

Clear-Host
Write-Host "========================================"
Write-Host "    CAD-change Server Startup Script"
Write-Host "========================================"
Write-Host ""
Write-Host "Checking environment..."

# Check Python installation
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "✓ Python installed"
} else {
    Write-Host "Error: Python not installed or not in PATH"
    Write-Host "Please install Python 3.6 or higher"
    Read-Host "Press any key to exit..."
    exit 1
}

# Check Node.js installation
if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "✓ Node.js installed"
} else {
    Write-Host "Error: Node.js not installed or not in PATH"
    Write-Host "Please install Node.js 14 or higher"
    Read-Host "Press any key to exit..."
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "    Starting Backend Server (Port: 8000)"
Write-Host "========================================"

# Start backend server in new window
$backendCmd = "cd /d `"$PSScriptRoot`" && python backend/app.py"
Start-Process cmd.exe -ArgumentList "/k", $backendCmd

# Wait for backend to start
Write-Host "Waiting for backend server to start..."
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================"
Write-Host "    Starting Frontend Server (Port: 3000)"
Write-Host "========================================"

Write-Host "Checking frontend dependencies..."

# Navigate to frontend directory
$frontendDir = Join-Path -Path $PSScriptRoot -ChildPath "web-app"

# Check if node_modules exists
if (-not (Test-Path -Path "$frontendDir\node_modules")) {
    Write-Host "First run, installing frontend dependencies..."
    Set-Location -Path $frontendDir
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Frontend dependencies installation failed"
        Read-Host "Press any key to exit..."
        exit 1
    }
    Write-Host "✓ Frontend dependencies installed"
}

Write-Host ""
Write-Host "Starting frontend server..."

# Start frontend server in new window
$frontendCmd = "cd /d `"$frontendDir`" && npm run dev -- --host"
Start-Process cmd.exe -ArgumentList "/k", $frontendCmd

Write-Host ""
Write-Host "========================================"
Write-Host "    Servers Started Successfully"
Write-Host ""
Write-Host "Frontend Server: http://localhost:3000"
Write-Host "Backend Server: http://localhost:8000"
Write-Host "Remote Access: http://$env:COMPUTERNAME:3000 or http://[Your IP Address]:3000"
Write-Host ""
Write-Host "Notes:"
Write-Host "1. Please ensure both server windows are running properly"
Write-Host "2. Closing this window won't affect the servers"
Write-Host "3. To stop servers, press Ctrl+C in their respective windows"
Write-Host "========================================"

# Open browser
Write-Host "Opening browser to frontend..."
Start-Process "http://localhost:3000"

Read-Host "Press any key to exit..."
