@echo off
echo ========================================
echo  FaithForge AI Contract Screener
echo ========================================

:: Check for .env
if not exist "backend\.env" (
    echo ERROR: backend\.env not found.
    echo Copy .env.example to backend\.env and fill in your values.
    pause
    exit /b 1
)

:: Start backend
echo Starting backend (FastAPI)...
start "FaithForge Backend" cmd /k "cd backend && pip install -r requirements.txt -q && python -m uvicorn main:app --reload --port 8000"

:: Wait for backend to start
timeout /t 4 /nobreak >nul

:: Start frontend
echo Starting frontend (React/Vite)...
start "FaithForge Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo.
echo ========================================
echo  App starting at http://localhost:5173
echo  API running at  http://localhost:8000
echo ========================================
echo.
echo Press any key to exit this window (servers continue in background)
pause
