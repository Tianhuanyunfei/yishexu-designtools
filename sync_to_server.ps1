# Sync script - sync code to LAN server
# Run: .\sync_to_server.ps1
# Add -NoPause to skip "Press Enter" (for automation)
# Edit deploy.config.ps1 to change server host/path

param(
    [string]$ServerName,
    [string]$ServerPath,
    [string]$ConnectionMode,
    [string]$ShareName,
    [string]$Username,
    [string]$Password,
    [switch]$NoPause
)

. (Join-Path $PSScriptRoot "deploy.config.ps1")

if (-not $ServerName) { $ServerName = $DeployServerHost }
if (-not $ServerPath) { $ServerPath = $DeployServerPath }
if (-not $ConnectionMode) { $ConnectionMode = $DeployConnectionMode }
if (-not $ShareName) { $ShareName = $DeployShareName }
if (-not $Username) { $Username = $DeployShareUsername }
if (-not $Password) { $Password = $DeploySharePassword }

$ErrorActionPreference = "Stop"
$script:ExitCode = 0

function Show-ErrorDetail {
    param($ErrorRecord)
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "    Sync failed" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host $ErrorRecord.Exception.Message -ForegroundColor Red
    if ($ErrorRecord.InvocationInfo) {
        $loc = $ErrorRecord.InvocationInfo
        Write-Host "At: $($loc.ScriptName):$($loc.ScriptLineNumber)" -ForegroundColor Yellow
        if ($loc.Line) {
            Write-Host "Line: $($loc.Line.Trim())" -ForegroundColor DarkYellow
        }
    }
    if ($ErrorRecord.ScriptStackTrace) {
        Write-Host ""
        Write-Host "Stack trace:" -ForegroundColor Yellow
        Write-Host $ErrorRecord.ScriptStackTrace
    }
}

function Wait-BeforeExit {
    if ($NoPause) { return }
    Write-Host ""
    Read-Host "Press Enter to exit"
}

function Read-TerminalPassword {
    param([string]$Prompt = "Password")
    $securePassword = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Get-DeployUncPath {
    param(
        [string]$Server,
        [string]$LocalPath,
        [string]$Mode,
        [string]$Share
    )

    if ($Mode -eq "share") {
        return "\\$Server\$Share"
    }

    if ($LocalPath -match '^([A-Za-z]):\\(.*)$') {
        $drive = $matches[1]
        $subPath = $matches[2]
        return "\\$Server\${drive}`$\$subPath"
    }

    throw "Invalid DeployServerPath: $LocalPath (expected e.g. D:\yishexu-designtools)"
}

function Get-DeployShareCredential {
    param(
        [string]$UncPath,
        [string]$User,
        [string]$Pass
    )

    if ($User -and $Pass) {
        return @{ Username = $User; Password = $Pass }
    }

    Write-Host ""
    Write-Host "Remote path login required: $UncPath" -ForegroundColor Yellow
    Write-Host "Enter server administrator account (examples: .\Administrator  or  WIN-xxx\User)" -ForegroundColor DarkGray
    Write-Host ""

    if (-not $User) {
        $User = Read-Host "Username"
    }
    if (-not $User) {
        throw "Username is required"
    }

    if (-not $Pass) {
        $Pass = Read-TerminalPassword "Password"
    }
    if (-not $Pass) {
        throw "Password is required"
    }

    return @{ Username = $User; Password = $Pass }
}

function Connect-DeployShare {
    param(
        [string]$UncPath,
        [string]$User,
        [string]$Pass
    )

    if (Test-Path $UncPath) {
        Write-Host "OK: Remote path already accessible" -ForegroundColor Green
        return $UncPath
    }

    Write-Host "Remote path is not connected. Trying credential login..." -ForegroundColor Yellow

    $serverHost = ($UncPath -replace '^\\\\([^\\]+)\\.*$', '$1')
    if ($serverHost -and -not (Test-Connection -ComputerName $serverHost -Count 1 -Quiet -ErrorAction SilentlyContinue)) {
        Write-Host "WARNING: Cannot ping $serverHost (server may block ICMP, continuing...)" -ForegroundColor Yellow
    }

    $cred = Get-DeployShareCredential -UncPath $UncPath -User $User -Pass $Pass

    & net use $UncPath /delete /y 2>$null | Out-Null

    $netUseOutput = & net use $UncPath $cred.Password "/user:$($cred.Username)" /persistent:no 2>&1
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $UncPath)) {
        Write-Host "ERROR: Cannot connect to remote path" -ForegroundColor Red
        if ($netUseOutput) {
            Write-Host $netUseOutput -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "Please check:" -ForegroundColor Yellow
        Write-Host "  1. Server IP/host is reachable"
        Write-Host "  2. Remote path exists on server: $UncPath"
        Write-Host "  3. Username/password are correct (admin account for D$ share)"
        Write-Host "  4. Server allows admin share access"
        Write-Host ""
        Write-Host "Manual test:" -ForegroundColor Yellow
        Write-Host "  net use $UncPath /user:$($cred.Username)"
        throw "Remote path connection failed"
    }

    Write-Host "OK: Connected to remote path" -ForegroundColor Green
    return $UncPath
}

$remoteUncPath = Get-DeployUncPath -Server $ServerName -LocalPath $ServerPath -Mode $ConnectionMode -Share $ShareName

Write-Host "=========================================="
Write-Host "    Sync to LAN Server"
Write-Host "    Server: $ServerName"
Write-Host "    Local:  $ServerPath"
Write-Host "    Remote: $remoteUncPath"
Write-Host "=========================================="
Write-Host ""

try {

Write-Host "Testing server connection..."
$connectedPath = Connect-DeployShare -UncPath $remoteUncPath -User $Username -Pass $Password

$syncDirs = @("backend", "web-app", "client_download")

Write-Host ""
Write-Host "=========================================="
Write-Host "    Syncing code files"
Write-Host "=========================================="

foreach ($dir in $syncDirs) {
    $sourcePath = Join-Path $PSScriptRoot $dir
    $destPath = Join-Path $connectedPath $dir

    if (Test-Path $sourcePath) {
        Write-Host "Syncing $dir ..."

        if (-not (Test-Path $destPath)) {
            New-Item -ItemType Directory -Path $destPath -Force | Out-Null
        }

        & robocopy $sourcePath $destPath /E /MT:8 /NP /NFL /NDL /NJH /NJS | Out-Null

        if ($LASTEXITCODE -le 7) {
            Write-Host "  OK: $dir synced" -ForegroundColor Green
        } else {
            Write-Host "  ERROR: $dir sync failed (robocopy exit $LASTEXITCODE)" -ForegroundColor Red
            $script:ExitCode = 1
        }
    } else {
        Write-Host "  SKIP: source not found - $sourcePath" -ForegroundColor Yellow
    }
}

Write-Host "Syncing config files..."
$rootFiles = @("start_servers.ps1", "deploy.config.ps1")
foreach ($file in $rootFiles) {
    $sourceFile = Join-Path $PSScriptRoot $file
    if (Test-Path $sourceFile) {
        $destFile = Join-Path $connectedPath $file
        Copy-Item -Path $sourceFile -Destination $destFile -Force
        Write-Host "  OK: $file synced" -ForegroundColor Green
    }
}

if ($script:ExitCode -eq 0) {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "    Sync complete!" -ForegroundColor Green
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Server local path: $ServerPath"
    Write-Host "Remote UNC path:   $connectedPath"
}

} catch {
    $script:ExitCode = 1
    Show-ErrorDetail $_
} finally {
    Wait-BeforeExit
    if ($script:ExitCode -ne 0) { exit $script:ExitCode }
}
