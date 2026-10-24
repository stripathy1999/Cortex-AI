# Discord & Slack: Message Your PC (Same as WhatsApp)

Discord and Slack work **identically** to WhatsApp: when you send a message, the agent reads it and performs the action (Open Notepad, search Google, etc.). Only **your** messages are processed.

---

## Discord Setup

### 1. Create a Discord bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it (e.g. "Shadow-OS")
2. Go to **Bot** → **Add Bot** → copy the **Token** → paste as `DISCORD_BOT_TOKEN` in `.env`
3. **CRITICAL – Enable Message Content Intent:**
   - In **Bot** settings, scroll to **Privileged Gateway Intents**
   - Turn **ON**: **Message Content Intent** (required for the bot to read your messages)
   - Turn **ON**: **Server Members Intent** (optional, for some features)
   - Click **Save Changes**
4. Go to **OAuth2** → **URL Generator**:
   - Scopes: `bot`
   - Bot permissions: `Send Messages`, `Read Message History`, `View Channels`
4. Copy the generated URL and open it in a browser → invite the bot to a server (or use DMs)

### 2. Get your Discord User ID

1. Discord Settings → **Advanced** → enable **Developer Mode**
2. Right-click your avatar (or username) → **Copy User ID**
3. Paste as `ALLOWED_DISCORD_USER_ID` in `.env`

### 3. Add to `.env`

```env
MESSAGE_SOURCES=discord,slack,whatsapp
DISCORD_BOT_TOKEN=your-bot-token-here
ALLOWED_DISCORD_USER_ID=your-user-id-here
```

### 4. Test

- **DM the bot** – Open Discord → find your bot in DMs → send: `Open Notepad`
- **Or** message in a channel where the bot is present

**No ngrok needed** – Discord uses a long-polling connection, not webhooks.

---

## Slack Setup

### 1. Create a Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. "Shadow-OS") and pick a workspace

### 2. Enable Socket Mode (no ngrok)

1. **Socket Mode** → enable → create **App-Level Token** with `connections:write` → copy it
2. Add as `SLACK_APP_TOKEN` in `.env` (starts with `xapp-`)

### 3. Add Bot Token

1. **OAuth & Permissions** → add scopes: `chat:write`, `channels:history`, `im:history`, `groups:history`
2. **Install to Workspace** → copy the **Bot User OAuth Token**
3. Add as `SLACK_BOT_TOKEN` in `.env` (starts with `xoxb-`)

### 4. Get your Slack User ID

1. In Slack, click your profile → **Profile** → **More** → **Copy member ID**
2. Add as `ALLOWED_SLACK_USER_ID` in `.env` (starts with `U`)

### 5. Add to `.env`

```env
MESSAGE_SOURCES=discord,slack,whatsapp
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
ALLOWED_SLACK_USER_ID=U01234567
```

### 6. Test

- **DM the app** – In Slack, find your app under Apps → send: `Open Notepad`
- **Or** message in a channel where the app is added

**No ngrok needed** – Slack Socket Mode connects outbound.

---

## Summary

| Platform | ngrok? | Setup |
|----------|--------|-------|
| **WhatsApp** | Yes | Twilio + webhook |
| **Discord** | No | Bot token + your user ID |
| **Slack** | No | Bot token + App token + your user ID |

All three deliver to the same backend. The agent doesn’t care which app you use – it reads the text and runs the task.
