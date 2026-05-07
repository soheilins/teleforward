import os
import requests
import sys

RUBIKA_TOKEN = os.environ.get("RUBIKA_TOKEN", "")
USER_ID = "u0JWE2R02172d15a02bb742a785ac9f8"   # your hardcoded ID

BASE_API = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}"
SEND_MESSAGE_URL = f"{BASE_API}/sendMessage"

def send_test():
    if not RUBIKA_TOKEN:
        print("❌ No RUBIKA_TOKEN")
        sys.exit(1)
    payload = {"chat_id": USER_ID, "text": "Test message from bot at " + str(__import__('time').time())}
    try:
        r = requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
        if r.status_code == 200:
            print("✅ Message sent (according to API)")
        else:
            print("❌ API returned error")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    send_test()
