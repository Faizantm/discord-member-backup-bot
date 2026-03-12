# free-members-discord-bot

A Discord bot for member backup and restoration using stored OAuth tokens. Built with discord.py and Flask.

## ⭐ Key Features

- **24/7 Keep-Alive** - Built-in Flask web server keeps bot running even when tab is closed
- **Beautiful OAuth2 UI** - Custom redirect page for authentication
- **Token Management** - Automatic token refresh and storage
- **Mass User Join** - Add authenticated users to Discord servers
- **Token Validation** - Check validity of stored tokens

## Architecture

### Workflows (2 running)

1. **Start application** (Main bot with keep-alive)
   - Runs `python bot.py`
   - Discord bot + Flask keep-alive server on port 8080
   - Accepts all Discord commands
   - Keeps running 24/7 on Replit

2. **Discord Redirect Server** (OAuth2 UI)
   - Runs `python redirect_app.py`
   - Beautiful authentication page on port 5000
   - Displays auth codes with copy button

### Files

- `bot.py` - Discord bot + Flask keep-alive server
- `redirect_app.py` - OAuth2 redirect handler
- `config.json` - Discord bot credentials
- `auths.txt` - User OAuth tokens
- `requirements.txt` - Dependencies

## How It Works

### Keep-Alive System

The bot includes a built-in Flask web server that:
- Runs on port 8080 in a background thread
- Responds to HTTP requests: `GET /` returns "🤖 Member Backup Bot is alive and running!"
- Keeps the process alive even when you close the Replit tab
- No external hosting needed - **runs 24/7 on Replit**

### Authentication Flow

1. User: `!get_token` → Gets OAuth link
2. User: Clicks link and authorizes on Discord
3. Discord: Redirects to your redirect server
4. Page: Shows auth code (30 characters exactly)
5. User: `!auth CODE` → Exchanges code for tokens
6. Bot: Saves tokens to `auths.txt`

### Command Format

- Authorization codes must be **exactly 30 characters long**
- Example: `!auth eyJhbGciOiJSUzI1NiIsInR5cCI`

## Setup

1. Fill in `config.json`:
   ```json
   {
     "token": "YOUR_BOT_TOKEN",
     "id": "YOUR_CLIENT_ID",
     "secret": "YOUR_CLIENT_SECRET"
   }
   ```

2. Register OAuth redirect in Discord Developer Portal:
   - Add: `https://[YOUR_REPLIT_DOMAIN]/discord-redirect.html`

## Bot Commands

| Command | Description |
|---|---|
| `!get_token` | Get OAuth authorization link |
| `!auth CODE` | Authenticate with 30-char code |
| `!djoin SERVER_ID` | Add all users to server |
| `!check_tokens` | Check token validity |
| `!list_users` | List authenticated users |
| `!count` | Show user count |
| `!servers` | List bot's servers |

## Running Locally

```bash
pip install -r requirements.txt
python bot.py
```

The bot will:
- Start Discord connection
- Start Flask keep-alive on port 8080
- Listen for commands indefinitely

## Deployment Options

### Option 1: Replit (Current)
- ✅ 24/7 running with keep-alive
- ✅ No external hosting needed
- ✅ Free tier available

### Option 2: Render or Similar
- Migrate `bot.py` to their platform
- Flask keep-alive still works
- Different port configuration

## Dependencies

```
discord.py>=2.3.0
requests>=2.31.0
aiohttp>=3.8.0
flask>=2.3.0
```

## Keep-Alive Technology

The bot uses Python's `threading.Thread` to run Flask and discord.py concurrently:
- Discord bot runs in main thread (blocking event loop)
- Flask server runs in daemon thread (background)
- Both share the same Python process
- HTTP requests to port 8080 prove the bot is alive
- Replit detects activity and keeps the process running

This ensures the bot **never goes to sleep** on Replit!
