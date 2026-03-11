@echo off
echo =========================================
echo Starting Intelli-Credit Application Stack
echo =========================================

echo Starting Frontend...
start "Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo Starting Backend...
start "Backend (Node API)" cmd /k "cd backend && npm run dev"

echo Starting AI Service...
start "AI Service (FastAPI)" cmd /k "cd ai-service && uvicorn main:app --reload --port 8000"

echo Starting Go Service...
start "Go Service" cmd /k "cd go-service && go run main.go"

echo.
echo All 4 services have been launched in separate terminal windows!
echo Their individual logs will be visible in those windows.
echo Please ensure your conda environment or virtual environment for python/uvicorn is active if needed.
