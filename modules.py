import os, json, asyncio, random, time, html, logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("vcbot.modules")

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import ReturnDocument
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False
    log.warning("motor not installed. Run: pip install motor pymongo")

try:
    from telethon.tl.types import KeyboardButtonStyle, KeyboardButtonCallback, KeyboardButtonUrl
    HAS_STYLE = True
except ImportError:
    HAS_STYLE = False

def style(s):
    if not HAS_STYLE or not s:
        return None
    try:
        return KeyboardButtonStyle(bg_primary=(s == "primary"), bg_success=(s == "success"), bg_danger=(s == "danger"))
    except Exception:
        return None

def btn(text, data, s=None):
    if HAS_STYLE:
        try:
            return KeyboardButtonCallback(text=text, data=data, style=style(s))
        except Exception:
            pass
    from telethon import Button
    return Button.inline(text, data)

def lnk(text, url, s=None):
    if HAS_STYLE:
        try:
            return KeyboardButtonUrl(text=text, url=url, style=style(s))
        except Exception:
            pass
    from telethon import Button
    return Button.url(text, url)

class Database:
    def __init__(self, uri, db_name="vcglich"):
        if not HAS_MOTOR:
            raise RuntimeError("motor not installed: pip install motor pymongo")
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.users = self.db["users"]
        self.pending = self.db["pending"]
        self.sessions = self.db["sessions"]
        self.logs = self.db["logs"]
        log.info("MongoDB connected: %s", db_name)

    async def ensure_indexes(self):
        await self.users.create_index("approved_at")
        await self.pending.create_index("requested_at")
        await self.sessions.create_index("updated_at")

    async def request_access(self, uid, name, username):
        doc = {"_id": uid, "name": name, "username": username or "", "requested_at": datetime.utcnow(), "status": "pending"}
        await self.pending.update_one({"_id": uid}, {"$set": doc}, upsert=True)
        return True

    async def approve(self, uid, by):
        r = await self.pending.find_one_and_update({"_id": uid, "status": "pending"}, {"$set": {"status": "approved", "approved_by": by, "approved_at": datetime.utcnow()}}, return_document=ReturnDocument.AFTER)
        if not r:
            return False
        await self.users.update_one({"_id": uid}, {"$set": {"name": r.get("name", ""), "username": r.get("username", ""), "approved_at": r["approved_at"], "approved_by": by, "role": "user"}}, upsert=True)
        return True

    async def reject(self, uid, by):
        r = await self.pending.find_one_and_update({"_id": uid, "status": "pending"}, {"$set": {"status": "rejected", "rejected_by": by, "rejected_at": datetime.utcnow()}})
        return bool(r)

    async def is_approved(self, uid):
        u = await self.users.find_one({"_id": uid})
        return bool(u and u.get("role") in ("user", "owner"))

    async def list_pending(self, limit=20):
        cur = self.pending.find({"status": "pending"}).sort("requested_at", 1).limit(limit)
        return [d async for d in cur]

    async def list_approved(self, limit=100):
        cur = self.users.find({"role": {"$in": ["user", "owner"]}}).sort("approved_at", -1).limit(limit)
        return [d async for d in cur]

    async def revoke(self, uid):
        r = await self.users.delete_one({"_id": uid, "role": "user"})
        return bool(r.deleted_count)

    async def count(self):
        return {"approved": await self.users.count_documents({"role": {"$in": ["user", "owner"]}}), "pending": await self.pending.count_documents({"status": "pending"})}

    async def save_session(self, owner_id, session_str):
        await self.sessions.update_one({"_id": owner_id}, {"$set": {"session": session_str, "updated_at": datetime.utcnow()}}, upsert=True)

    async def get_session(self, owner_id):
        d = await self.sessions.find_one({"_id": owner_id})
        return d.get("session") if d else None

    async def delete_session(self, owner_id):
        await self.sessions.delete_one({"_id": owner_id})

    async def log_event(self, uid, action, detail=""):
        await self.logs.insert_one({"user_id": uid, "action": action, "detail": detail, "ts": datetime.utcnow()})

class LoginFlow:
    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
        self._clients = {}
        self._states = {}

    def _new_client(self, uid):
        from telethon import TelegramClient
        return TelegramClient(f"login_{uid}", self.api_id, self.api_hash)

    async def start(self, uid, phone):
        if self._states.get(uid) in ("otp", "2fa"):
            return {"ok": False, "error": "Login in progress. /cancel first."}
        c = self._new_client(uid)
        await c.connect()
        try:
            sent = await c.send_code_request(phone)
            self._clients[uid] = (c, phone, sent.phone_code_hash)
            self._states[uid] = "otp"
            return {"ok": True, "step": "otp", "phone": phone}
        except Exception as e:
            await c.disconnect()
            return {"ok": False, "error": str(e)}

    async def submit_code(self, uid, code):
        if self._states.get(uid) != "otp":
            return {"ok": False, "error": "No OTP pending. /login first."}
        from telethon.errors import SessionPasswordNeededError
        c, phone, h = self._clients[uid]
        try:
            await c.sign_in(phone=phone, code=code, phone_code_hash=h)
            s = c.session.save()
            self._states[uid] = "done"
            return {"ok": True, "step": "done", "session": s}
        except SessionPasswordNeededError:
            self._states[uid] = "2fa"
            return {"ok": True, "step": "2fa"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def submit_password(self, uid, password):
        if self._states.get(uid) != "2fa":
            return {"ok": False, "error": "No 2FA pending."}
        c, _, _ = self._clients[uid]
        try:
            await c.sign_in(password=password)
            s = c.session.save()
            self._states[uid] = "done"
            return {"ok": True, "step": "done", "session": s}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def cancel(self, uid):
        if uid in self._clients:
            try:
                asyncio.create_task(self._clients[uid][0].disconnect())
            except Exception:
                pass
        self._clients.pop(uid, None)
        self._states.pop(uid, None)

    def get_state(self, uid):
        return self._states.get(uid)

def MENUS(urls):
    t = urls.get("tutorial", "https://github.com/oyevipthoma88/Vc-glich-")
    v = urls.get("video", t)
    bf = urls.get("botfather", "https://t.me/BotFather")
    mt = urls.get("mytg", "https://my.telegram.org")

    def main():
        return [
            [btn("Get VC IP", b"menu:vc", "primary"), btn("My Account", b"menu:me", "primary")],
            [btn("Tutorial", b"menu:tut", "success"), btn("Help", b"menu:help", "primary")],
            [lnk("Video Guide", v, "success"), lnk("Docs", t, "primary")],
        ]

    def owner():
        return [
            [btn("Pending", b"own:pending", "primary"), btn("Approved", b"own:approved", "success")],
            [btn("Stats", b"own:stats", "primary"), btn("Refresh", b"own:refresh", "primary")],
            [btn("Login Userbot", b"own:login", "success")],
            [btn("Main Menu", b"menu:main", "success")],
        ]

    def tutorial():
        return [
            [lnk("BotFather", bf, "primary"), lnk("my.telegram.org", mt, "primary")],
            [lnk("GitHub Docs", t, "success"), lnk("Video", v, "success")],
            [btn("Back", b"menu:main", "danger")],
        ]

    return {"main": main, "owner": owner, "tutorial": tutorial}

async def broadcast(bot, db, owner_id, text, parse_mode="html"):
    sent, failed = 0, 0
    cur = db.users.find({"role": {"$in": ["user", "owner"]}})
    async for u in cur:
        try:
            await bot.send_message(u["_id"], text, parse_mode=parse_mode)
            sent += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1
    return sent, failed

async def health_check(user_client):
    try:
        me = await user_client.get_me()
        return {"ok": True, "name": me.first_name, "id": me.id, "phone": "+" + str(me.phone), "ts": time.time()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Strong logic helpers ────────────────────────────────────────
import re as _re
_COOLDOWN = {}
COOLDOWN_SEC = 15

def check_cooldown(uid):
    now = time.time()
    last = _COOLDOWN.get(uid, 0)
    if now - last < COOLDOWN_SEC:
        return int(COOLDOWN_SEC - (now - last))
    _COOLDOWN[uid] = now
    return 0

def validate_target(text):
    t = text.strip()
    if _re.match(r"^https?://t\.me/", t):
        return t
    if _re.match(r"^@[A-Za-z0-9_]{4,}$", t):
        return t
    if _re.match(r"^-100\d{7,}$", t):
        return t
    return None

def paginate(items, page=0, per_page=8):
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    return items[page*per_page:(page+1)*per_page], page, pages

def format_vc_result(res):
    if "error" in res:
        return "❌ <b>Error:</b> <code>" + html.escape(str(res.get("error"))) + "</code>\n" + html.escape(str(res.get("detail", "")))
    lines = ["✅ <b>VC Server Info</b>", "", "📛 <b>" + html.escape(str(res.get("title", ""))) + "</b>", "🆔 <code>" + str(res.get("group_id", "")) + "</code>", "👥 Participants: <b>" + str(res.get("participants", "?")) + "</b>", "", "<b>SFU IPs:</b>"]
    for ip in res.get("ips", []):
        lines.append("• <code>" + html.escape(str(ip)) + "</code>")
    return "\n".join(lines)

# ─── MENUS v2 (colored + better labels) ─────────────────────────
def MENUS(urls):
    t = urls.get("tutorial", "https://github.com/oyevipthoma88/Vc-glich-")
    v = urls.get("video", t)
    bf = urls.get("botfather", "https://t.me/BotFather")
    mt = urls.get("mytg", "https://my.telegram.org")

    def main():
        return [
            [btn("🔍 Get VC IP", b"menu:vc", "primary"), btn("👤 My Account", b"menu:me", "primary")],
            [btn("📖 Tutorial", b"menu:tut", "success"), btn("❓ Help", b"menu:help", "primary")],
            [lnk("🎥 Video Guide", v, "success"), lnk("📄 Docs", t, "primary")],
        ]

    def owner():
        return [
            [btn("👥 Pending", b"own:pending:0", "primary"), btn("✅ Approved", b"own:approved:0", "success")],
            [btn("📊 Stats", b"own:stats", "primary"), btn("🩺 Health", b"own:health", "primary")],
            [btn("🔑 Login Userbot", b"own:login", "success"), btn("📢 Broadcast", b"own:broadcast", "danger")],
            [btn("🏠 Main Menu", b"menu:main", "success")],
        ]

    def tutorial():
        return [
            [lnk("🤖 BotFather", bf, "primary"), lnk("🔑 my.telegram.org", mt, "primary")],
            [lnk("📄 GitHub Docs", t, "success"), lnk("🎥 Video", v, "success")],
            [btn("⬅️ Back", b"menu:main", "danger")],
        ]

    return {"main": main, "owner": owner, "tutorial": tutorial}
