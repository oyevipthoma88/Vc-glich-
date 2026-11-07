import os, json, asyncio, random, time, html, logging
from pathlib import Path
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import JoinGroupCallRequest, LeaveGroupCallRequest, GetGroupCallRequest
from telethon.tl.types import DataJSON, InputPeerSelf, UpdateGroupCallConnection, PeerChannel, PeerChat

try:
    from telethon.tl.types import KeyboardButtonCallback, KeyboardButtonStyle
    HAS_CB_STYLE = True
except Exception:
    HAS_CB_STYLE = False

try:
    from telethon.tl.types import KeyboardButtonUrl
    HAS_URL_STYLE = True
except Exception:
    HAS_URL_STYLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vcbot")

from modules import Database, LoginFlow, MENUS, broadcast, health_check, btn, lnk, check_cooldown, validate_target, paginate, format_vc_result, safe_call, send_log, send_start_pic
from logsystem import Logger, _bot_ref

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_IDS = [int(x.strip()) for x in os.environ.get("OWNER_IDS", "").split(",") if x.strip()]
TG_SESSION = os.environ.get("TG_SESSION", "").strip()
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
APPROVED_FILE = DATA_DIR / "approved.json"
PENDING_FILE = DATA_DIR / "pending.json"
TUTORIAL_URL = os.environ.get("TUTORIAL_URL", "").strip()
VIDEO_URL = os.environ.get("VIDEO_URL", "").strip()
BOTFATHER_URL = "https://t.me/BotFather"
MYTG_URL = "https://my.telegram.org"

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

approved = set(OWNER_IDS)
for x in os.environ.get("APPROVED_IDS", "").split(","):
    if x.strip():
        approved.add(int(x.strip()))
approved |= set(int(x) for x in load_json(APPROVED_FILE, []))
pending = {int(k): v for k, v in load_json(PENDING_FILE, {}).items()}
WAIT = {}

def style_obj(style):
    if not (HAS_CB_STYLE or HAS_URL_STYLE) or not style:
        return None
    try:
        if style == "primary":
            return KeyboardButtonStyle(bg_primary=True)
        if style == "success":
            return KeyboardButtonStyle(bg_success=True)
        if style == "danger":
            return KeyboardButtonStyle(bg_danger=True)
    except Exception:
        return None
    return None

def cb(text, data, style=None):
    if HAS_CB_STYLE:
        try:
            return KeyboardButtonCallback(text=text, data=data, style=style_obj(style))
        except Exception:
            pass
    return Button.inline(text, data)

def lnk(text, url, style=None):
    if HAS_URL_STYLE:
        try:
            return KeyboardButtonUrl(text=text, url=url, style=style_obj(style))
        except Exception:
            pass
    return Button.url(text, url)




async def resolve_entity(client, target):
    try:
        return await client.get_entity(target)
    except Exception:
        pass
    try:
        tid = int(target)
        if tid < 0 and str(tid).startswith("-100"):
            return await client.get_entity(PeerChannel(tid + 1000000000000))
        if tid < 0:
            return await client.get_entity(PeerChat(-tid))
        return await client.get_entity(tid)
    except Exception:
        pass
    try:
        async for _ in client.iter_dialogs(limit=200):
            pass
        return await client.get_entity(target)
    except Exception as e:
        raise e

async def fetch_vc(uc, target):
    try:
        entity = await resolve_entity(uc, target)
    except Exception as e:
        return {"target": target, "error": "entity_not_found", "detail": str(e)}
    full = await uc(GetFullChannelRequest(entity))
    if not full.full_chat.call:
        return {"target": target, "title": entity.title, "error": "no_active_vc"}
    call = full.full_chat.call
    parts = None
    try:
        info = await uc(GetGroupCallRequest(call=call, limit=200))
        plist = info.participants or []
        parts = (str(len(plist)) + "+") if getattr(info, "participants_next_offset", None) else len(plist)
    except Exception:
        pass
    ssrc = random.randint(100000000, 999999999)
    params = DataJSON(data=json.dumps({
        "ssrc": ssrc,
        "transport": {
            "ufrag": "abcd",
            "pwd": "0123456789abcdef0123456789abcdef",
            "fingerprints": [{"hash": "sha-256", "setup": "passive", "fingerprint": ":".join(["00"] * 32)}],
            "candidates": [{"component": "1", "foundation": "1", "generation": "0", "id": "1", "ip": "1.1.1.1", "port": "1", "priority": "1", "protocol": "udp", "type": "host", "network-cost": "999"}],
        },
    }))
    try:
        result = await uc(JoinGroupCallRequest(call=call, join_as=InputPeerSelf(), params=params, muted=True, video_stopped=True))
    except Exception as e:
        return {"target": target, "title": entity.title, "error": "join_failed", "detail": str(e)}
    ips = set()
    for upd in result.updates:
        if isinstance(upd, UpdateGroupCallConnection):
            try:
                d = json.loads(upd.params.data)
                for x in d["transport"]["candidates"]:
                    ips.add(str(x.get("ip", "")) + ":" + str(x.get("port", "")))
            except Exception:
                pass
    try:
        await uc(LeaveGroupCallRequest(call=call, source=0))
    except Exception:
        pass
    return {"target": target, "title": entity.title, "group_id": entity.id, "active_vc": True, "ssrc": ssrc, "ips": sorted(ips), "participants": parts}

bot = TelegramClient("bot", API_ID, API_HASH)

DB = Database(os.environ["MONGO_URI"]) if os.environ.get("MONGO_URI") else None
LOGIN = LoginFlow(API_ID, API_HASH)
MENU = MENUS({"tutorial": TUTORIAL_URL, "video": VIDEO_URL})
LOGGER = Logger(DB)
_bot_ref["bot"] = bot
main_menu = MENU["main"]
owner_menu = MENU["owner"]
tutorial_menu = MENU["tutorial"]
if TG_SESSION and TG_SESSION.strip() and TG_SESSION.strip().startswith("1") and len(TG_SESSION.strip()) > 100:
    user_client = TelegramClient(StringSession(TG_SESSION), API_ID, API_HASH)
    log.info("Using StringSession from env")
else:
    log.error("TG_SESSION missing or invalid — bot will not work for VC fetch")
    user_client = TelegramClient(StringSession(), API_ID, API_HASH)

async def is_user_approved(uid):
    if uid in OWNER_IDS:
        return True
    if DB:
        return await DB.is_approved(uid)
    return uid in approved

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def h_start(event):
    uid = event.sender_id
    WAIT.pop(uid, None)
    await LOGGER.log(uid, getattr(event.sender, "username", ""), getattr(event.sender, "first_name", ""), "START", "User opened bot")
    if uid in OWNER_IDS:
        await event.respond("👑 <b>Owner Panel</b>\n\nManage access requests and approvals.", buttons=owner_menu(), parse_mode="html")
        return
    if await is_user_approved(uid):
        await event.respond("✅ <b>Access granted</b>\n\nChoose an option below.", buttons=main_menu(), parse_mode="html")
        return
    name = html.escape(event.sender.first_name or "Unknown")
    username = ("@" + event.sender.username) if event.sender.username else "None"
    pending[uid] = {"name": event.sender.first_name or "", "username": event.sender.username or "", "time": int(time.time())}
    save_json(PENDING_FILE, pending)
    await event.respond(
        "⏳ <b>Approval pending</b>\n\nYour request has been sent to the owners. You will be notified once approved.",
        buttons=[[lnk("📖 Tutorial", TUTORIAL_URL, "primary")]],
        parse_mode="html",
    )
    card = (
        "🆕 <b>New access request</b>\n\n"
        "👤 Name: <b>" + name + "</b>\n"
        "🆔 ID: <code>" + str(uid) + "</code>\n"
        "🔗 Username: " + html.escape(username) + "\n\n"
        "Approve or reject below."
    )
    buttons = [[
        cb("✅ Approve", ("apr:" + str(uid)).encode(), "success"),
        cb("❌ Reject", ("rej:" + str(uid)).encode(), "danger"),
    ]]
    for oid in OWNER_IDS:
        try:
            await bot.send_message(oid, card, buttons=buttons, parse_mode="html")
        except Exception as e:
            log.warning("owner notify failed %s: %s", oid, e)

@bot.on(events.CallbackQuery)
async def h_callback(event):
    uid = event.sender_id
    data = event.data.decode(errors="ignore")
    await LOGGER.log(uid, getattr(event.sender, "username", ""), getattr(event.sender, "first_name", ""), "CALLBACK", data)
    if data.startswith(("own:health","own:broadcast","own:pending:","own:approved:","own:login","own:stats","own:logs","own:settings","own:set_log","own:set_pic","log:del:")):
        return
    if data.startswith("apr:") or data.startswith("rej:"):
        if uid not in OWNER_IDS:
            return await event.answer("Only owners can do this.", alert=True)
        target = int(data.split(":", 1)[1])
        if data.startswith("apr:"):
            approved.add(target)
            pending.pop(target, None)
            save_json(APPROVED_FILE, sorted(approved))
            save_json(PENDING_FILE, pending)
            await event.edit("✅ Approved user <code>" + str(target) + "</code>", parse_mode="html")
            try:
                await bot.send_message(target, "✅ <b>Approved!</b>\n\nSend /start.", buttons=main_menu(), parse_mode="html")
            except Exception:
                pass
        else:
            pending.pop(target, None)
            save_json(PENDING_FILE, pending)
            await event.edit("❌ Rejected user <code>" + str(target) + "</code>", parse_mode="html")
            try:
                await bot.send_message(target, "❌ Your access request was rejected.")
            except Exception:
                pass
        return
    if uid not in approved and uid not in OWNER_IDS:
        return await event.answer("Access denied.", alert=True)
    if data == "menu:main":
        await event.edit("🏠 <b>Main Menu</b>", buttons=main_menu(), parse_mode="html")
    elif data == "menu:vc":
        WAIT[uid] = "vc"
        await event.edit("🔍 <b>Send group link, @username, or chat ID.</b>", parse_mode="html")
    elif data == "menu:me":
        me = await user_client.get_me()
        await event.edit("👤 <b>My Account</b>\n\nName: <b>" + html.escape(me.first_name or "") + "</b>\nID: <code>" + str(me.id) + "</code>\nPhone: <code>+" + str(me.phone) + "</code>", buttons=[[cb("⬅️ Back", b"menu:main", "danger")]], parse_mode="html")
    elif data == "menu:tut":
        await event.edit("📖 <b>Tutorial & Resources</b>", buttons=tutorial_menu(), parse_mode="html")
    elif data == "menu:help":
        await event.edit("❓ <b>Help</b>\n\nSend group URL, @username, or chat ID. Bot joins VC silently and extracts SFU server IPs.", buttons=[[cb("⬅️ Back", b"menu:main", "danger")]], parse_mode="html")
    elif data == "own:pending":
        if uid not in OWNER_IDS:
            return await event.answer("Owner only.", alert=True)
        if not pending:
            await event.edit("👥 <b>Pending</b>\n\nNone.", buttons=[[cb("⬅️ Back", b"menu:main", "danger")]], parse_mode="html")
        else:
            lines = ["👥 <b>Pending requests</b>\n"]
            for pid, info in list(pending.items())[:20]:
                lines.append("• <code>" + str(pid) + "</code> — " + html.escape(info.get("name", "")))
            await event.edit("\n".join(lines), buttons=[[cb("⬅️ Back", b"menu:main", "danger")]], parse_mode="html")
    elif data == "own:approved":
        if uid not in OWNER_IDS:
            return await event.answer("Owner only.", alert=True)
        lines = ["✅ <b>Approved users</b>\n"]
        for aid in sorted(approved)[:50]:
            lines.append("• <code>" + str(aid) + "</code>")
        await event.edit("\n".join(lines), buttons=[[cb("⬅️ Back", b"menu:main", "danger")]], parse_mode="html")
    elif data == "own:stats":
        if uid not in OWNER_IDS:
            return await event.answer("Owner only.", alert=True)
        await event.edit("📊 <b>Stats</b>\n\nOwners: <b>" + str(len(OWNER_IDS)) + "</b>\nApproved: <b>" + str(len(approved)) + "</b>\nPending: <b>" + str(len(pending)) + "</b>", buttons=[[cb("⬅️ Back", b"menu:main", "danger")]], parse_mode="html")
    elif data == "own:refresh":
        await event.answer("Refreshed.")

@bot.on(events.NewMessage(pattern=r"^/pending$"))
async def h_pending(event):
    if event.sender_id not in OWNER_IDS:
        return
    if not pending:
        return await event.respond("No pending requests.")
    lines = ["👥 <b>Pending</b>\n"]
    for pid, info in list(pending.items())[:30]:
        lines.append("• <code>" + str(pid) + "</code> — " + html.escape(info.get("name", "")))
    await event.respond("\n".join(lines), parse_mode="html")

@bot.on(events.NewMessage(pattern=r"^/approved$"))
async def h_approved(event):
    if event.sender_id not in OWNER_IDS:
        return
    lines = ["✅ <b>Approved</b>\n"]
    for aid in sorted(approved)[:50]:
        lines.append("• <code>" + str(aid) + "</code>")
    await event.respond("\n".join(lines), parse_mode="html")

@bot.on(events.NewMessage(pattern=r"^/revoke(?:\s+(\d+))?$"))
async def h_revoke(event):
    if event.sender_id not in OWNER_IDS:
        return
    m = event.pattern_match
    if not m.group(1):
        return await event.respond("Usage: /revoke <user_id>")
    target = int(m.group(1))
    approved.discard(target)
    save_json(APPROVED_FILE, sorted(approved))
    await event.respond("Revoked <code>" + str(target) + "</code>", parse_mode="html")

@bot.on(events.NewMessage())
async def h_text(event):
    uid = event.sender_id
    text = (event.raw_text or "").strip()
    if text and not text.startswith("/"):
        await LOGGER.log(uid, getattr(event.sender, "username", ""), getattr(event.sender, "first_name", ""), "TEXT", text[:200])
    if not text or text.startswith("/"):
        return
    if LOGIN.get_state(uid):
        return
    if WAIT.get(uid) == "log_chat":
        WAIT.pop(uid, None)
        try:
            v = text.strip()
            if v == "0" or v == "":
                if DB:
                    await DB.set_setting("log_chat_id", 0)
                return await event.respond("✅ Log channel disabled.")
            val = int(v)
            if not str(val).startswith("-100"):
                raise ValueError("ID must start with -100")
            if DB:
                await DB.set_setting("log_chat_id", val)
                return await event.respond("✅ Log channel set: <code>" + str(val) + "</code>\nBot admin hai toh logs aayenge.", parse_mode="html")
            return await event.respond("❌ DB not configured")
        except Exception as ex:
            return await event.respond("❌ Invalid: " + str(ex))
    if WAIT.get(uid) == "start_pic":
        WAIT.pop(uid, None)
        if text.strip().lower() == "none":
            if DB:
                await DB.set_setting("start_pic_url", "")
            return await event.respond("✅ Start picture removed.")
        if not (text.startswith("http://") or text.startswith("https://")):
            return await event.respond("❌ URL must start with http:// or https://")
        if DB:
            await DB.set_setting("start_pic_url", text.strip())
            return await event.respond("✅ Start picture set:\n<code>" + text.strip() + "</code>", parse_mode="html")
        return await event.respond("❌ DB not configured")
    if WAIT.get(uid) == "broadcast":
        WAIT.pop(uid, None)
        if not text:
            return await event.respond("Empty message, cancelled.")
        if DB:
            from modules import broadcast as _bcast
            s, f = await _bcast(bot, DB, uid, text)
            await event.respond("📢 Broadcast sent: ✅ " + str(s) + " / ❌ " + str(f))
        else:
            await event.respond("DB not configured")
        return
    if uid not in approved and uid not in OWNER_IDS:
        return await event.respond("⛔ Access denied. Send /start to request access.")
    if WAIT.get(uid) == "vc" or validate_target(text):
        target = validate_target(text) or text
        cd = check_cooldown(uid)
        if cd:
            return await event.respond("⏳ Cooldown: wait " + str(cd) + "s")
        WAIT.pop(uid, None)
        msg = await event.respond("⏳ Fetching VC server IPs...")
        try:
            res = await fetch_vc(user_client, target)
            await msg.edit(format_vc_result(res), parse_mode="html")
        except Exception as e:
            await msg.edit("❌ Error: <code>" + html.escape(str(e)) + "</code>", parse_mode="html")
    else:
        await event.respond("Use the menu or send a group link.", buttons=main_menu())

import handlers
handlers.init({"bot": bot, "user_client": user_client, "DB": DB, "LOGIN": LOGIN, "MENU": MENU, "OWNER_IDS": OWNER_IDS, "approved": approved, "pending": pending, "WAIT": WAIT, "fetch_vc": fetch_vc, "format_vc_result": format_vc_result, "paginate": paginate, "check_cooldown": check_cooldown, "validate_target": validate_target, "broadcast": broadcast, "health_check": health_check})

async def main():
    global user_client
    if DB is not None:
        try:
            _s = await DB.get_settings()
            if _s.get("log_chat_id"):
                try:
                    import logsystem as _ls
                    _ls.LOG_CHAT_ID = int(_s["log_chat_id"])
                except Exception:
                    pass
            if _s.get("start_pic_url"):
                try:
                    import modules as _md
                    _md.START_PIC = _s["start_pic_url"]
                except Exception:
                    pass
            log.info("Settings loaded: log_chat=%s, start_pic=%s", _s.get("log_chat_id"), bool(_s.get("start_pic_url")))
        except Exception as _e:
            log.warning("settings load: %s", _e)
    if not TG_SESSION and DB:
        try:
            _s = await DB.get_session(OWNER_IDS[0])
            if _s:
                from telethon.sessions import StringSession as _SS
                user_client = TelegramClient(_SS(_s), API_ID, API_HASH)
        except Exception:
            pass
    await bot.start(bot_token=BOT_TOKEN)
    await user_client.connect()
    ok = await user_client.is_user_authorized()
    log.info("Userbot session valid: %s", ok)
    me = await bot.get_me()
    log.info("Bot started: @%s | Owners: %s", me.username, OWNER_IDS)
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
