$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
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

if (-not (Test-LocalPort -Port 8010)) {
    $apiStart = [System.Diagnostics.ProcessStartInfo]::new()
    $apiStart.FileName = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $apiStart.Arguments = "-m weekly_intel.review_server"
    $apiStart.WorkingDirectory = $repoRoot
    $apiStart.UseShellExecute = $true
    $apiStart.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [System.Diagnostics.Process]::Start($apiStart) | Out-Null
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
    if ((Test-LocalPort -Port 8010) -and (Test-LocalPort -Port 3000)) {
        Write-Output "Local review is ready at http://127.0.0.1:3000/departments/orbitinfer/"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "Local review services did not become ready within 30 seconds."
