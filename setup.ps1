Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  LiteLLM Enterprise Setup" -ForegroundColor Cyan
Write-Host "  Anthropic + Grok (xAI) + Redis Cache" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

$REPO_RAW = "https://raw.githubusercontent.com/doron-stack/litellm-enterprise/main"
$INSTALL_DIR = "$env:USERPROFILE\Desktop\litellm-enterprise"

# Step 1: Create directory
Write-Host "[1/5] Setting up directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
Write-Host "      [OK] $INSTALL_DIR" -ForegroundColor Green

# Step 2: Download all files
Write-Host "[2/5] Downloading from GitHub..." -ForegroundColor Yellow
$files = @("docker-compose.yml", "config.yaml", "prometheus.yml", "README.md", "admin.html")
foreach ($file in $files) {
    try {
        Invoke-WebRequest -Uri "$REPO_RAW/$file" -OutFile "$INSTALL_DIR\$file" -UseBasicParsing -ErrorAction Stop
        Write-Host "      [OK] $file" -ForegroundColor Green
    } catch {
        Write-Host ("      [FAIL] {0}" -f $file) -ForegroundColor Red
        pause; exit 1
    }
}

# Step 3: API keys - prompt once, save to .env, never ask again
Write-Host "[3/5] Configuring API keys..." -ForegroundColor Yellow
$envFile = "$INSTALL_DIR\.env"

if (Test-Path $envFile) {
    $existingEnv = Get-Content $envFile -Raw
    $hasAnthropic = $existingEnv -match "ANTHROPIC_API_KEY=\S+"
    $hasXai = $existingEnv -match "XAI_API_KEY=\S+"
} else {
    $hasAnthropic = $false
    $hasXai = $false
}

if ($hasAnthropic -and $hasXai) {
    Write-Host "      [OK] Keys already configured - skipping" -ForegroundColor Green
    # Extract existing keys and set as Windows env vars
    if ($existingEnv -match 'ANTHROPIC_API_KEY=(\S+)') {
        [System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $Matches[1], "User")
    }
    if ($existingEnv -match 'XAI_API_KEY=(\S+)') {
        [System.Environment]::SetEnvironmentVariable("XAI_API_KEY", $Matches[1], "User")
    }
    Write-Host "      [OK] Keys set as Windows environment variables" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  Enter your API keys below (one time only - saved to .env)" -ForegroundColor White
    Write-Host ""

    if (-not $hasAnthropic) {
        $anthropicKey = Read-Host "  Anthropic API key (sk-ant-...)"
    } else {
        $anthropicKey = ""
    }

    if (-not $hasXai) {
        $xaiKey = Read-Host "  Grok/xAI API key (xai-...)"
    } else {
        $xaiKey = ""
    }

    # Build .env
    $envContent = @"
MASTER_KEY=sk-9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e
POSTGRES_PASSWORD=litellm
REDIS_PASSWORD=litellm
GRAFANA_ADMIN_PASSWORD=adminchangeinproduction
UI_USERNAME=admin
UI_PASSWORD=admin123
ANTHROPIC_API_KEY=$anthropicKey
XAI_API_KEY=$xaiKey
"@
    Set-Content -Path $envFile -Value $envContent -Encoding UTF8
    Write-Host "      [OK] Keys saved to .env" -ForegroundColor Green

    # Set as Windows environment variables so Claude Code and all tools auto-detect them
    if ($anthropicKey) {
        [System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $anthropicKey, "User")
    }
    if ($xaiKey) {
        [System.Environment]::SetEnvironmentVariable("XAI_API_KEY", $xaiKey, "User")
    }
    Write-Host "      [OK] Keys set as Windows environment variables" -ForegroundColor Green
}

# Step 4: Docker check and start
Write-Host "[4/5] Starting Docker containers..." -ForegroundColor Yellow
$dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCheck) {
    Write-Host "  [ERROR] Docker not found. Install Docker Desktop first." -ForegroundColor Red
    Write-Host "  https://docker.com/products/docker-desktop" -ForegroundColor Yellow
    pause; exit 1
}

Set-Location $INSTALL_DIR
docker compose up -d --pull always 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }

# Step 5: Verify
Write-Host "[5/5] Verifying services..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
docker compose ps 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Admin Dashboard: $INSTALL_DIR\admin.html" -ForegroundColor White
Write-Host "  (double-click to open)" -ForegroundColor Gray
Write-Host ""
Write-Host "  LiteLLM Admin UI:  http://localhost:4000/ui" -ForegroundColor White
Write-Host "    Username: admin | Password: admin123" -ForegroundColor Gray
Write-Host ""
Write-Host "  Prometheus:        http://localhost:9090" -ForegroundColor White
Write-Host "  Grafana:           http://localhost:3100" -ForegroundColor White
Write-Host "    Username: admin | Password: adminchangeinproduction" -ForegroundColor Gray
Write-Host ""
Write-Host "  Models pre-configured:" -ForegroundColor Yellow
Write-Host "    claude-sonnet-4, claude-opus-4, claude-haiku-3-5" -ForegroundColor Gray
Write-Host "    grok-3, grok-3-mini" -ForegroundColor Gray
Write-Host ""
Write-Host "  Use from any code:" -ForegroundColor Yellow
Write-Host "    base_url = http://localhost:4000" -ForegroundColor Gray
Write-Host "    api_key  = sk-9f8e7d6c5b...  (your MASTER_KEY)" -ForegroundColor Gray
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Open admin dashboard
Start-Process "$INSTALL_DIR\admin.html"

pause
