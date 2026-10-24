# Discord Bot Not Receiving Messages? Fix Here

## Error: "Privileged intents have not been explicitly enabled"

Your Discord bot **cannot read messages** until you enable the **Message Content Intent** in the Developer Portal.

### Steps (takes ~1 minute)

1. Go to **[Discord Developer Portal](https://discord.com/developers/applications/)**
2. Click your application (the one whose token you use)
3. Click **Bot** in the left sidebar
4. Scroll down to **Privileged Gateway Intents**
5. Turn **ON** the switch for **Message Content Intent**
6. Click **Save Changes**
7. **Restart the message bridge** (close the window and run `.\run_windows.ps1` again, or run `.\scripts\run_message_bridge_debug.ps1` to see logs)

![Location: Bot → Privileged Gateway Intents → Message Content Intent = ON]

After this, when you DM the bot or message in a channel, the bot will receive your messages and forward them to your PC.
