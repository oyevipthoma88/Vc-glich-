#!/bin/bash

echo "═══════════════════════════════════════════════"
echo "  VC Glich Bot — Interactive Env Setup"
echo "═══════════════════════════════════════════════"
echo ""

read -rp "API_ID [28795512]: " IN
export API_ID="${IN:-28795512}"

read -rp "API_HASH [c17e4eb6d994c9892b8a8b6bfea4042a]: " IN
export API_HASH="${IN:-c17e4eb6d994c9892b8a8b6bfea4042a}"

read -rp "BOT_TOKEN [9208317007:AAFsE08g3OvkNMsayh7_8IX3joOltQJ3b6U]: " IN
export BOT_TOKEN="${IN:-9208317007:AAFsE08g3OvkNMsayh7_8IX3joOltQJ3b6U}"

read -rp "OWNER_IDS [8098146730]: " IN
export OWNER_IDS="${IN:-8098146730}"

# TG_SESSION from file
if [ -f /root/.tg_session_string.txt ]; then
    AUTO_SESSION=$(head -1 /root/.tg_session_string.txt | tr -d '\n')
    if [ -n "$AUTO_SESSION" ] && [[ "$AUTO_SESSION" == 1* ]] && [ ${#AUTO_SESSION} -gt 100 ]; then
        echo "TG_SESSION found (${#AUTO_SESSION} chars)"
        read -rp "Use it? [Y/n]: " USE
        [[ ! "$USE" =~ ^[Nn]$ ]] && export TG_SESSION="$AUTO_SESSION"
    else
        echo "⚠️  /root/.tg_session_string.txt invalid (len=${#AUTO_SESSION}) — ignoring"
    fi
fi

read -rp "MONGO_URI [mongodb+srv://xmyqiqn5_db_user:wRw6UK2ha4KlvaUq@cluster0.mcrnm6f.mongodb.net/]: " IN
export MONGO_URI="${IN:-mongodb+srv://xmyqiqn5_db_user:wRw6UK2ha4KlvaUq@cluster0.mcrnm6f.mongodb.net/}"

# Optional URLs (press Enter for empty)
read -rp "TUTORIAL_URL (optional): " IN
export TUTORIAL_URL="$IN"

read -rp "VIDEO_URL (optional): " IN
export VIDEO_URL="$IN"

read -rp "LOG_CHAT_ID (group ID for logs, -100...): " IN
export LOG_CHAT_ID="${IN:-0}"

read -rp "START_PIC_URL (optional image URL): " IN
export START_PIC_URL="$IN"

echo ""
echo "═══════════════════════════════════════════════"
echo "  Env Summary"
echo "═══════════════════════════════════════════════"
echo "  API_ID:      $API_ID"
echo "  API_HASH:    ${API_HASH:0:8}... (${#API_HASH} chars)"
echo "  BOT_TOKEN:   ${BOT_TOKEN:0:10}... (${#BOT_TOKEN} chars)"
echo "  OWNER_IDS:   $OWNER_IDS"
echo "  TG_SESSION:  ${TG_SESSION:+set (${#TG_SESSION} chars)}${TG_SESSION:-not set}"
echo "  MONGO_URI:   ${MONGO_URI:-not set}"
echo "  TUTORIAL:    ${TUTORIAL_URL:-(empty — button hidden)}"
echo "  VIDEO:       ${VIDEO_URL:-(empty — button hidden)}"
echo "═══════════════════════════════════════════════"
echo ""

read -rp "Start bot? [Y/n]: " GO
[[ "$GO" =~ ^[Nn]$ ]] && echo "Cancelled." && exit 0

echo ""
echo "🚀 Starting bot... (Ctrl+C to stop)"
echo ""
/root/vcvenv/bin/python3 -u bot.py
