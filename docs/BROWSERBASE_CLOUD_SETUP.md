# Browserbase Cloud Setup

Stagehand runs browser tasks in the cloud with your Chrome credentials.

## One-Time Setup

```bash
# From project root
./scripts/setup_browserbase_cloud.sh
```

Or manually:
1. `python3 scripts/create_browserbase_context.py` — creates context (only needed once)
2. `python3 sync_chrome_to_browserbase.py` — copies Chrome cookies to the context

## Required .env

```env
STAGEHAND_USE_BROWSERBASE=true
BROWSERBASE_API_KEY=your-key
BROWSERBASE_PROJECT_ID=your-project-id
MODEL_API_KEY=your-openai-or-anthropic-key
```

## Re-Sync Cookies

Run periodically or after logging into new sites:

```bash
python3 sync_chrome_to_browserbase.py
```

## How It Works

- **Context** — persistent storage for cookies, cache, and session data
- **Sync** — copies cookies from your Chrome (Default + Profile 1/2/3) into the context
- **Stagehand** — every browser task uses this context, so you stay logged in

## Status

```bash
curl http://127.0.0.1:5005/api/status
```

Returns `context_configured: true` when ready.

## Reliable flow (context persistence)

- All session creates use `browserSettings.context` with `persist: true`.
- After sync or sign-in scripts end a session, they wait ~8s so Browserbase can sync the context.
- If a task hits a login page: open the **Live View** link from the reply, log in there, then future tasks use that context.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No context | Run `setup_browserbase_cloud.sh` |
| Logins not persisting | Re-run `sync_chrome_to_browserbase.py`; wait ~10s before next task |
| Chrome locked | Close Chrome before sync (or sync while closed for cleanest copy) |
| Sites need re-login | Open the Live View link, log in manually; session is persisted |
