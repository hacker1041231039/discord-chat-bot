# Discord Chat Bot

A feature-rich, production-ready Discord chat bot built with Python and discord.py. Supports both slash commands and prefix commands, automatic responses to mentions/DMs, conversation history, rate limiting, and integration with any OpenAI-compatible LLM API.

## Features

- **Dual Command System**: Both slash commands (`/`) and prefix commands (`!`)
- **Auto-Response**: Responds to mentions and DMs automatically
- **Conversation Memory**: Maintains context per channel/user
- **Rate Limiting**: Token bucket algorithm per user
- **LLM Integration**: Works with OpenRouter, Together.ai, Groq, OpenAI, etc.
- **Admin Commands**: Message management, cog reloading, command syncing
- **Structured Logging**: Loguru with file rotation
- **Type Safety**: Pydantic settings validation
- **Error Handling**: Comprehensive error handling with user-friendly messages

## Quick Start

### Prerequisites

- Python 3.10+
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- LLM API Key (OpenRouter, Together.ai, Groq, etc.)

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd discord-chat-bot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate   # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

5. **Run the bot:**
   ```bash
   python bot.py
   ```

## Configuration

### Required Settings (`.env`)

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Your Discord bot token |
| `DISCORD_APPLICATION_ID` | Your Discord application ID |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_GUILD_ID` | None | Guild ID for instant command sync (dev) |
| `COMMAND_PREFIX` | `!` | Prefix for text commands |
| `BOT_STATUS` | `Chatting with users \| /help` | Bot presence message |
| `LLM_API_URL` | `https://api.example.com/v1/chat/completions` | LLM API endpoint |
| `LLM_API_KEY` | None | LLM API key |
| `LLM_MODEL` | `meta-llama/llama-3-8b-instruct` | Model name |
| `LLM_MAX_TOKENS` | `2000` | Max tokens per response |
| `LLM_TEMPERATURE` | `0.7` | Temperature (0-2) |
| `LLM_SYSTEM_PROMPT` | See .env.example | System prompt for AI |
| `RATE_LIMIT_PER_USER` | `30` | Messages per minute per user |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `logs/bot.log` | Log file path |

### LLM Provider Examples

**OpenRouter (Free tier available):**
```env
LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
LLM_API_KEY=sk-or-v1-xxxxx
LLM_MODEL=meta-llama/llama-3-8b-instruct:free
```

**Together.ai:**
```env
LLM_API_URL=https://api.together.xyz/v1/chat/completions
LLM_API_KEY=xxxxx
LLM_MODEL=meta-llama/Llama-3-8b-chat-hf
```

**Groq (Fast, free):**
```env
LLM_API_URL=https://api.groq.com/openai/v1/chat/completions
LLM_API_KEY=gsk_xxxxx
LLM_MODEL=llama3-8b-8192
```

**Local (Ollama):**
```env
LLM_API_URL=http://localhost:11434/v1/chat/completions
LLM_API_KEY=ollama
LLM_MODEL=llama3
```

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to **Bot** tab → Create bot
4. Copy **Token** → `DISCORD_TOKEN`
5. Copy **Application ID** → `DISCORD_APPLICATION_ID`
6. Enable **Message Content Intent** and **Server Members Intent**
7. Go to **OAuth2** → **URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Add Reactions`, `Use External Emojis`, `Manage Messages`
8. Use generated URL to invite bot to your server

## Commands

### General Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/ping` / `!ping` | - | Check bot latency |
| `/help` / `!help` | - | Show help message |
| `/info` / `!info` | `!botinfo`, `!bi` | Show bot information |
| `/invite` / `!invite` | - | Get bot invite link |
| `/rate` / `!rate` | - | Check rate limit status |
| `/uptime` / `!uptime` | - | Show bot uptime |

### LLM Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/chat` / `!chat` | `!ask`, `!ai` | Chat with the AI |
| `/model` / `!model` | - | Show/change LLM model (owner) |
| `/systemprompt` / `!systemprompt` | `!sp` | Show/set system prompt (owner) |
| `/temperature` / `!temperature` | `!temp` | Show/set temperature (owner) |
| `/llmhealth` / `!llmhealth` | `!llmstatus` | Check LLM API health |
| `/personality` / `!personality` | `!persona` | Set AI personality for conversation |

### Admin Commands (Owner/Moderator)

| Command | Aliases | Permission | Description |
|---------|---------|------------|-------------|
| `/clear` / `!clear` | `!purge` | Manage Messages | Clear messages in channel |
| `/reload` / `!reload` | - | Bot Owner | Reload a cog |
| `/sync` / `!sync` | - | Bot Owner | Sync slash commands |
| `/clearhistory` / `!clearhistory` | `!ch` | Any | Clear conversation history |
| `/ratelimit` / `!ratelimit` | `!rl` | Bot Owner | Manage rate limits |
| `/shutdown` / `!shutdown` | - | Bot Owner | Shutdown the bot |

## Auto-Response Behavior

The bot automatically responds to:
- **Mentions**: `@BotName hello`
- **DMs**: Direct messages to the bot
- **Replies**: Replying to bot's messages

The bot does **not** respond to every message in a server to avoid spam.

## Project Structure

```
discord-chat-bot/
├── bot.py                 # Main bot entry point
├── config.py              # Configuration management
├── logging_config.py      # Logging setup
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── commands/              # Command modules (cogs)
│   ├── __init__.py
│   ├── general.py         # General commands
│   ├── admin.py           # Admin commands
│   └── llm.py             # LLM commands
├── services/
│   ├── __init__.py
│   └── llm_service.py     # LLM API integration
└── utils/
    ├── __init__.py
    ├── rate_limiter.py    # Rate limiting
    └── conversation.py    # Conversation history
```

## Development

### Adding New Commands

1. Create a new cog in `commands/` or add to existing
2. Use `@commands.command()` for prefix commands
3. Use `@app_commands.command()` for slash commands
4. Add cog to `bot.py` in `_load_cogs()`

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run tests
pytest
```

### Code Quality

```bash
# Format code
pip install black isort
black .
isort .

# Type check
pip install mypy
mypy .
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t discord-chat-bot .
docker run -d --env-file .env discord-chat-bot
```

### Systemd Service (Linux)

```ini
# /etc/systemd/system/discord-bot.service
[Unit]
Description=Discord Chat Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/discord-chat-bot
ExecStart=/opt/discord-chat-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=/opt/discord-chat-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
```

## Security Considerations

- Never commit `.env` file
- Use strong API keys
- Enable rate limiting
- Restrict admin commands to owner
- Keep dependencies updated
- Monitor logs for suspicious activity

## Troubleshooting

### Bot doesn't respond to commands
- Check bot has `Message Content Intent` enabled
- Verify bot has permissions in channel
- Check logs for errors

### Slash commands not appearing
- Wait up to 1 hour for global sync
- Use `/sync` command (owner only) for instant guild sync
- Verify `applications.commands` scope in invite

### LLM API errors
- Verify API key and endpoint
- Check rate limits on provider side
- Check logs for detailed error messages

### High memory usage
- Reduce `max_history_per_channel` in `conversation.py`
- Enable log rotation (already configured)

## License

MIT License - Feel free to use and modify.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Support

For issues and questions, please open a GitHub issue.