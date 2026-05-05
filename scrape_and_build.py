import os
import re
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime

CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
OUTPUT_DIR = 'output'
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

STATE_FILE = 'last_id.txt'
POSTS_FILE = os.path.join(OUTPUT_DIR, 'posts.json')

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_state(last_id):
    with open(STATE_FILE, 'w') as f:
        f.write(str(last_id))

def load_posts():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_posts(posts_dict):
    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts_dict, f, ensure_ascii=False, indent=2)

def scrape_new_posts():
    url = f"https://t.me/s/{CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message')
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
    # posts are newest first from the page. Reverse to oldest first.
    posts.reverse()
    return posts

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
    except:
        pass
    return None

def build_html(all_posts):
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{CHANNEL} Archive</title>
    <style>
        body {{ font-family: Arial; max-width: 800px; margin: auto; padding: 20px; background: #f0f2f5; }}
        .post {{ background: white; margin-bottom: 20px; padding: 15px; border-radius: 8px; }}
        .post-text {{ font-size: 16px; }}
        .post-image {{ max-width: 100%; margin-top: 10px; }}
        .date {{ color: gray; font-size: 12px; }}
        a {{ color: #1e6f9f; }}
    </style>
</head>
<body>
    <h1>@{CHANNEL}</h1>
    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
    for p in all_posts:
        html += f"""
    <div class="post">
        <div class="date">{p.get('date', p['id'])}</div>
        <div class="post-text">{p['text'].replace(chr(10), '<br>')}</div>
"""
        if p.get('img_local'):
            html += f'        <img class="post-image" src="{p["img_local"]}">\n'
        html += f'        <div><a href="{p["link"]}" target="_blank">View on Telegram</a></div>\n'
        html += '    </div>\n'
    html += '</body></html>'
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    print("Scraping...")
    all_posts = scrape_new_posts()
    if not all_posts:
        print("No posts found.")
        return
    last_id = load_state()
    new_posts = [p for p in all_posts if not last_id or p['id'] > last_id]  # simple numeric compare
    if not new_posts:
        print("No new posts.")
        return
    print(f"Found {len(new_posts)} new posts")
    # Load existing posts from JSON
    existing = load_posts()
    for p in new_posts:
        p['img_local'] = download_image(p['img_url'], p['id'])
        existing[p['id']] = p
    save_posts(existing)
    # Build HTML from all posts, sorted by id
    all_sorted = sorted(existing.values(), key=lambda x: int(x['id']))
    build_html(all_sorted)
    # Save state = latest post id
    save_state(all_posts[-1]['id'])
    print("Done.")

if __name__ == '__main__':
    main()
