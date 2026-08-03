param(
    [string]$Department = "orbitinfer"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$departmentDataPath = Join-Path $repoRoot "site\app\department-data.json"
$departmentData = Get-Content -LiteralPath $departmentDataPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$departmentEntry = $departmentData.departments |
    Where-Object {
        $_.id -eq $Department -or $_.slug -eq $Department
    } |
    Select-Object -First 1
if (-not $departmentEntry) {
    throw "Unknown department: $Department"
}
$departmentSlug = $departmentEntry.slug
$logDirectory = Join-Path $repoRoot "runs\local"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

function Test-LocalPort {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return $task.Wait(800) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

if (-not (Test-LocalPort -Port 3000)) {
    $nodeCommand = (Get-Command node.exe).Source
    $vinextCli = Join-Path $repoRoot "site\node_modules\vinext\dist\cli.js"
    $siteStart = [System.Diagnostics.ProcessStartInfo]::new()
    $siteStart.FileName = $nodeCommand
    $siteStart.Arguments = (
        "`"$vinextCli`" dev --hostname 127.0.0.1 --port 3000"
    )
    $siteStart.WorkingDirectory = Join-Path $repoRoot "site"
    $siteStart.UseShellExecute = $true
    $siteStart.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [System.Diagnostics.Process]::Start($siteStart) | Out-Null
}

$deadline = [DateTime]::UtcNow.AddSeconds(30)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-LocalPort -Port 3000) {
        Write-Output (
            "Local read-only preview is ready at " +
            "http://127.0.0.1:3000/departments/$departmentSlug/"
        )
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "Local read-only preview did not become ready within 30 seconds."
