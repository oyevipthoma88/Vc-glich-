import os, html
from datetime import datetime
from telethon import Button

LOG_CHAT_ID = int(os.environ.get("LOG_CHAT_ID", "0"))

def _style(s):
    try:
        from telethon.tl.types import KeyboardButtonStyle
        if s == "primary": return KeyboardButtonStyle(bg_primary=True)
        if s == "success": return KeyboardButtonStyle(bg_success=True)
        if s == "danger": return KeyboardButtonStyle(bg_danger=True)
    except Exception:
        pass
    return None

def _btn(text, data, s=None):
    try:
        from telethon.tl.types import KeyboardButtonCallback
        return KeyboardButtonCallback(text=text, data=data, style=_style(s))
    except Exception:
        return Button.inline(text, data)

class Logger:
    def __init__(self, db):
        self.db = db
        self.logs = db.logs if db is not None else None

    async def log(self, uid, username, first_name, action, detail="", chat_id=None):
        if self.logs is None:
            return
        doc = {
            "user_id": uid,
            "username": username or "",
            "first_name": first_name or "",
            "action": action,
            "detail": detail,
            "chat_id": chat_id,
            "ts": datetime.utcnow(),
        }
        try:
            res = await self.logs.insert_one(doc)
            doc["_id"] = res.inserted_id
        except Exception:
            return
        await self._send_to_group(doc)

    async def _send_to_group(self, doc):
        log_chat_id = None
        if self.db is not None:
            try:
                s = await self.db.get_settings()
                log_chat_id = s.get("log_chat_id")
            except Exception:
                pass
        if not log_chat_id:
            log_chat_id = LOG_CHAT_ID
        if not log_chat_id:
            return
        bot = _bot_ref.get("bot")
        if not bot:
            return
        try:
            text = (
                "📋 <b>LOG EVENT</b>\n\n"
                "👤 <b>User:</b> " + html.escape(doc["first_name"] or "Unknown") + "\n"
                "🆔 <b>ID:</b> <code>" + str(doc["user_id"]) + "</code>\n"
                "🔗 <b>Username:</b> @" + html.escape(doc["username"] or "none") + "\n\n"
                "⚡ <b>Action:</b> <code>" + html.escape(doc["action"]) + "</code>\n"
                "📝 <b>Detail:</b> " + html.escape(str(doc["detail"])[:200]) + "\n"
                "🕒 <b>Time:</b> <code>" + doc["ts"].strftime("%Y-%m-%d %H:%M:%S") + " UTC</code>"
            )
            await bot.send_message(int(log_chat_id), text, parse_mode="html", buttons=[
                [_btn("🗑 Delete This Log", ("log:del:" + str(doc.get("_id", ""))).encode(), "danger")]
            ])
        except Exception:
            pass

_bot_ref = {}
