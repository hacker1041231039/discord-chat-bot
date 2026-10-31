#!/bin/bash
# Run script for Discord Chat Bot

set -e

echo "🤖 Starting Discord Chat Bot..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "📝 Copy .env.example to .env and configure it:"
    echo "   cp .env.example .env"
    echo "   # Then edit .env with your values"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run the bot
echo "🚀 Starting bot..."
python bot.py