param(
    [switch]$NoReload,
    [switch]$Reload,
    [switch]$SkipCleanup
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $repoRoot "backend"
$frontendPath = Join-Path $repoRoot "frontend"
$pythonExe = Join-Path $backendPath "venv\Scripts\python.exe"
$logPath = Join-Path $repoRoot ".run-dev-logs"
$backendPort = 8011
$frontendPort = 5173

if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at '$pythonExe'. Create/activate backend venv first."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is not available in PATH. Install Node.js first."
}

if (-not (Test-Path $logPath)) {
    New-Item -ItemType Directory -Path $logPath | Out-Null
}

function Stop-PortListeners {
    param(
        [int[]]$Ports
    )

    foreach ($port in $Ports) {
        $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
        foreach ($listener in $listeners) {
            $ownerPid = $listener.OwningProcess
            if ($ownerPid -eq $PID -or $ownerPid -eq 0) {
                continue
            }

            try {
                Stop-Process -Id $ownerPid -Force -ErrorAction Stop
                Write-Host "Stopped process $ownerPid listening on port $port."
            }
            catch {
                Write-Warning "Failed to stop process $ownerPid on port $port."
            }
        }
    }
}

function Find-ServiceProcessId {
    param(
        [string]$Pattern,
        [int]$LocalPort = 0,
        [bool]$SkipRepoMatch = $false,
        [int[]]$ExcludeIds = @()
    )

    if ($LocalPort -gt 0) {
        $listener = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($listener -and $listener.OwningProcess -and $listener.OwningProcess -ne $PID -and ($ExcludeIds -notcontains $listener.OwningProcess)) {
            return [int]$listener.OwningProcess
        }
    }

    if (-not $Pattern) {
        return $null
    }

    $repoRootPattern = [Regex]::Escape($repoRoot)

    $candidates = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and
        $_.ProcessId -ne $PID -and
        ($ExcludeIds -notcontains $_.ProcessId)
    }

    if (-not $SkipRepoMatch) {
        $candidates = $candidates | Where-Object { $_.CommandLine -match $repoRootPattern }
    }

    $candidate = $candidates | Where-Object { $_.CommandLine -match $Pattern } | Select-Object -First 1

    if ($candidate) {
        return [int]$candidate.ProcessId
    }

    return $null
}

if (-not $SkipCleanup) {
    Stop-PortListeners -Ports @($backendPort, $frontendPort)

    $repoRootPattern = [Regex]::Escape($repoRoot)
    $staleProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and
        $_.ProcessId -ne $PID -and
        $_.CommandLine -match $repoRootPattern -and
        (
            $_.CommandLine -match "uvicorn|celery|vite --host|npm.cmd run dev"
        )
    }

    foreach ($stale in $staleProcesses) {
        try {
            Stop-Process -Id $stale.ProcessId -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Failed to stop stale process $($stale.ProcessId)."
        }
    }

    if ($staleProcesses.Count -gt 0) {
        Write-Host "Stopped $($staleProcesses.Count) stale dev process(es)."
    }
}

$runStamp = Get-Date -Format "yyyyMMdd-HHmmss"

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort")
if ($Reload -and -not $NoReload) {
    $uvicornArgs += "--reload"
}

$services = @(
    @{
        Name = "backend-api"
        Cwd = $backendPath
        Command = $pythonExe
        Args = $uvicornArgs
        HealthPattern = "uvicorn\s+app\.main:app\s+--host\s+127\.0\.0\.1\s+--port\s+$backendPort"
        HealthPort = $backendPort
        SkipRepoMatch = $false
    },
    @{
        Name = "celery-worker"
        Cwd = $backendPath
        Command = $pythonExe
        Args = @("-m", "celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "-P", "solo")
        HealthPattern = "celery\s+-A\s+app\.celery_app\.celery_app\s+worker"
        HealthPort = 0
        SkipRepoMatch = $false
    },
    @{
        Name = "celery-beat"
        Cwd = $backendPath
        Command = $pythonExe
        Args = @("-m", "celery", "-A", "app.celery_app.celery_app", "beat", "--loglevel=info")
        HealthPattern = "celery\s+-A\s+app\.celery_app\.celery_app\s+beat"
        HealthPort = 0
        SkipRepoMatch = $false
    },
    @{
        Name = "frontend-vite"
        Cwd = $frontendPath
        Command = "npm.cmd"
        Args = @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort")
        HealthPattern = "vite\s+--host\s+127\.0\.0\.1\s+--port\s+$frontendPort"
        HealthPort = $frontendPort
        SkipRepoMatch = $true
    }
)

$processes = @()
$stdoutCounts = @{}
$stderrCounts = @{}

function Read-NewLines {
    param(
        [string]$FilePath,
        [int]$CurrentCount
    )

    if (-not (Test-Path $FilePath)) {
        return @{ Count = $CurrentCount; Lines = @() }
    }

    $allLines = Get-Content -Path $FilePath -ErrorAction SilentlyContinue
    if (-not $allLines) {
        return @{ Count = 0; Lines = @() }
    }

    if ($CurrentCount -ge $allLines.Count) {
        return @{ Count = $allLines.Count; Lines = @() }
    }

    $newLines = $allLines[$CurrentCount..($allLines.Count - 1)]
    return @{ Count = $allLines.Count; Lines = $newLines }
}

foreach ($service in $services) {
    $stdoutFile = Join-Path $logPath "$($service.Name).$runStamp.out.log"
    $stderrFile = Join-Path $logPath "$($service.Name).$runStamp.err.log"

    $argText = $service.Args | ForEach-Object {
        if ($_ -match "\s") {
            '"' + $_ + '"'
        } else {
            $_
        }
    }

    Write-Host "[$($service.Name)] starting in $($service.Cwd)"
    $proc = Start-Process -FilePath $service.Command -ArgumentList $argText -WorkingDirectory $service.Cwd -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -WindowStyle Hidden -PassThru

    $processes += [pscustomobject]@{
        Name = $service.Name
        Process = $proc
        Stdout = $stdoutFile
        Stderr = $stderrFile
        HealthPattern = $service.HealthPattern
        HealthPort = $service.HealthPort
        SkipRepoMatch = $service.SkipRepoMatch
    }

    $stdoutCounts[$service.Name] = 0
    $stderrCounts[$service.Name] = 0
}

Write-Host "All services started: $($services.Name -join ', ')"
Write-Host "Press Ctrl+C to stop everything."

try {
    while ($true) {
        foreach ($svc in $processes) {
            $stdoutResult = Read-NewLines -FilePath $svc.Stdout -CurrentCount $stdoutCounts[$svc.Name]
            $stdoutCounts[$svc.Name] = $stdoutResult.Count
            foreach ($line in $stdoutResult.Lines) {
                Write-Host "[$($svc.Name)] $line"
            }

            $stderrResult = Read-NewLines -FilePath $svc.Stderr -CurrentCount $stderrCounts[$svc.Name]
            $stderrCounts[$svc.Name] = $stderrResult.Count
            foreach ($line in $stderrResult.Lines) {
                Write-Host "[$($svc.Name)] STDERR: $line"
            }
        }

        $exited = $processes | Where-Object { $_.Process.HasExited }
        if ($exited.Count -gt 0) {
            $verifiedExited = @()

            foreach ($svc in $exited) {
                $replacementPid = Find-ServiceProcessId -Pattern $svc.HealthPattern -LocalPort $svc.HealthPort -SkipRepoMatch $svc.SkipRepoMatch -ExcludeIds @($svc.Process.Id)
                if ($replacementPid) {
                    try {
                        $replacementProc = Get-Process -Id $replacementPid -ErrorAction Stop
                        $svc.Process = $replacementProc
                        Write-Warning "Service '$($svc.Name)' launcher process exited, but child process $replacementPid is running. Monitoring child process."
                        continue
                    }
                    catch {
                        # If the candidate process vanishes between lookup and attach,
                        # treat this as a real exit below.
                    }
                }

                $verifiedExited += $svc
            }

            if ($verifiedExited.Count -eq 0) {
                Start-Sleep -Milliseconds 700
                continue
            }

            foreach ($svc in $verifiedExited) {
                $stdoutResult = Read-NewLines -FilePath $svc.Stdout -CurrentCount $stdoutCounts[$svc.Name]
                foreach ($line in $stdoutResult.Lines) {
                    Write-Host "[$($svc.Name)] $line"
                }

                $stderrResult = Read-NewLines -FilePath $svc.Stderr -CurrentCount $stderrCounts[$svc.Name]
                foreach ($line in $stderrResult.Lines) {
                    Write-Host "[$($svc.Name)] STDERR: $line"
                }

                $exitCode = "unknown"
                try {
                    $exitCode = $svc.Process.ExitCode
                }
                catch {
                    # keep unknown
                }

                Write-Warning "Service '$($svc.Name)' exited with code $exitCode."
            }
            throw "One or more services exited. Stopping all services."
        }

        Start-Sleep -Milliseconds 700
    }
}
finally {
    foreach ($svc in $processes) {
        if (-not $svc.Process.HasExited) {
            Stop-Process -Id $svc.Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "All services stopped."
}
