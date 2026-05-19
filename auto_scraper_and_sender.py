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
MAX_MESSAGES_PER_RUN = 50          # fetch up to this many new messages each iteration
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

# ========== Helper Functions ==========
def reshape_persian_text(text):
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

def encode_message(plain_text: str, key: str) -> str:
    """XOR + base64 encoding. Works with Unicode (UTF-8)."""
    plain_bytes = plain_text.encode('utf-8')
    key_bytes = key.encode('utf-8')
    encoded_bytes = bytearray()
    for i, b in enumerate(plain_bytes):
        encoded_bytes.append(b ^ key_bytes[i % len(key_bytes)])
    return base64.b64encode(encoded_bytes).decode('ascii')

def send_rubika_message(chat_id, text):
    """Send a plain text message to Rubika."""
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
    """Pull latest changes to get fresh sent IDs."""
    subprocess.run(["git", "pull", "--ff-only"], check=False)
    print("  🔄 Git pull done", flush=True)

def git_commit_push(file_path, commit_msg):
    """Commit and push changes to the repository."""
    subprocess.run(["git", "add", file_path], check=True)
    # Check if there are changes to commit
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False)
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"  ✅ Committed and pushed {file_path}", flush=True)
    else:
        print("  ℹ️ No changes to commit", flush=True)

def load_sent_ids():
    """Load already sent message IDs from JSON file."""
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get("sent_ids", []))
    return set()

def save_sent_ids(sent_ids):
    """Save sent IDs to JSON file (overwrites)."""
    with open(SENT_IDS_FILE, 'w') as f:
        json.dump({"sent_ids": list(sent_ids)}, f, indent=2)

def fetch_new_messages(last_known_id=None):
    """Fetch messages from Telegram web, return list of dicts (id, text, link)."""
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
            # Stop if we reached already sent messages
            if last_known_id and post_id <= last_known_id:
                # Since we fetch oldest first, we can break entirely
                return all_messages
            text_div = msg.find('div', class_='tgme_widget_message_text')
            text = text_div.get_text(strip=True) if text_div else ''
            if not text:
                continue  # skip messages without text (e.g., pure images)
            link = f"https://t.me/{data_post}"
            page_messages.append({
                'id': post_id,
                'text': text,
                'link': link
            })

        if page_messages:
            # Sort ascending (oldest first) to process from earliest new message
            page_messages.sort(key=lambda x: x['id'])
            oldest_id = min(m['id'] for m in page_messages)
            all_messages.extend(page_messages)
            print(f"  📄 Page {page}: +{len(page_messages)} messages (total {len(all_messages)})", flush=True)
        else:
            break
        time.sleep(1)

    # Limit to MAX_MESSAGES_PER_RUN
    if len(all_messages) > MAX_MESSAGES_PER_RUN:
        all_messages = all_messages[:MAX_MESSAGES_PER_RUN]
    return all_messages

# ========== Main Loop ==========
def main():
    print("="*60, flush=True)
    print("🤖 TEXT SCRAPER & ENCODER STARTED", flush=True)
    print(f"Channel: @{CHANNEL}", flush=True)
    print(f"Target Rubika ID: {RUBIKA_USER_ID}", flush=True)
    print("="*60, flush=True)

    start_time = time.time()
    MAX_RUNTIME = 5.9 * 3600  # almost 6 hours
    iteration = 0

    while time.time() - start_time < MAX_RUNTIME:
        iteration += 1
        loop_start = datetime.now()
        print(f"\n{'='*60}", flush=True)
        print(f"🔄 ITERATION {iteration} at {loop_start.strftime('%H:%M:%S')}", flush=True)
        print(f"{'='*60}", flush=True)

        # 1. Pull latest changes (so we get any sent IDs committed by previous runs)
        git_pull()

        # 2. Load already sent IDs
        sent_ids = load_sent_ids()
        print(f"📋 Already sent messages: {len(sent_ids)}", flush=True)

        # 3. Find the highest ID sent so far (to fetch only newer ones)
        max_sent_id = max(sent_ids) if sent_ids else 0

        # 4. Fetch new messages (only those with ID > max_sent_id)
        new_messages = fetch_new_messages(max_sent_id)
        print(f"🆕 Found {len(new_messages)} new text messages", flush=True)

        # 5. For each new message: encode, send to Rubika, mark as sent
        for msg in new_messages:
            msg_id = msg['id']
            original_text = msg['text']
            # Reshape Persian text for correct display (optional, but keeps original readable in logs)
            reshaped = reshape_persian_text(original_text)
            # Encode the original text using the secret key
            coded = encode_message(original_text, ENCRYPTION_KEY)
            # Optional: include the Telegram link in a separate message or together?
            # We'll send only the coded text to keep it compact.
            send_rubika_message(RUBIKA_USER_ID, coded)
            # Mark as sent
            sent_ids.add(msg_id)
            # Save after each message to avoid losing progress
            save_sent_ids(sent_ids)
            git_commit_push(SENT_IDS_FILE, f"Add sent message {msg_id}")
            time.sleep(0.5)  # slight delay to avoid rate limits

        # 6. If no new messages, just wait
        if not new_messages:
            print("📭 No new messages this round.", flush=True)

        # 7. Wait until 1 hour has passed since loop start
        elapsed = time.time() - loop_start.timestamp()
        sleep_time = max(0, 3600 - elapsed)
        if sleep_time > 0:
            print(f"⏳ Waiting {sleep_time:.0f} seconds until next iteration", flush=True)
            time.sleep(sleep_time)

    print("\n🏁 6-hour runtime completed.\n", flush=True)

if __name__ == "__main__":
    main()
