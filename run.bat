@echo off
REM Run script for Discord Chat Bot (Windows)

echo 🤖 Starting Discord Chat Bot...

REM Check if .env exists
if not exist .env (
    echo ❌ .env file not found!
    echo 📝 Copy .env.example to .env and configure it:
    echo    copy .env.example .env
    echo    REM Then edit .env with your values
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist venv (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/update dependencies
echo 📥 Installing dependencies...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

REM Run the bot
echo 🚀 Starting bot...
python bot.py

pause