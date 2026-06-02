# Deploy Survey API + Survey Agent to EC2
# Run from: E:\surveyProj

$EC2_HOST = "ec2-15-223-192-87.ca-central-1.compute.amazonaws.com"
$EC2_USER = "ubuntu"
$KEY_PATH = "E:\aws-services-stage.pem"
$PROJECT_DIR = "E:\surveyProj"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Survey API + Survey Agent - Deploy to EC2" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Pre-flight
if (-not (Test-Path $KEY_PATH)) {
    Write-Host "ERROR: Key file not found: $KEY_PATH" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $PROJECT_DIR)) {
    Write-Host "ERROR: Project not found: $PROJECT_DIR" -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: SSH connection test..." -ForegroundColor Yellow
ssh -i $KEY_PATH -o ConnectTimeout=15 -o StrictHostKeyChecking=no -o BatchMode=yes "$EC2_USER@$EC2_HOST" "echo OK"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Cannot SSH to $EC2_USER@$EC2_HOST" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Connected" -ForegroundColor Green
Write-Host ""

# Step 2: Transfer files (exclude heavy dirs)
Write-Host "Step 2: Transferring project files..." -ForegroundColor Yellow
$tempDir = Join-Path $env:TEMP "surveyProj-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

$excludeItems = @('node_modules', '.git', 'logs', '.DS_Store', '.venv')
Get-ChildItem -Path $PROJECT_DIR -Force | Where-Object {
    $excludeItems -notcontains $_.Name -and $_.Name -notlike '*.log'
} | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination (Join-Path $tempDir $_.Name) -Recurse -Force
}

# Remove venv / node_modules if copied
@(
    (Join-Path $tempDir "node_modules"),
    (Join-Path $tempDir "survey-agent\.venv"),
    (Join-Path $tempDir "survey-agent\__pycache__")
) | ForEach-Object {
    if (Test-Path $_) { Remove-Item $_ -Recurse -Force -ErrorAction SilentlyContinue }
}

ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" "mkdir -p ~/surveyProj"
# Always sync root .env (DB + secrets) — same file Survey API uses
if (Test-Path (Join-Path $PROJECT_DIR ".env")) {
    scp -i $KEY_PATH (Join-Path $PROJECT_DIR ".env") "$EC2_USER@${EC2_HOST}:~/surveyProj/.env"
    Write-Host "  [OK] Synced .env to EC2" -ForegroundColor Green
}
$tempDirName = Split-Path -Leaf $tempDir
scp -i $KEY_PATH -r "$tempDir" "$EC2_USER@${EC2_HOST}:~/"
ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" "cp -r ~/$tempDirName/* ~/surveyProj/ 2>/dev/null; rm -rf ~/$tempDirName"
Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: File transfer failed" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Files transferred" -ForegroundColor Green
Write-Host ""

# Step 3: Free disk — stop other containers, prune
Write-Host "Step 3: Disk cleanup..." -ForegroundColor Yellow
$cleanupCommand = "df -h /; sudo systemctl stop agents-service 2>/dev/null || true; sudo systemctl disable agents-service 2>/dev/null || true; sudo fuser -k 8000/tcp 2>/dev/null || true; cd ~/surveyProj && (docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true); docker stop `$(docker ps -q) 2>/dev/null || true; docker rm -f `$(docker ps -aq) 2>/dev/null || true; docker image prune -af; docker builder prune -af; docker system prune -af; df -h /"
ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" $cleanupCommand
Write-Host ""

# Step 4: Build and start survey-api + survey-agent
Write-Host "Step 4: Building and starting containers (may take several minutes)..." -ForegroundColor Yellow
$deployCommand = "cd ~/surveyProj && if docker compose version >/dev/null 2>&1; then DC='docker compose'; else DC='docker-compose'; fi && `$DC down 2>/dev/null; `$DC build --no-cache && `$DC up -d && sleep 15 && docker ps && `$DC logs --tail=20 survey-api && `$DC logs --tail=20 survey-agent && curl -sf http://localhost:3000/api/test; echo; curl -sf http://localhost:8000/health; echo; curl -sf http://localhost:8000/health/db; echo"
ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" $deployCommand
$agentOk = ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" "curl -sf http://localhost:8000/health >/dev/null && echo OK || echo FAIL"
if ($agentOk -notmatch "OK") {
    Write-Host "ERROR: survey-agent health check failed on EC2" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Deployment completed!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test URLs:" -ForegroundColor Yellow
Write-Host "  Survey API:    http://${EC2_HOST}:3000/api/test" -ForegroundColor White
Write-Host "  Survey Agent:  http://${EC2_HOST}:8000/health" -ForegroundColor White
Write-Host "  Agent Swagger: http://${EC2_HOST}:8000/docs" -ForegroundColor White
Write-Host "  Agent DB check: http://${EC2_HOST}:8000/health/db" -ForegroundColor White
Write-Host ""
Write-Host "Chat (pass admin JWT in Authorization header):" -ForegroundColor Yellow
Write-Host '  POST http://' + $EC2_HOST + ':8000/chat' -ForegroundColor White
Write-Host ""
Write-Host "If port 8000 is blocked, open it in the EC2 security group." -ForegroundColor Gray
Write-Host "Logs: ssh then cd ~/surveyProj && docker compose logs -f survey-agent" -ForegroundColor Gray
Write-Host ""
