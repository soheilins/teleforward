import os
import sys
import time
import requests
import json

# ========== CONFIGURATION ==========
TOKEN = os.environ.get("RUBIKA_TOKEN")
if not TOKEN:
    print("❌ Error: RUBIKA_TOKEN environment variable not set.")
    sys.exit(1)

BASE_API = f"https://botapi.rubika.ir/v3/{TOKEN}"
GET_UPDATES_URL = f"{BASE_API}/getUpdates"
SEND_MESSAGE_URL = f"{BASE_API}/sendMessage"

def send_message(chat_id, text):
    """Send a text message to a chat."""
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
        data = resp.json()
        print(f"Send response: {json.dumps(data, indent=2)}")
        return data.get("status") == "OK"
    except Exception as e:
        print(f"Send error: {e}")
        return False

def get_chat_id_from_update(limit=10, timeout_seconds=60):
    """Poll for updates and return the first chat_id found."""
    print(f"🔄 Polling for updates (timeout: {timeout_seconds}s)...")
    print("📱 Please send any message to the bot RIGHT NOW (e.g., /start or 'hello').")
    start_time = time.time()
    offset_id = None

    while time.time() - start_time < timeout_seconds:
        payload = {"limit": limit}
        if offset_id:
            payload["offset_id"] = offset_id

        try:
            resp = requests.post(GET_UPDATES_URL, json=payload, timeout=10)
            data = resp.json()
            # print(f"DEBUG: {json.dumps(data, indent=2)}")  # uncomment for debugging

            if data.get("status") != "OK":
                print(f"⚠️ API status not OK: {data}")
                time.sleep(2)
                continue

            updates = data.get("data", {}).get("updates", [])
            if updates:
                # Process the first update
                upd = updates[0]
                offset_id = data["data"].get("next_offset_id")  # for future polling
                chat_id = upd.get("chat_id")
                if chat_id:
                    print(f"✅ Found chat_id: {chat_id}")
                    return chat_id
                else:
                    print("⚠️ Update has no chat_id, skipping...")
            else:
                print("⏳ No updates yet, waiting...")
        except Exception as e:
            print(f"Polling error: {e}")
        time.sleep(2)

    print("❌ Timeout: No update received. Did you send a message?")
    return None

def main():
    print("="*60)
    print("Rubika Bot – Chat ID Detector & Test Sender")
    print("="*60)

    # Step 1: Get chat_id from an incoming message
    chat_id = get_chat_id_from_update(limit=10, timeout_seconds=60)
    if not chat_id:
        print("Failed to obtain chat_id. Exiting.")
        sys.exit(1)

    # Step 2: Send a test message to that chat_id
    test_text = f"✅ Test message from your bot at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    success = send_message(chat_id, test_text)

    # Step 3: Report result
    if success:
        print("\n🎉 SUCCESS! The bot can send messages to this chat_id.")
        print(f"👉 Use this chat_id in your main script: {chat_id}")
    else:
        print("\n❌ Failed to send test message. Check token or network.")

if __name__ == "__main__":
    main()
