@echo off
REM One-click installer for MCP Desktop Visual
REM Run this script to set up everything automatically

echo.
echo ================================================
echo   MCP Desktop Visual - Quick Setup
echo ================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo       Created .venv
) else (
    echo       .venv already exists
)

echo.
echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [3/4] Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install -e . -q
echo       Dependencies installed

echo.
echo [4/5] Checking Tesseract OCR...
where tesseract >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo       Tesseract found at C:\Program Files\Tesseract-OCR\tesseract.exe
    ) else (
        echo       Tesseract not found - installing via winget...
        winget install --id tesseract-ocr.tesseract -e --accept-package-agreements --accept-source-agreements --silent
        if errorlevel 1 (
            echo       WARNING: Could not install Tesseract automatically
            echo       Please install manually: https://github.com/UB-Mannheim/tesseract/wiki
        ) else (
            echo       Tesseract installed successfully!
        )
    )
) else (
    echo       Tesseract found in PATH
)

echo.
echo [5/5] Running tests...
python test_mcp.py

echo.
echo ================================================
echo   Setup Complete!
echo ================================================
echo.
echo The MCP server is now ready to use.
echo.
echo To use in VS Code:
echo   1. Open this folder in VS Code
echo   2. The 'desktop-visual' MCP server is configured in .vscode/mcp.json
echo   3. Start using the desktop visual tools!
echo.
echo To run the server manually:
echo   .venv\Scripts\python.exe -m mcp_desktop_visual.server
echo.
pause
