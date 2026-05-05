import os
import pickle
import requests
from bs4 import BeautifulSoup

# ========== CONFIGURATION ==========
RUBIKA_TOKEN = os.getenv('RUBIKA_BOT_TOKEN')
RUBIKA_CHAT_ID = os.getenv('RUBIKA_CHAT_ID')
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL', 'IranintlTV')

recipients = [cid.strip() for cid in RUBIKA_CHAT_ID.split(',')]

# ========== RUBIKA SEND ==========
SEND_MESSAGE_URL = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}/sendMessage"

def send_rubika_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(SEND_MESSAGE_URL, json=payload, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

# ========== STATE USING FILE (not cached by Actions) ==========
STATE_FILE = "last_id.txt"

def get_last_id():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    return None

def set_last_id(post_id):
    with open(STATE_FILE, 'w') as f:
        f.write(str(post_id))

# ========== SCRAPER ==========
def fetch_new_posts():
    url = f"https://t.me/s/{TELEGRAM_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0"}
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
        post_id = data_post.split('/')[-1]
        if last_id and post_id == last_id:
            break
        text_div = msg.find('div', class_='tgme_widget_message_text')
        text = text_div.get_text(strip=True) if text_div else ''
        link = f"https://t.me/{data_post}"
        new_posts.append({'id': post_id, 'text': text, 'link': link})
    
    new_posts.reverse()
    return new_posts

def main():
    print(f"Scraping @{TELEGRAM_CHANNEL}")
    try:
        posts = fetch_new_posts()
    except Exception as e:
        print(f"Failed: {e}")
        return
    
    if not posts:
        print("No new posts.")
        return
    
    for post in posts:
        text = post['text'][:3000]
        msg = f"📢 <b>New from {TELEGRAM_CHANNEL}</b>\n\n{text}\n\n🔗 <a href='{post['link']}'>View</a>"
        for cid in recipients:
            send_rubika_message(cid, msg)
            print(f"Sent to {cid}: {post['link']}")
        set_last_id(post['id'])
    
    print(f"Done. Last ID: {posts[-1]['id']}")

if __name__ == "__main__":
    main()
