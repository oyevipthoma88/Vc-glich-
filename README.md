# VC Glich Bot

Telegram bot: fetch SFU server IPs of active group VCs, owner approval, MongoDB storage, colored inline buttons.

## Deploy to Heroku

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/oyevipthoma88/Vc-glich-)

## Required Config Vars

| Var | Description |
|---|---|
| `API_ID` | From my.telegram.org |
| `API_HASH` | From my.telegram.org |
| `BOT_TOKEN` | From @BotFather |
| `OWNER_IDS` | Comma-separated numeric IDs |
| `MONGO_URI` | MongoDB Atlas URI (optional) |
| `TG_SESSION` | Telethon StringSession (optional if using /login) |

## Features

- Colored inline buttons (primary / success / danger)
- Owner approval with atomic MongoDB updates
- Login flow: phone → OTP → 2FA → session saved to MongoDB
- VC SFU IP fetch with cooldown + validation
- Pagination for pending/approved lists
- `/health`, `/stats`, `/broadcast` owner commands

## Commands

- `/start` — menu / request access
- `/health` — userbot status
- `/stats` — approval stats
- `/broadcast <text>` — message all approved users
- `/pending`, `/approved`, `/revoke <id>` — owner tools
