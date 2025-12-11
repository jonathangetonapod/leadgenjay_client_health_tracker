@echo off
REM Instantly.ai MCP Server Setup Script for Windows
REM This script automates the installation process for team members

echo ==================================================
echo Instantly.ai MCP Server - Setup Script
echo ==================================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment and install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo Dependencies installed
echo.

REM Get paths
set "INSTALL_DIR=%CD%"
set "PYTHON_PATH=%INSTALL_DIR%\venv\Scripts\python.exe"
set "SERVER_PATH=%INSTALL_DIR%\mcp_server.py"
set "CONFIG_FILE=%APPDATA%\Claude\claude_desktop_config.json"

echo ==================================================
echo Configuration
echo ==================================================
echo Install directory: %INSTALL_DIR%
echo Python path: %PYTHON_PATH%
echo Server path: %SERVER_PATH%
echo Config file: %CONFIG_FILE%
echo.

REM Create config directory if it doesn't exist
if not exist "%APPDATA%\Claude\" mkdir "%APPDATA%\Claude"

REM Check if config file exists
if exist "%CONFIG_FILE%" (
    echo WARNING: Config file already exists at:
    echo    %CONFIG_FILE%
    echo.
    echo You need to manually add this MCP server to your config.
    echo.
    echo Add this to the 'mcpServers' section:
    echo.
    echo     "instantly-leads": {
    echo       "command": "%PYTHON_PATH%",
    echo       "args": ["%SERVER_PATH%"]
    echo     }
    echo.
) else (
    echo Creating new config file...
    (
        echo {
        echo   "mcpServers": {
        echo     "instantly-leads": {
        echo       "command": "%PYTHON_PATH%",
        echo       "args": ["%SERVER_PATH%"]
        echo     }
        echo   }
        echo }
    ) > "%CONFIG_FILE%"
    echo Config file created
)

echo.
echo ==================================================
echo Setup Complete!
echo ==================================================
echo.
echo Next steps:
echo 1. Make sure you have access to the Google Sheet
echo 2. Restart Claude Desktop
echo 3. Test it with: 'Show me the client list'
echo.
echo If you see any issues, check INSTALL.md for troubleshooting.
echo.
pause
