#!/usr/bin/env python3
import sys
import os
import time
import re
import json
import base64
import requests
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime
import arabic_reshaper
from bidi.algorithm import get_display

sys.stdout.reconfigure(line_buffering=True)

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES_PER_RUN = 50
RUBIKA_USER_ID = "b0JWE2R0bQW0eae5690fa217ebebf122"
RUBIKA_TOKEN = os.environ.get("RUBIKA_TOKEN", "")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")

if not RUBIKA_TOKEN:
    print("❌ RUBIKA_TOKEN not set", flush=True)
    sys.exit(1)
if not ENCRYPTION_KEY:
    print("❌ ENCRYPTION_KEY not set", flush=True)
    sys.exit(1)

BASE_API = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}"
SEND_MESSAGE_URL = f"{BASE_API}/sendMessage"
SENT_IDS_FILE = "sent_message_ids.json"

def reshape_persian_text(text):
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

def encode_message(plain_text: str, key: str) -> str:
    plain_bytes = plain_text.encode('utf-8')
    key_bytes = key.encode('utf-8')
    encoded_bytes = bytearray()
    for i, b in enumerate(plain_bytes):
        encoded_bytes.append(b ^ key_bytes[i % len(key_bytes)])
    return base64.b64encode(encoded_bytes).decode('ascii')

def send_rubika_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ Send failed: {resp.status_code}", flush=True)
        else:
            print(f"  📨 Sent coded message (length {len(text)})", flush=True)
    except Exception as e:
        print(f"  ⚠️ Message send error: {e}", flush=True)

def git_pull():
    subprocess.run(["git", "pull", "--ff-only"], check=False)
    print("  🔄 Git pull done", flush=True)

def git_commit_push(file_path, commit_msg):
    subprocess.run(["git", "add", file_path], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False)
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        push_result = subprocess.run(["git", "push"], check=False)
        if push_result.returncode != 0:
            print("  ⚠️ Git push failed – check permissions", flush=True)
        else:
            print(f"  ✅ Committed and pushed {file_path}", flush=True)
    else:
        print("  ℹ️ No changes to commit", flush=True)

def load_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get("sent_ids", []))
    return set()

def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, 'w') as f:
        json.dump({"sent_ids": list(sent_ids)}, f, indent=2)

def fetch_new_messages(last_known_id=None):
    print(f"📡 Fetching messages from @{CHANNEL}...", flush=True)
    all_messages = []
    oldest_id = None
    page = 0

    while len(all_messages) < MAX_MESSAGES_PER_RUN:
        page += 1
        url = f"https://t.me/s/{CHANNEL}"
        if oldest_id:
            url += f"?before={oldest_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  ❌ HTTP error: {e}", flush=True)
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message')
        if not messages:
            break

        page_messages = []
        for msg in messages:
            data_post = msg.get('data-post')
            if not data_post:
                continue
            post_id = int(data_post.split('/')[-1])
            if last_known_id and post_id <= last_known_id:
                return all_messages
            text_div = msg.find('div', class_='tgme_widget_message_text')
            text = text_div.get_text(strip=True) if text_div else ''
            if not text:
                continue
            link = f"https://t.me/{data_post}"
            page_messages.append({'id': post_id, 'text': text, 'link': link})

        if page_messages:
            page_messages.sort(key=lambda x: x['id'])
            oldest_id = min(m['id'] for m in page_messages)
            all_messages.extend(page_messages)
            print(f"  📄 Page {page}: +{len(page_messages)} messages (total {len(all_messages)})", flush=True)
        else:
            break
        time.sleep(1)

    if len(all_messages) > MAX_MESSAGES_PER_RUN:
        all_messages = all_messages[:MAX_MESSAGES_PER_RUN]
    return all_messages

def main():
    print("="*60, flush=True)
    print("🤖 TEXT SCRAPER & ENCODER STARTED", flush=True)
    print(f"Channel: @{CHANNEL}", flush=True)
    print(f"Target Rubika ID: {RUBIKA_USER_ID}", flush=True)
    print("="*60, flush=True)

    start_time = time.time()
    MAX_RUNTIME = 5.9 * 3600
    iteration = 0

    while time.time() - start_time < MAX_RUNTIME:
        iteration += 1
        loop_start = datetime.now()
        print(f"\n{'='*60}", flush=True)
        print(f"🔄 ITERATION {iteration} at {loop_start.strftime('%H:%M:%S')}", flush=True)
        print(f"{'='*60}", flush=True)

        git_pull()
        sent_ids = load_sent_ids()
        print(f"📋 Already sent messages: {len(sent_ids)}", flush=True)

        max_sent_id = max(sent_ids) if sent_ids else 0
        new_messages = fetch_new_messages(max_sent_id)
        print(f"🆕 Found {len(new_messages)} new text messages", flush=True)

        # 🔽 SORT OLDEST FIRST
        new_messages.sort(key=lambda x: x['id'])

        newly_sent = 0
        for msg in new_messages:
            msg_id = msg['id']
            original_text = msg['text']
            coded = encode_message(original_text, ENCRYPTION_KEY)
            send_rubika_message(RUBIKA_USER_ID, coded)
            sent_ids.add(msg_id)
            newly_sent += 1
            time.sleep(0.5)

        if newly_sent > 0:
            save_sent_ids(sent_ids)
            git_commit_push(SENT_IDS_FILE, f"Add {newly_sent} new sent messages (up to {max(sent_ids)})")
        else:
            print("📭 No new messages this round.", flush=True)

        elapsed = time.time() - loop_start.timestamp()
        sleep_time = max(0, 300 - elapsed)
        if sleep_time > 0:
            print(f"⏳ Waiting {sleep_time:.0f} seconds until next iteration", flush=True)
            time.sleep(sleep_time)

    print("\n🏁 6-hour runtime completed.\n", flush=True)

if __name__ == "__main__":
    main()
