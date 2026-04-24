param(
    [string]$BaseUrl = "http://127.0.0.1:8011",
    [string]$Email = "async-test-user@example.com",
    [string]$Password = "test12345",
    [int]$PollCount = 10,
    [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"

function Invoke-ApiJson {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$Body = "",
        [string]$ContentType = "application/json"
    )

    if ($Body -and $ContentType) {
        return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -ContentType $ContentType -Body $Body
    }

    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers
}

Write-Host "[1/8] Checking Redis TCP connectivity on localhost:6379..." -ForegroundColor Cyan
$redisCheck = Test-NetConnection -ComputerName localhost -Port 6379
if (-not $redisCheck.TcpTestSucceeded) {
    throw "Redis is not reachable on localhost:6379. Install/start Redis, then rerun this validation."
}
Write-Host "Redis is reachable." -ForegroundColor Green

$backendRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pythonExe = Join-Path $backendRoot "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv executable not found at $pythonExe"
}

Write-Host "[2/8] Running Celery healthcheck task roundtrip (true async)..." -ForegroundColor Cyan
$healthcheckCode = "from app.tasks import healthcheck_task; r=healthcheck_task.delay(); p=r.get(timeout=20); assert p.get('status')=='ok', p; print('task_id=' + r.id); print('payload=' + str(p))"
$nativeErrorPref = $PSNativeCommandUseErrorActionPreference
$PSNativeCommandUseErrorActionPreference = $false
try {
    $healthcheckOutput = & $pythonExe -c $healthcheckCode 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Celery healthcheck task did not complete successfully. Ensure worker and beat are running. Output: $healthcheckOutput"
    }
    $healthcheckOutput | ForEach-Object { Write-Host $_ }
} finally {
    $PSNativeCommandUseErrorActionPreference = $nativeErrorPref
}
Write-Host "Celery worker roundtrip OK." -ForegroundColor Green

Write-Host "[3/8] Checking backend health endpoint..." -ForegroundColor Cyan
$root = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/"
Write-Host "Server says: $($root.message)" -ForegroundColor Green

Write-Host "[4/8] Signup (safe if user exists)..." -ForegroundColor Cyan
try {
    $null = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/signup" -Body (@{ email = $Email; password = $Password } | ConvertTo-Json)
    Write-Host "Signup completed." -ForegroundColor Green
} catch {
    Write-Host "Signup skipped (likely existing user)." -ForegroundColor Yellow
}

Write-Host "[5/8] Login..." -ForegroundColor Cyan
$login = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/login" -ContentType "application/x-www-form-urlencoded" -Body "username=$Email&password=$Password"
if (-not $login.access_token) {
    throw "Login failed: no token returned."
}
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Write-Host "Login OK." -ForegroundColor Green

Write-Host "[6/8] Ensure at least one topic exists and trigger ingestion..." -ForegroundColor Cyan
$seedTopic = "Technology"
try {
    $null = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/topics" -Headers $headers -Body (@{ name = $seedTopic } | ConvertTo-Json)
} catch {
    # Topic likely exists already.
}

$topics = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/topics" -Headers $headers
if (-not $topics -or $topics.Count -eq 0) {
    throw "No topics found."
}
$topicId = $topics[0].id

$job = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/articles/fetch-and-process" -Headers $headers -Body (@{ topic_ids = @($topicId) } | ConvertTo-Json)
$jobJson = $job | ConvertTo-Json -Depth 6
Write-Host $jobJson

if (-not $job.task_id) {
    throw "Expected async queue response with task_id, but got fallback/sync response. Redis/Celery queue is not functioning end-to-end."
}
Write-Host "Async queue accepted run_id=$($job.run_id), task_id=$($job.task_id)." -ForegroundColor Green

Write-Host "[7/8] Polling ingestion run until completion..." -ForegroundColor Cyan
$finalStatus = $null
for ($i = 1; $i -le $PollCount; $i++) {
    Start-Sleep -Seconds $PollSeconds
    $run = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/ingestion/runs/$($job.run_id)" -Headers $headers
    Write-Host ("Poll {0}/{1}: status={2}, success={3}, fail={4}, discovered={5}, scraped={6}" -f $i, $PollCount, $run.status, $run.success_count, $run.fail_count, $run.urls_discovered, $run.urls_scraped)

    if ($run.status -in @("completed", "completed_with_errors", "failed")) {
        $finalStatus = $run.status
        break
    }
}

if (-not $finalStatus) {
    throw "Ingestion run did not finish within timeout window."
}

Write-Host "[8/8] Validation complete. Final status: $finalStatus" -ForegroundColor Green
