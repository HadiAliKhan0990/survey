# PowerShell script to test and troubleshoot EC2 SSH connection
# Run this to diagnose connection issues

$EC2_HOST = "ec2-15-223-192-87.ca-central-1.compute.amazonaws.com"
$EC2_USER = "ubuntu"
$KEY_PATH = "E:\aws-services-stage.pem"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "EC2 Connection Diagnostic Tool" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check key file
Write-Host "Test 1: Checking key file..." -ForegroundColor Yellow
if (Test-Path $KEY_PATH) {
    Write-Host "  [OK] Key file exists: $KEY_PATH" -ForegroundColor Green
    
    # Check permissions
    $acl = Get-Acl $KEY_PATH
    $hasReadAccess = $false
    foreach ($access in $acl.Access) {
        if ($access.IdentityReference -eq $env:USERNAME -and $access.FileSystemRights -match "Read") {
            $hasReadAccess = $true
            break
        }
    }
    if ($hasReadAccess) {
        Write-Host "  [OK] Key file is readable" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] Key file may have permission issues" -ForegroundColor Yellow
        $fixCmd = 'icacls "' + $KEY_PATH + '" /inheritance:r /grant:r "' + $env:USERNAME + ':R"'
        Write-Host ('    Run: ' + $fixCmd) -ForegroundColor Cyan
    }
} else {
    Write-Host "  [ERROR] Key file NOT found: $KEY_PATH" -ForegroundColor Red
    Write-Host "    Please verify the path and try again." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 2: DNS Resolution
Write-Host "Test 2: Testing DNS resolution..." -ForegroundColor Yellow
try {
    $dnsResult = Resolve-DnsName $EC2_HOST -ErrorAction Stop
    Write-Host "  [OK] DNS resolved successfully" -ForegroundColor Green
    Write-Host ('    IP Address: ' + $dnsResult[0].IPAddress) -ForegroundColor Gray
} catch {
    Write-Host "  [ERROR] DNS resolution failed" -ForegroundColor Red
    Write-Host ('    Error: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 3: Port connectivity
Write-Host "Test 3: Testing port 22 connectivity..." -ForegroundColor Yellow
try {
    $dnsResult = Resolve-DnsName $EC2_HOST
    $ipAddress = $dnsResult[0].IPAddress
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connect = $tcpClient.BeginConnect($ipAddress, 22, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(5000, $false)
    if ($wait) {
        $tcpClient.EndConnect($connect)
        Write-Host "  [OK] Port 22 is open and accessible" -ForegroundColor Green
        $tcpClient.Close()
    } else {
        Write-Host "  [ERROR] Port 22 connection timeout" -ForegroundColor Red
        Write-Host "    This usually means:" -ForegroundColor Yellow
        Write-Host "    - Security Group doesn't allow SSH from your IP" -ForegroundColor White
        Write-Host "    - EC2 instance is not running" -ForegroundColor White
        Write-Host "    - Firewall is blocking the connection" -ForegroundColor White
    }
} catch {
    Write-Host "  [ERROR] Port 22 connection failed" -ForegroundColor Red
    Write-Host ('    Error: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    if ($null -ne $tcpClient -and $tcpClient.Connected) {
        $tcpClient.Close()
    }
}
Write-Host ""

# Test 4: SSH connection
Write-Host "Test 4: Testing SSH connection..." -ForegroundColor Yellow
$sshCmd = 'ssh -i "' + $KEY_PATH + '" ' + $EC2_USER + '@' + $EC2_HOST
Write-Host ('  Command: ' + $sshCmd) -ForegroundColor Gray
Write-Host ""

$sshTest = ssh -i $KEY_PATH -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes "$EC2_USER@$EC2_HOST" "echo 'SSH connection successful'" 2>&1
$sshOutput = $sshTest | Out-String

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] SSH connection successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now proceed with deployment." -ForegroundColor Green
} else {
    Write-Host "  [ERROR] SSH connection failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "SSH Error Output:" -ForegroundColor Yellow
    Write-Host $sshOutput -ForegroundColor Gray
    Write-Host ""
    Write-Host "Common Solutions:" -ForegroundColor Yellow
    Write-Host "  1. Check AWS Console - Is the EC2 instance running?" -ForegroundColor White
    Write-Host "  2. Security Group - Add inbound rule for SSH (port 22) from your IP" -ForegroundColor White
    $fixKeyCmd = 'icacls "' + $KEY_PATH + '" /inheritance:r /grant:r "' + $env:USERNAME + ':R"'
    Write-Host ('  3. Key Permissions - Run: ' + $fixKeyCmd) -ForegroundColor White
    $manualCmd = 'ssh -i "' + $KEY_PATH + '" -v ' + $EC2_USER + '@' + $EC2_HOST
    Write-Host '  4. Try manual connection to see detailed error:' -ForegroundColor White
    Write-Host ('     ' + $manualCmd) -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Diagnostic Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
