# WhatsApp: Message Your Windows PC from Your Phone

Control your PC by sending WhatsApp messages from your phone. Only **your** messages are processed.

---

## Flow

1. You send a WhatsApp message to the Twilio number
2. Twilio forwards it to your PC (via ngrok webhook)
3. The message bridge delivers it to the backend
4. Backend routes to **Stagehand** (browser tasks) or **Agent-S** (desktop tasks)
5. Your PC performs the action
6. Reply is sent back to your WhatsApp (when supported)

---

## Step 1: Twilio Account

1. Go to [twilio.com](https://www.twilio.com) and sign up
2. In **Console** → copy your **Account SID** and **Auth Token**
3. Go to **Messaging** → **Try it out** → **Send a WhatsApp message**
4. Note the **sandbox number** (e.g. `+14155238886`) and **join code** (e.g. `join happy-tiger`)

---

## Step 2: Join the Sandbox

1. Open WhatsApp on your phone
2. Add the sandbox number as a contact (e.g. `+1 415 523 8886`)
3. Send the join code (e.g. `join happy-tiger`) to that number
4. You should get a confirmation

---

## Step 3: ngrok (Public URL for Webhook)

Twilio needs a public URL to send messages to your PC. Use ngrok:

1. Install ngrok: [ngrok.com/download](https://ngrok.com/download)
2. Run:
   ```powershell
   ngrok http 8100
   ```
3. Copy the **HTTPS** URL (e.g. `https://abc123.ngrok-free.app`)

---

## Step 4: Configure Twilio Webhook

1. In Twilio Console → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Under **Sandbox settings** → **When a message comes in**
3. Set URL to: `https://YOUR-NGROK-URL/webhooks/whatsapp`
   - Example: `https://abc123.ngrok-free.app/webhooks/whatsapp`
4. Method: **POST**
5. Save

---

## Step 5: .env Configuration

Add to `Treehacks/.env`:

```env
# Use WhatsApp only (or add discord,slack for multiple)
MESSAGE_SOURCES=whatsapp

# Twilio credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# YOUR phone number (with country code) - only your messages are processed
ALLOWED_WHATSAPP_PHONE=+15555550100
```

Replace with your actual values.

---

## Step 6: Install WhatsApp Dependency

```powershell
cd Treehacks\backend
uv add ".[whatsapp]"
```

---

## Step 7: Run Everything

**Terminal 1 – ngrok** (must stay running):
```powershell
ngrok http 8100
```

**Terminal 2 – Full stack**:
```powershell
cd Treehacks
.\run_windows.ps1
```

Or start services manually:
- Windows message bridge (port 8100)
- Backend (port 8003)
- Agent-S (port 8001)
- Stagehand (port 5005)

---

## Step 8: Test

1. Open WhatsApp on your phone
2. Message the Twilio sandbox number (the one you joined)
3. Send: **Open Notepad**
4. Your PC should open Notepad and type "Hello from Shadow-OS"

Other examples:
- **Open Chrome and search Sakshi Tripathy on Google**
- **Open Calculator**

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No response | Ensure ngrok is running and webhook URL is correct |
| "No message sources" | Set `MESSAGE_SOURCES=whatsapp` and Twilio credentials |
| Messages ignored | Check `ALLOWED_WHATSAPP_PHONE` matches your number exactly (with + and country code) |
| 401 from Twilio | Verify Account SID and Auth Token |
| ngrok URL changed | Update the webhook URL in Twilio (free ngrok URLs change on restart) |

---

## Production (Optional)

For a permanent WhatsApp number (no sandbox):

1. Apply for Twilio WhatsApp Business API
2. Use the same webhook URL
3. Update `TWILIO_WHATSAPP_NUMBER` to your approved number
