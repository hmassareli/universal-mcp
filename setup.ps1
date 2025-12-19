<#
.SYNOPSIS
    Setup script for MCP Desktop Visual

.DESCRIPTION
    This script sets up the MCP Desktop Visual server including:
    - Creating virtual environment
    - Installing dependencies
    - Checking for Tesseract OCR
    - Generating VS Code configuration

.EXAMPLE
    .\setup.ps1
#>

param(
    [switch]$SkipVenv,
    [switch]$SkipTesseractCheck,
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "🖥️  MCP Desktop Visual Setup" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Gray

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check Python
Write-Host "`n📌 Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = & $PythonPath --version 2>&1
    Write-Host "   Found: $pythonVersion" -ForegroundColor Green
    
    # Check version
    $version = [regex]::Match($pythonVersion, '(\d+)\.(\d+)').Groups
    $major = [int]$version[1].Value
    $minor = [int]$version[2].Value
    
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Write-Host "   ⚠️  Python 3.10+ is required, found $major.$minor" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   ❌ Python not found. Please install Python 3.10+" -ForegroundColor Red
    Write-Host "   Download: https://www.python.org/downloads/" -ForegroundColor Gray
    exit 1
}

# Create virtual environment
if (-not $SkipVenv) {
    Write-Host "`n📌 Creating virtual environment..." -ForegroundColor Yellow
    
    if (Test-Path ".venv") {
        Write-Host "   Virtual environment already exists, skipping..." -ForegroundColor Gray
    } else {
        & $PythonPath -m venv .venv
        Write-Host "   Created .venv" -ForegroundColor Green
    }
    
    # Activate venv
    $venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    $PythonPath = $venvPython
    
    Write-Host "   Using: $PythonPath" -ForegroundColor Gray
}

# Install dependencies
Write-Host "`n📌 Installing dependencies..." -ForegroundColor Yellow
& $PythonPath -m pip install --upgrade pip -q
& $PythonPath -m pip install -e . -q
Write-Host "   Dependencies installed" -ForegroundColor Green

# Check Tesseract
if (-not $SkipTesseractCheck) {
    Write-Host "`n📌 Checking Tesseract OCR..." -ForegroundColor Yellow
    
    $tesseractPaths = @(
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe"
    )
    
    $tesseractFound = $false
    $tesseractPath = ""
    
    # Check common paths
    foreach ($path in $tesseractPaths) {
        if (Test-Path $path) {
            $tesseractPath = $path
            $tesseractFound = $true
            break
        }
    }
    
    # Check PATH
    if (-not $tesseractFound) {
        try {
            $tesseractVersion = & tesseract --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $tesseractFound = $true
                $tesseractPath = "tesseract"
            }
        } catch {}
    }
    
    if ($tesseractFound) {
        Write-Host "   Found: $tesseractPath" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Tesseract not found - installing via winget..." -ForegroundColor Yellow
        
        try {
            winget install --id tesseract-ocr.tesseract -e --accept-package-agreements --accept-source-agreements --silent
            if ($LASTEXITCODE -eq 0) {
                $tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
                $tesseractFound = $true
                Write-Host "   ✅ Tesseract installed successfully!" -ForegroundColor Green
            } else {
                Write-Host "   ❌ Failed to install Tesseract via winget" -ForegroundColor Red
                Write-Host "   Please install manually: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Gray
            }
        } catch {
            Write-Host "   ❌ winget not available, please install Tesseract manually" -ForegroundColor Red
            Write-Host "   Download: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Gray
        }
    }
}

# Create VS Code configuration
Write-Host "`n📌 Creating VS Code configuration..." -ForegroundColor Yellow

$vscodeDir = Join-Path $ScriptDir ".vscode"
if (-not (Test-Path $vscodeDir)) {
    New-Item -ItemType Directory -Path $vscodeDir | Out-Null
}

# MCP configuration
$mcpConfig = @{
    servers = @{
        "desktop-visual" = @{
            command = (Join-Path $ScriptDir ".venv\Scripts\python.exe").Replace("\", "/")
            args = @("-m", "mcp_desktop_visual.server")
        }
    }
} | ConvertTo-Json -Depth 10

$mcpConfigPath = Join-Path $vscodeDir "mcp.json"
$mcpConfig | Out-File -FilePath $mcpConfigPath -Encoding utf8
Write-Host "   Created .vscode/mcp.json" -ForegroundColor Green

# Create default config file
Write-Host "`n📌 Creating default configuration..." -ForegroundColor Yellow

$defaultConfig = @{
    capture = @{
        diff_threshold = 30
        min_region_area = 100
        capture_interval = 0.5
    }
    ocr = @{
        tesseract_path = if ($tesseractPath) { $tesseractPath.Replace("\", "/") } else { $null }
        language = "eng"
        confidence_threshold = 60
    }
    input = @{
        click_delay = 0.1
        typing_delay = 0.02
        failsafe = $true
    }
    cache = @{
        max_elements = 1000
        max_history = 10
    }
} | ConvertTo-Json -Depth 10

$configPath = Join-Path $ScriptDir "mcp-desktop-config.json"
$defaultConfig | Out-File -FilePath $configPath -Encoding utf8
Write-Host "   Created mcp-desktop-config.json" -ForegroundColor Green

# Done!
Write-Host "`n✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Open VS Code in this folder" -ForegroundColor White
Write-Host "   2. The MCP server will be available as 'desktop-visual'" -ForegroundColor White
Write-Host "   3. Start using the desktop visual tools!" -ForegroundColor White
Write-Host ""

if (-not $tesseractFound) {
    Write-Host "⚠️  Optional: Install Tesseract OCR for text recognition" -ForegroundColor Yellow
    Write-Host "   https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "🚀 To test the server manually:" -ForegroundColor Cyan
Write-Host "   .venv\Scripts\python.exe -m mcp_desktop_visual.server" -ForegroundColor Gray
