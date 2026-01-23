@echo off
echo 🚀 Activating virtual environment...
call venv\Scripts\activate

echo 🧠 Starting FastAPI server...
start cmd /k "uvicorn mira.api.main:app --reload"

timeout /t 5 >nul

echo 🌍 Starting ngrok tunnel...
start cmd /k "ngrok http --host-header=localhost 8000"
