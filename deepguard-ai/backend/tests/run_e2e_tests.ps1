# Step 1: Kill any existing server on port 8000
$existing = netstat -ano | Select-String ":8000" | Select-String "LISTENING"
if ($existing) {
    $oldpid = $existing.ToString().Trim().Split()[-1]
    Stop-Process -Id $oldpid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Step 2: Start server
$projDir = "D:\adk-workspace\deepguard-ai\backend"
$logFile = "$projDir\_debug_logs\server_log_e2e.txt"
$null = New-Item -ItemType Directory -Path "$projDir\_debug_logs" -Force
Remove-Item $logFile -ErrorAction SilentlyContinue
Start-Job -Name "e2e" -ScriptBlock { param($d,$lf) Set-Location $d; uv run uvicorn app.api:app --host 0.0.0.0 --port 8000 --log-level debug *>$lf } -ArgumentList $projDir, $logFile | Out-Null
Start-Sleep -Seconds 10

Write-Host "========================================"
Write-Host "=== 5.1 Server Start ==="
Write-Host "========================================"
Get-Content $logFile | Select-String -Pattern "Uvicorn running|Application startup complete|Started server"

Write-Host "`n========================================"
Write-Host "=== 5.2 Image Upload ==="
Write-Host "========================================"
$testImage = "D:\adk-workspace\deepguard-ai\.venv\images\imagehash.png"
$r1 = curl.exe -s -X POST "http://localhost:8000/api/analyze" -F "file=@$testImage" --max-time 120
$ec1 = $LASTEXITCODE
Write-Host "curl exit: $ec1"
if ($ec1 -eq 0) {
    $r1 | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

Write-Host "`n========================================"
Write-Host "=== 5.2 Server Log (media evidence) ==="
Write-Host "========================================"
Start-Sleep -Seconds 2
Get-Content $logFile | Select-String -Pattern "XXX|Media|Attaching|Router decision"

Write-Host "`n========================================"
Write-Host "=== 5.3 Video Upload ==="
Write-Host "========================================"
$testVideo = "$projDir\tests\test_video.mp4"
$r2 = curl.exe -s -X POST "http://localhost:8000/api/analyze" -F "file=@$testVideo" --max-time 120
$ec2 = $LASTEXITCODE
Write-Host "curl exit: $ec2"
if ($ec2 -eq 0) {
    $r2 | ConvertFrom-Json | ConvertTo-Json -Depth 10
} else {
    Write-Host "curl failed with exit code $ec2"
    Start-Sleep -Seconds 1
    Get-Content $logFile -Tail 20 | Select-String -Pattern "Error|error|Permission|WinError|traceback|failed|Pipeline"
}

Write-Host "`n========================================"
Write-Host "=== Server Log (video frame extraction) ==="
Write-Host "========================================"
Start-Sleep -Seconds 2
Get-Content $logFile | Select-String -Pattern "Video|frame|cached|Media|Attaching|XXX|shared"
