import os
import re
import time
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES = 100               # 👈 Change this to how many you want (e.g., 100)
OUTPUT_DIR = 'output'
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

POSTS_FILE = os.path.join(OUTPUT_DIR, 'posts.json')

def fetch_messages_page(before_id=None):
    """Fetch one page of messages. If before_id is given, use ?before=..."""
    url = f"https://t.me/s/{CHANNEL}"
    if before_id:
        url += f"?before={before_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message')
    if not messages:
        return []
    posts = []
    for msg in messages:
        data_post = msg.get('data-post')
        if not data_post:
            continue
        post_id = data_post.split('/')[-1]
        text_div = msg.find('div', class_='tgme_widget_message_text')
        text = text_div.get_text(strip=True) if text_div else ''
        date_div = msg.find('time', class_='datetime')
        date_str = date_div.get('datetime') if date_div else None
        # image
        img_url = None
        photo = msg.find('a', class_='tgme_widget_message_photo_wrap')
        if photo:
            style = photo.get('style', '')
            match = re.search(r'background-image:url\(\'(.*?)\'\)', style)
            if match:
                img_url = match.group(1)
        link = f"https://t.me/{data_post}"
        posts.append({
            'id': post_id,
            'text': text,
            'date': date_str,
            'img_url': img_url,
            'link': link
        })
    return posts   # newest first on the page

def download_image(img_url, post_id):
    if not img_url:
        return None
    ext = '.jpg'
    if '?' in img_url:
        img_url = img_url.split('?')[0]
    if img_url.endswith('.webp'):
        ext = '.webp'
    filename = f"{post_id}{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(filepath):
        return f"images/{filename}"
    try:
        r = requests.get(img_url, timeout=10)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return f"images/{filename}"
    except Exception as e:
        print(f"Image download failed for {post_id}: {e}")
    return None

def build_html(all_posts_sorted):
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{CHANNEL} – Latest {len(all_posts_sorted)} Posts</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; background: #f0f2f5; }}
        .post {{ background: white; margin-bottom: 20px; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .post-text {{ font-size: 16px; line-height: 1.5; }}
        .post-image {{ max-width: 100%; margin-top: 10px; border-radius: 4px; }}
        .date {{ color: #666; font-size: 12px; margin-bottom: 5px; }}
        hr {{ border: none; border-top: 1px solid #ddd; }}
        a {{ color: #1e6f9f; }}
    </style>
</head>
<body>
    <h1>📡 @{CHANNEL} – Latest {len(all_posts_sorted)} Posts</h1>
    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <hr>
"""
    for p in all_posts_sorted:
        html += f"""
    <div class="post">
        <div class="date">{p.get('date', p['id'])}</div>
        <div class="post-text">{p['text'].replace(chr(10), '<br>')}</div>
"""
        if p.get('img_local'):
            html += f'        <img class="post-image" src="{p["img_local"]}" alt="image">\n'
        html += f'        <div><a href="{p["link"]}" target="_blank">View on Telegram</a></div>\n'
        html += '    </div>\n'
    html += '</body></html>'
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML built with {len(all_posts_sorted)} posts.")

def main():
    print(f"[{datetime.now()}] Fetching up to {MAX_MESSAGES} latest messages from @{CHANNEL}...")
    all_posts = []           # will hold posts as we fetch them (newest first from each page)
    oldest_id = None
    page_count = 0

    while len(all_posts) < MAX_MESSAGES:
        page_count += 1
        print(f"Fetching page {page_count} (before={oldest_id})...")
        page_posts = fetch_messages_page(before_id=oldest_id)
        if not page_posts:
            print("No more messages available. Stopping.")
            break
        print(f"  Got {len(page_posts)} messages on this page.")
        all_posts.extend(page_posts)
        # Find the oldest message ID in this page (smallest numeric id)
        ids_on_page = [int(p['id']) for p in page_posts]
        if ids_on_page:
            oldest_id = min(ids_on_page)   # for next 'before' request
        else:
            break
        # Stop if we've reached or exceeded the limit (we'll trim later)
        if len(all_posts) >= MAX_MESSAGES:
            print(f"Reached limit of {MAX_MESSAGES} messages.")
            break
        time.sleep(1)   # polite delay

    if not all_posts:
        print("No posts retrieved.")
        return

    # Remove duplicates (shouldn't happen) and limit to MAX_MESSAGES
    unique_posts = {}
    for p in all_posts:
        if p['id'] not in unique_posts:
            unique_posts[p['id']] = p
    # Keep only the latest MAX_MESSAGES (based on ID, larger ID = newer)
    sorted_by_id_desc = sorted(unique_posts.values(), key=lambda x: int(x['id']), reverse=True)
    limited_posts = sorted_by_id_desc[:MAX_MESSAGES]
    print(f"Collected {len(limited_posts)} unique messages (latest {MAX_MESSAGES}).")

    # Download images for the limited posts
    for p in limited_posts:
        p['img_local'] = download_image(p['img_url'], p['id'])

    # Save all posts as JSON (optional)
    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump({p['id']: p for p in limited_posts}, f, ensure_ascii=False, indent=2)

    # Sort by ID (oldest first) for chronological display
    sorted_chrono = sorted(limited_posts, key=lambda x: int(x['id']))
    build_html(sorted_chrono)
    print("Done.")

if __name__ == '__main__':
    main()
