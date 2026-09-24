@echo off
setlocal

set "PROJECT_DIR=%~dp0sharedspend"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"
set "BACKEND_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "FRONTEND_VITE=%FRONTEND_DIR%\node_modules\.bin\vite.cmd"

if not exist "%BACKEND_DIR%\app\main.py" (
    echo Backend files not found at "%BACKEND_DIR%".
    pause
    exit /b 1
)
if not exist "%BACKEND_PYTHON%" (
    echo Backend Python environment not found at "%BACKEND_PYTHON%".
    echo Create it with: cd sharedspend\backend ^&^& python -m venv .venv
    pause
    exit /b 1
)
if not exist "%FRONTEND_DIR%\package.json" (
    echo Frontend files not found at "%FRONTEND_DIR%".
    pause
    exit /b 1
)
if not exist "%FRONTEND_VITE%" (
    echo Frontend dependencies not found. Run npm install in "%FRONTEND_DIR%" first.
    pause
    exit /b 1
)

echo Starting SharedSpend Backend...
start "SharedSpend Backend" /D "%BACKEND_DIR%" "%BACKEND_PYTHON%" -m uvicorn app.main:app --reload --port 8000

echo Starting SharedSpend Frontend...
start "SharedSpend Frontend" /D "%FRONTEND_DIR%" cmd /k call "%FRONTEND_VITE%"

echo.
echo ========================================
echo SharedSpend is starting...
echo ========================================
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo ========================================

pause
