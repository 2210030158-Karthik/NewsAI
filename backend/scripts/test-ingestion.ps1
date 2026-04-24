param(
    [string]$BaseUrl = "http://127.0.0.1:8011",
    [string]$Email = "testuser1@example.com",
    [string]$Password = "test12345",
    [int]$TopicsToUse = 3,
    [int]$PollCount = 8,
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

Write-Host "[1/8] Health check..." -ForegroundColor Cyan
$root = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/"
Write-Host "Server says: $($root.message)" -ForegroundColor Green

Write-Host "[2/8] Signup (safe if already exists)..." -ForegroundColor Cyan
try {
    $null = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/signup" -Body (@{ email = $Email; password = $Password } | ConvertTo-Json)
    Write-Host "Signup completed." -ForegroundColor Green
} catch {
    Write-Host "Signup skipped (likely existing user)." -ForegroundColor Yellow
}

Write-Host "[3/8] Login..." -ForegroundColor Cyan
$login = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/login" -ContentType "application/x-www-form-urlencoded" -Body "username=$Email&password=$Password"
if (-not $login.access_token) {
    throw "Login failed: no token returned."
}
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Write-Host "Login OK." -ForegroundColor Green

Write-Host "[4/8] Ensure seed topics..." -ForegroundColor Cyan
$seedTopics = @("Technology", "AI", "Startups")
foreach ($topicName in $seedTopics) {
    try {
        $null = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/topics" -Headers $headers -Body (@{ name = $topicName } | ConvertTo-Json)
        Write-Host "Created topic: $topicName" -ForegroundColor Green
    } catch {
        Write-Host "Topic exists or not created: $topicName" -ForegroundColor Yellow
    }
}

Write-Host "[5/8] Load topics..." -ForegroundColor Cyan
$topics = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/topics" -Headers $headers
if (-not $topics -or $topics.Count -eq 0) {
    throw "No topics available."
}
$topicIds = @($topics | Select-Object -First $TopicsToUse | ForEach-Object { $_.id })
if ($topicIds.Count -eq 0) {
    throw "Could not select topic IDs."
}
Write-Host "Using topic IDs: $($topicIds -join ', ')" -ForegroundColor Green

Write-Host "[6/8] Trigger ingestion..." -ForegroundColor Cyan
$job = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/articles/fetch-and-process" -Headers $headers -Body (@{ topic_ids = $topicIds } | ConvertTo-Json)
$job | ConvertTo-Json -Depth 6

if (-not $job.run_id) {
    Write-Host "No run_id returned. This means sync mode is active (ENABLE_ASYNC_INGESTION=false) or endpoint returned a non-queued response." -ForegroundColor Yellow
    Write-Host "Done." -ForegroundColor Green
    exit 0
}

Write-Host "[7/8] Poll ingestion run status for run_id=$($job.run_id)..." -ForegroundColor Cyan
for ($i = 1; $i -le $PollCount; $i++) {
    Start-Sleep -Seconds $PollSeconds
    $run = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/ingestion/runs/$($job.run_id)" -Headers $headers
    Write-Host ("Poll {0}/{1}: status={2}, success={3}, fail={4}, discovered={5}, scraped={6}" -f $i, $PollCount, $run.status, $run.success_count, $run.fail_count, $run.urls_discovered, $run.urls_scraped)

    if ($run.status -in @("completed", "completed_with_errors", "failed")) {
        Write-Host "Run finished with status: $($run.status)" -ForegroundColor Green
        break
    }
}

Write-Host "[8/8] Done." -ForegroundColor Green
