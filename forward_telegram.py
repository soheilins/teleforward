import os
import re
import requests
import feedparser
from datetime import timezone

# ========== CONFIGURATION (from GitHub Secrets) ==========
RUBIKA_TOKEN = os.getenv('RUBIKA_BOT_TOKEN')
RUBIKA_CHAT_ID = os.getenv('RUBIKA_CHAT_ID')       # single chat ID or comma-separated
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL', 'IranintlTV')

if not RUBIKA_TOKEN or not RUBIKA_CHAT_ID:
    raise Exception("Missing RUBIKA_BOT_TOKEN or RUBIKA_CHAT_ID")

# Support multiple recipients (comma-separated)
recipients = [cid.strip() for cid in RUBIKA_CHAT_ID.split(',')]

# ========== RUBIKA SEND MESSAGE (same as your working bot) ==========
SEND_MESSAGE_URL = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}/sendMessage"

def send_rubika_message(chat_id, text):
    """Send text message to Rubika chat (supports HTML or Markdown)"""
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(SEND_MESSAGE_URL, json=payload, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"Error sending to {chat_id}: {e}")
        return None

# ========== STATE MANAGEMENT ==========
STATE_FILE = "last_post_id.txt"

def get_last_id():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    return None

def set_last_id(post_id):
    with open(STATE_FILE, 'w') as f:
        f.write(str(post_id))

# ========== FETCH RSS FEED ==========
def fetch_new_posts():
    rss_url = f"https://rsshub.app/telegram/channel/{TELEGRAM_CHANNEL}"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        print("No entries found. RSSHub might be down or channel invalid.")
        return []
    
    # Sort by published date (oldest first)
    entries = sorted(feed.entries, key=lambda e: e.get('published_parsed', 0))
    
    last_id = get_last_id()
    new_entries = []
    for entry in entries:
        entry_id = entry.link   # e.g. https://t.me/IranintlTV/1234
        if last_id and entry_id == last_id:
            break
        new_entries.append(entry)
    
    return new_entries

# ========== FORMAT MESSAGE ==========
def format_message(entry):
    title = entry.get('title', '')
    link = entry.link
    summary = entry.get('summary', '')
    # Remove HTML tags from summary
    summary_clean = re.sub('<[^<]+?>', '', summary)
    # Truncate if too long (Rubika limit ~4000)
    if len(summary_clean) > 3000:
        summary_clean = summary_clean[:3000] + '...'
    
    msg = f"📢 <b>New from {TELEGRAM_CHANNEL}</b>\n\n"
    if title:
        msg += f"<b>{title}</b>\n\n"
    if summary_clean:
        msg += f"{summary_clean}\n\n"
    msg += f"🔗 <a href='{link}'>View original</a>"
    return msg

# ========== MAIN ==========
def main():
    print(f"Checking channel: @{TELEGRAM_CHANNEL}")
    new_posts = fetch_new_posts()
    
    if not new_posts:
        print("No new posts.")
        return
    
    # Process from oldest to newest
    for entry in reversed(new_posts):
        message_text = format_message(entry)
        for chat_id in recipients:
            send_rubika_message(chat_id, message_text)
            print(f"Sent to {chat_id}: {entry.link}")
    
    # Update state with the most recent post's link
    latest = new_posts[-1]
    set_last_id(latest.link)
    print(f"Done. Last ID updated to {latest.link}")

if __name__ == "__main__":
    main()
