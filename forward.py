import os
import asyncio
import requests
from telethon import TelegramClient

async def main():
    # ---------- Load secrets ----------
    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')
    channel_username = os.getenv('TELEGRAM_CHANNEL')
    rubika_bot_token = os.getenv('RUBIKA_BOT_TOKEN')
    # List of Rubika user IDs (comma-separated in secret)
    recipient_ids_str = os.getenv('RUBIKA_RECIPIENTS')   # e.g. "123456,789012,345678"
    recipient_ids = [uid.strip() for uid in recipient_ids_str.split(',') if uid.strip()]

    if not recipient_ids:
        print("No Rubika recipients provided.")
        return

    # ---------- Telethon client ----------
    client = TelegramClient('session', api_id, api_hash)
    await client.start(phone=phone)
    
    entity = await client.get_entity(channel_username)
    print(f"Connected to channel: {entity.title}")

    # ---------- State: last processed message ID ----------
    state_file = 'last_msg_id.txt'
    last_id = 0
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            last_id = int(f.read().strip())
    print(f"Last processed msg ID: {last_id}")

    # ---------- Fetch new text messages ----------
    new_msgs = []
    async for msg in client.iter_messages(entity, limit=30):
        if msg.id <= last_id:
            break
        if msg.text and msg.text.strip():
            new_msgs.append(msg)

    if not new_msgs:
        print("No new text messages.")
        await client.disconnect()
        return

    print(f"Found {len(new_msgs)} new message(s)")

    # Process from oldest to newest
    for msg in reversed(new_msgs):
        text = msg.text[:4000]   # safe length
        # Telegram original link
        link = f"https://t.me/{channel_username}/{msg.id}"
        full_text = f"📢 *New from channel*:\n\n{text}\n\n[View original]({link})"

        # Send to each Rubika recipient
        for uid in recipient_ids:
            url = f"https://api.telegram.org/bot{rubika_bot_token}/sendMessage"
            payload = {
                "chat_id": uid,
                "text": full_text,
                "parse_mode": "Markdown"
            }
            try:
                resp = requests.post(url, data=payload, timeout=10)
                print(f"Sent msg {msg.id} to {uid} → {resp.status_code}")
            except Exception as e:
                print(f"Failed to send to {uid}: {e}")

    # Update state with the newest message ID we saw
    with open(state_file, 'w') as f:
        f.write(str(new_msgs[0].id))

    await client.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
