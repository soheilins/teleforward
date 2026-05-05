import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ========== CONFIGURATION (from GitHub Secrets) ==========
RUBIKA_TOKEN = os.getenv('RUBIKA_BOT_TOKEN')
RUBIKA_CHAT_ID = os.getenv('RUBIKA_CHAT_ID')
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL', 'IranintlTV')

if not RUBIKA_TOKEN or not RUBIKA_CHAT_ID:
    raise Exception("Missing RUBIKA_BOT_TOKEN or RUBIKA_CHAT_ID")

recipients = [cid.strip() for cid in RUBIKA_CHAT_ID.split(',')]

# ========== RUBIKA SEND MESSAGE ==========
SEND_MESSAGE_URL = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}/sendMessage"

def send_rubika_message(chat_id, text):
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

# ========== SCRAPE TELEGRAM CHANNEL ==========
def fetch_new_posts():
    url = f"https://t.me/s/{TELEGRAM_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message')
    
    last_id = get_last_id()
    new_posts = []
    
    for msg in messages:
        data_post = msg.get('data-post')
        if not data_post:
            continue
        # data-post format: "channel_username/12345"
        post_id = data_post.split('/')[-1]
        if last_id and post_id == last_id:
            break
        
        # Extract text
        text_div = msg.find('div', class_='tgme_widget_message_text')
        text = text_div.get_text(strip=True) if text_div else ''
        
        # Extract link
        link = f"https://t.me/{data_post}"
        
        new_posts.append({
            'id': post_id,
            'text': text,
            'link': link
        })
    
    # Reverse to get oldest first
    new_posts.reverse()
    return new_posts

def format_message(post):
    text = post['text']
    if len(text) > 3000:
        text = text[:3000] + '...'
    msg = f"📢 <b>New from {TELEGRAM_CHANNEL}</b>\n\n{text}\n\n🔗 <a href='{post['link']}'>View original</a>"
    return msg

def main():
    print(f"Scraping channel: @{TELEGRAM_CHANNEL}")
    try:
        posts = fetch_new_posts()
    except Exception as e:
        print(f"Scraping failed: {e}")
        return
    
    if not posts:
        print("No new posts.")
        return
    
    for post in posts:
        message_text = format_message(post)
        for chat_id in recipients:
            send_rubika_message(chat_id, message_text)
            print(f"Sent to {chat_id}: {post['link']}")
        # Update state after each post (optional, but safe)
        set_last_id(post['id'])
    
    print(f"Done. Last ID: {posts[-1]['id']}")

if __name__ == "__main__":
    main()
