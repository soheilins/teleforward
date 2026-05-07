import os
import requests
import time
import sys

TOKEN = os.environ.get("RUBIKA_TOKEN")
if not TOKEN:
    print("❌ RUBIKA_TOKEN environment variable not set.")
    sys.exit(1)

BASE_API = f"https://botapi.rubika.ir/v3/{TOKEN}"
GET_UPDATES_URL = f"{BASE_API}/getUpdates"
SEND_MESSAGE_URL = f"{BASE_API}/sendMessage"

def get_chat_id_from_user():
    """Ask user to send a message to the bot, then extract chat_id."""
    print("📡 Waiting for you to send ANY message to the bot...")
    print("   (e.g., send /start or just 'hello')")
    print("   You have 60 seconds.")
    time.sleep(60)

    payload = {"limit": 1}
    try:
        resp = requests.post(GET_UPDATES_URL, json=payload, timeout=10)
        data = resp.json()
        if data.get("status") != "OK":
            print(f"❌ API error: {data}")
            return None

        updates = data.get("data", {}).get("updates", [])
        if not updates:
            print("❌ No updates received. Did you send a message?")
            return None

        for update in updates:
            if update.get("type") == "NewMessage":
                chat_id = update.get("chat_id")
                print(f"✅ Found your chat_id: {chat_id}")
                return chat_id
        print("❌ Found an update, but it was not a new message.")
        return None
    except Exception as e:
        print(f"❌ Exception while fetching updates: {e}")
        return None

def send_text_message(chat_id, text):
    """Send a simple text message to the given chat_id."""
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        print(f"Response JSON: {r.text}")
        if r.status_code == 200 and r.json().get("status") == "OK":
            print("✅ Message sent successfully.")
            return True
        else:
            print("❌ Message sending failed.")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    # Step 1: Get the correct chat_id
    chat_id = get_chat_id_from_user()
    if not chat_id:
        print("Cannot proceed without chat_id.")
        sys.exit(1)

    # Step 2: Send a test message
    test_text = f"Test message at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    success = send_text_message(chat_id, test_text)
    if success:
        print("🎉 Bot is working! Use this chat_id in your main script.")
        print(f"   Hardcode: RUBIKA_USER_ID = '{chat_id}'")
    else:
        print("⚠️ Failed to send message. Check bot token or network.")

if __name__ == "__main__":
    main()
