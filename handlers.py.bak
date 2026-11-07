import asyncio, html
from telethon import events, Button

def init(ctx):
    bot = ctx["bot"]; user_client = ctx["user_client"]; DB = ctx["DB"]
    LOGIN = ctx["LOGIN"]; MENU = ctx["MENU"]; OWNER_IDS = ctx["OWNER_IDS"]
    approved = ctx["approved"]; pending = ctx["pending"]; WAIT = ctx["WAIT"]
    format_vc_result = ctx["format_vc_result"]; paginate = ctx["paginate"]
    check_cooldown = ctx["check_cooldown"]; validate_target = ctx["validate_target"]
    broadcast = ctx["broadcast"]; health_check = ctx["health_check"]

    async def owner(uid): return uid in OWNER_IDS

    @bot.on(events.NewMessage(pattern=r"^/health$"))
    async def h_health(event):
        if not await owner(event.sender_id): return
        r = await health_check(user_client)
        t = "🩺 <b>Health OK</b>\n👤 " + html.escape(str(r.get("name"))) + "\n🆔 <code>" + str(r.get("id")) + "</code>\n📱 <code>" + html.escape(str(r.get("phone"))) + "</code>" if r.get("ok") else "❌ <b>Unhealthy</b>\n<code>" + html.escape(str(r.get("error"))) + "</code>"
        await event.respond(t, parse_mode="html")

    @bot.on(events.NewMessage(pattern=r"^/stats$"))
    async def h_stats(event):
        if not await owner(event.sender_id): return
        if DB:
            c = await DB.count(); t = "📊 <b>Stats</b>\n👥 Approved: <b>" + str(c["approved"]) + "</b>\n⏳ Pending: <b>" + str(c["pending"]) + "</b>"
        else:
            t = "📊 <b>Stats</b>\n👥 Approved: <b>" + str(len(approved)) + "</b>\n⏳ Pending: <b>" + str(len(pending)) + "</b>"
        await event.respond(t, parse_mode="html", buttons=MENU["owner"]())

    @bot.on(events.NewMessage(pattern=r"^/broadcast(?:\s+([\s\S]+))?$"))
    async def h_broadcast(event):
        if not await owner(event.sender_id): return
        txt = event.pattern_match.group(1)
        if not txt and event.reply_to_msg_id:
            m = await event.get_reply_message(); txt = m.raw_text if m else None
        if not txt: return await event.respond("Usage: /broadcast <text> or reply to a message.")
        if DB:
            s, f = await broadcast(bot, DB, event.sender_id, txt)
            await event.respond("📢 Broadcast: ✅ " + str(s) + " / ❌ " + str(f))
        else:
            await event.respond("DB not configured.")

    @bot.on(events.CallbackQuery(func=lambda e: e.data == b"own:health"))
    async def cb_health(event):
        r = await health_check(user_client)
        t = "🩺 <b>Health</b>\n" + ("OK ✅" if r.get("ok") else "ERROR ❌")
        await event.edit(t, parse_mode="html", buttons=[[Button.inline("⬅️ Back", b"menu:main")]])
        raise events.StopPropagation

    @bot.on(events.CallbackQuery(func=lambda e: e.data == b"own:login"))
    async def cb_login(event):
        uid = event.sender_id
        if uid not in OWNER_IDS: return await event.answer("Owner only", alert=True)
        if await user_client.is_user_authorized(): return await event.answer("Already logged in", alert=True)
        LOGIN.cancel(uid)
        await event.edit("📱 Send phone number (e.g. +91...)", parse_mode="html")
        raise events.StopPropagation

    @bot.on(events.NewMessage())
    async def h_login(event):
        uid = event.sender_id; st = LOGIN.get_state(uid)
        if not st: return
        txt = (event.raw_text or "").strip()
        if not txt: return
        if st == "phone":
            r = await LOGIN.start(uid, txt)
            await event.respond("📨 OTP sent." if r.get("ok") else "❌ " + html.escape(r.get("error","")))
        elif st == "otp":
            r = await LOGIN.submit_code(uid, txt)
            if r.get("ok") and r.get("step") == "done":
                if DB: await DB.save_session(OWNER_IDS[0], r["session"])
                await event.respond("✅ Logged in! Session saved.")
            elif r.get("ok") and r.get("step") == "2fa":
                await event.respond("🔐 2FA password required:")
            else:
                await event.respond("❌ " + html.escape(r.get("error","")))
        elif st == "2fa":
            r = await LOGIN.submit_password(uid, txt)
            if r.get("ok"):
                if DB: await DB.save_session(OWNER_IDS[0], r["session"])
                await event.respond("✅ Logged in with 2FA! Session saved.")
            else:
                await event.respond("❌ " + html.escape(r.get("error","")))
        raise events.StopPropagation

    @bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"own:pending:")))
    async def cb_pending(event):
        if event.sender_id not in OWNER_IDS: return await event.answer("Owner only", alert=True)
        page = int(event.data.decode().split(":")[2])
        items = await DB.list_pending(limit=100) if DB else [{"_id": k, "name": v.get("name","")} for k,v in pending.items()]
        chunk, page, pages = paginate(items, page, 8)
        lines = ["👥 <b>Pending</b> (" + str(page+1) + "/" + str(pages) + ")\n"]
        for it in chunk:
            lines.append("• <code>" + str(it.get("_id")) + "</code> — " + html.escape(str(it.get("name",""))))
        nav = []
        if page > 0: nav.append(Button.inline("⬅️ Prev", ("own:pending:"+str(page-1)).encode()))
        if page < pages-1: nav.append(Button.inline("Next ➡️", ("own:pending:"+str(page+1)).encode()))
        btns = [nav] if nav else []
        btns.append([Button.inline("⬅️ Back", b"menu:main")])
        await event.edit("\n".join(lines), parse_mode="html", buttons=btns)
        raise events.StopPropagation

    @bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"own:approved:")))
    async def cb_approved(event):
        if event.sender_id not in OWNER_IDS: return await event.answer("Owner only", alert=True)
        page = int(event.data.decode().split(":")[2])
        items = await DB.list_approved(limit=200) if DB else [{"_id": x} for x in approved]
        chunk, page, pages = paginate(items, page, 8)
        lines = ["✅ <b>Approved</b> (" + str(page+1) + "/" + str(pages) + ")\n"]
        for it in chunk:
            lines.append("• <code>" + str(it.get("_id")) + "</code>")
        nav = []
        if page > 0: nav.append(Button.inline("⬅️ Prev", ("own:approved:"+str(page-1)).encode()))
        if page < pages-1: nav.append(Button.inline("Next ➡️", ("own:approved:"+str(page+1)).encode()))
        btns = [nav] if nav else []
        btns.append([Button.inline("⬅️ Back", b"menu:main")])
        await event.edit("\n".join(lines), parse_mode="html", buttons=btns)
        raise events.StopPropagation
