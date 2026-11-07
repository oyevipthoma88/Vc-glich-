# VC Glich Bot

Telegram bot for fetching SFU server IPs of active group voice chats.
Features: owner approval, MongoDB storage, colored inline buttons.

## Deploy to Heroku

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/oyevipthoma88/Vc-glich-)

> Deploy button reference karna zaroori hai — hataya toh button kaam nahi karega.
> Agar button bhi nahi chahiye, is file se us line ko delete kar sakte ho.

## Required Config Vars

| Var | Description |
|---|---|
| `API_ID` | From my.telegram.org |
| `API_HASH` | From my.telegram.org |
| `BOT_TOKEN` | From @BotFather |
| `OWNER_IDS` | Comma-separated numeric IDs |
| `TG_SESSION` | Telethon StringSession (>=1.43 required for colored buttons) |
| `MONGO_URI` | MongoDB Atlas URI (optional) |

## Colored Buttons — Version Requirement

Colored inline buttons need **Telethon >= 1.43.2** (Bot API 9.4 `style` field).
`requirements.txt` already pins this.

## Commands

- `/start` — menu / request access
- `/health` — userbot status
- `/stats` — approval stats
- `/broadcast <text>` — message all approved users
- `/pending`, `/approved`, `/revoke <id>` — owner tools
