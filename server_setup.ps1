# 服务器端设置脚本 - 局域网部署
# 在服务器上以管理员身份运行一次即可

$ErrorActionPreference = "Stop"

$configPath = Join-Path $PSScriptRoot "deploy.config.ps1"
if (Test-Path $configPath) {
    . $configPath
    $AppPath = $DeployServerPath
} else {
    $AppPath = "D:\yishexu-designtools"
}

Write-Host "=========================================="
Write-Host "    Server Setup Script"
Write-Host "=========================================="
Write-Host ""
Write-Host "App path: $AppPath"
Write-Host ""

# Create application directory
if (-not (Test-Path $AppPath)) {
    New-Item -ItemType Directory -Path $AppPath -Force | Out-Null
}

# Create file share with READ/WRITE access
Write-Host "Setting up file share..."
$ShareName = "yishexu-designtools"

# Check if share already exists
try {
    $existingShare = net share | Select-String $ShareName
    if ($existingShare) {
        Write-Host "Removing old share..." -ForegroundColor Yellow
        net share $ShareName /DELETE 2>$null
    }
} catch {}

# Create share with full access (read/write)
net share $ShareName=$AppPath /GRANT:Everyone,FULL 2>$null

Write-Host "Created share: \\$env:COMPUTERNAME\$ShareName" -ForegroundColor Green
Write-Host "Access: Everyone (Full Control)" -ForegroundColor Yellow

Write-Host ""
Write-Host "Server setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Share path: \\$env:COMPUTERNAME\$ShareName"
