# PowerShell script for deploying Survey API to EC2
# Run this from your local Windows machine

$EC2_HOST = "ec2-15-223-192-87.ca-central-1.compute.amazonaws.com"
$EC2_USER = "ubuntu"
$KEY_PATH = "E:\aws-services-stage.pem"
$PROJECT_DIR = "E:\surveyProj"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Survey API - Deployment to EC2" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Pre-flight checks
Write-Host "Step 0: Pre-flight checks..." -ForegroundColor Yellow

# Check if key file exists
if (-not (Test-Path $KEY_PATH)) {
    Write-Host "ERROR: Key file not found at: $KEY_PATH" -ForegroundColor Red
    Write-Host "Please verify the key file path and try again." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Key file found: $KEY_PATH" -ForegroundColor Green

# Check if project directory exists
if (-not (Test-Path $PROJECT_DIR)) {
    Write-Host "ERROR: Project directory not found at: $PROJECT_DIR" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Project directory found: $PROJECT_DIR" -ForegroundColor Green
Write-Host ""

# Step 1: Test SSH connection
Write-Host "Step 1: Testing SSH connection..." -ForegroundColor Yellow
Write-Host "  Attempting to connect to: $EC2_USER@$EC2_HOST" -ForegroundColor Gray

$testConnection = ssh -i $KEY_PATH -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes "$EC2_USER@$EC2_HOST" "echo 'Connection successful'" 2>&1
$connectionError = $testConnection | Out-String

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Cannot connect to EC2 instance!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Connection Error Details:" -ForegroundColor Yellow
    Write-Host $connectionError -ForegroundColor Gray
    Write-Host ""
    Write-Host "Troubleshooting Steps:" -ForegroundColor Yellow
    Write-Host "  1. Verify EC2 instance is running in AWS Console" -ForegroundColor White
    Write-Host "  2. Check Security Group allows SSH (port 22) from your IP address" -ForegroundColor White
    Write-Host "  3. Verify the key file permissions (should be readable only by you)" -ForegroundColor White
    Write-Host "  4. Try manual connection:" -ForegroundColor White
    $manualCmd = 'ssh -i "' + $KEY_PATH + '" ' + $EC2_USER + '@' + $EC2_HOST
    Write-Host ('     ' + $manualCmd) -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Would you like to:" -ForegroundColor Yellow
    Write-Host "  A) Skip connection test and proceed with file transfer (may fail)" -ForegroundColor White
    Write-Host "  B) Exit and fix connection issues first" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "Enter choice (A/B)"
    
    if ($choice -ne "A" -and $choice -ne "a") {
        Write-Host "Exiting. Please fix connection issues and try again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Proceeding with file transfer (connection may fail)..." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Connection successful!" -ForegroundColor Green
}
Write-Host ""

# Step 2: Transfer project files (excluding node_modules)
Write-Host "Step 2: Transferring project files to EC2 (excluding node_modules)..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

# Create a temporary directory without node_modules
$tempDir = Join-Path $env:TEMP "surveyProj-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "  Creating temporary directory without node_modules..." -ForegroundColor Gray

# Copy project files excluding node_modules and other unnecessary files
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy all files and folders except excluded ones
$excludeItems = @('node_modules', '.git', 'logs', '.DS_Store')
Get-ChildItem -Path $PROJECT_DIR -Force | Where-Object { 
    $excludeItems -notcontains $_.Name -and 
    $_.Name -notlike '*.log' 
} | ForEach-Object {
    if ($_.PSIsContainer) {
        Copy-Item -Path $_.FullName -Destination (Join-Path $tempDir $_.Name) -Recurse -Force
    } else {
        Copy-Item -Path $_.FullName -Destination (Join-Path $tempDir $_.Name) -Force
    }
}

# Verify node_modules is not in temp directory
if (Test-Path (Join-Path $tempDir "node_modules")) {
    Write-Host "  WARNING: node_modules still found, removing..." -ForegroundColor Yellow
    Remove-Item -Path (Join-Path $tempDir "node_modules") -Recurse -Force -ErrorAction SilentlyContinue
}

# Transfer the cleaned directory contents
Write-Host "  Transferring files (node_modules excluded)..." -ForegroundColor Gray
# Ensure remote directory exists and is clean
ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" "mkdir -p ~/surveyProj"
# Transfer the entire temp directory, then move contents to surveyProj
$tempDirName = Split-Path -Leaf $tempDir
scp -i $KEY_PATH -r "$tempDir" "$EC2_USER@${EC2_HOST}:~/"
# Move contents from temp directory to surveyProj
ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" "cp -r ~/$tempDirName/* ~/surveyProj/ 2>/dev/null || mv ~/$tempDirName/* ~/surveyProj/ 2>/dev/null; rm -rf ~/$tempDirName"

# Clean up temporary directory
Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to transfer files!" -ForegroundColor Red
    exit 1
}
Write-Host "Files transferred successfully (node_modules excluded)!" -ForegroundColor Green
Write-Host "  (node_modules will be installed fresh during Docker build)" -ForegroundColor Gray
Write-Host ""

# Step 3: Aggressive disk space cleanup
Write-Host "Step 3: Performing aggressive disk space cleanup..." -ForegroundColor Yellow
Write-Host "  WARNING: This will remove ALL Docker images, containers, and volumes!" -ForegroundColor Yellow
$cleanupCommand = "echo '=== Aggressive Disk Space Cleanup ===' && echo 'Current disk usage:' && df -h / && echo '' && echo 'Stopping all containers...' && docker-compose -f ~/surveyProj/docker-compose.yml down 2>/dev/null || true && docker stop $(docker ps -aq) 2>/dev/null || true && echo 'Removing ALL containers...' && docker rm -f $(docker ps -aq) 2>/dev/null || true && echo 'Removing ALL images...' && docker rmi -f $(docker images -aq) 2>/dev/null || true && echo 'Removing ALL volumes...' && docker volume rm $(docker volume ls -q) 2>/dev/null || true && echo 'Removing build cache...' && docker builder prune -a -f && echo 'System prune...' && docker system prune -a -f --volumes 2>/dev/null || docker system prune -a -f && echo 'Cleaning npm cache...' && rm -rf /root/.npm 2>/dev/null || true && echo 'Cleaning Docker logs...' && truncate -s 0 /var/lib/docker/containers/*/*-json.log 2>/dev/null || true && echo '' && echo '=== Disk Space After Cleanup ===' && df -h /"
ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" $cleanupCommand
Write-Host ""

# Step 4: Run deployment on EC2
Write-Host "Step 4: Running deployment on EC2..." -ForegroundColor Yellow

# Run Docker commands (using semicolons to avoid line ending issues)
$deployCommand = "cd ~/surveyProj && echo '=== Stopping existing containers ===' && docker-compose down && echo '=== Building new Docker images ===' && docker-compose build --no-cache && echo '=== Starting containers ===' && docker-compose up -d && echo '=== Waiting for services to start ===' && sleep 10 && echo '=== Checking container status ===' && docker ps && echo '=== Showing recent logs ===' && docker-compose logs --tail=50"

ssh -i $KEY_PATH "$EC2_USER@$EC2_HOST" $deployCommand
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed!" -ForegroundColor Red
    Write-Host "Please check the logs on the EC2 instance" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test your API:" -ForegroundColor Yellow
$apiUrl = 'http://' + $EC2_HOST + ':3000/api/test'
Write-Host ('  ' + $apiUrl) -ForegroundColor White
Write-Host ""
Write-Host "To view logs, SSH into EC2 and run:" -ForegroundColor Yellow
Write-Host '  docker-compose logs -f' -ForegroundColor White
Write-Host ""
