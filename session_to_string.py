import os, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(input("API_ID: "))
API_HASH = input("API_HASH: ")

client = TelegramClient(os.path.expanduser("~/.tgv"), API_ID, API_HASH)

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("Session not authorized. Run /root/vc first.")
        return
    print("")
    print("TG_SESSION (copy to Heroku config):")
    print("")
    print(StringSession.save(client.session))

asyncio.run(main())
