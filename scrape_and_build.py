import os
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

CHANNEL = os.getenv('TELEGRAM_CHANNEL', 'IranintlTV')
OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

def fetch_posts():
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
        # Get date (if available) – fallback to post_id as timestamp
        date_div = msg.find('time', class_='datetime')
        date_str = date_div.get('datetime') if date_div else None
        # Get image
        img_url = None
        photo = msg.find('a', class_='tgme_widget_message_photo_wrap')
        if photo:
            style = photo.get('style', '')
            match = re.search(r'background-image:url\(\'(.*?)\'\)', style)
            if match:
                img_url = match.group(1)
        posts.append({
            'id': post_id,
            'text': text,
            'date': date_str,
            'img_url': img_url,
            'link': f"https://t.me/{data_post}"
        })
    # Reverse to oldest first
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

def generate_html(posts):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Channel: @{CHANNEL}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: auto; padding: 20px; background: #f0f2f5; }}
        .post {{ background: white; margin-bottom: 20px; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .post-text {{ font-size: 16px; line-height: 1.5; }}
        .post-image {{ max-width: 100%; margin-top: 10px; border-radius: 4px; }}
        .post-link {{ font-size: 12px; color: #888; margin-top: 10px; }}
        hr {{ border: none; border-top: 1px solid #ddd; }}
        .date {{ color: #666; font-size: 12px; margin-bottom: 5px; }}
    </style>
</head>
<body>
    <h1>📡 @{CHANNEL}</h1>
    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
    for post in posts:
        html_content += f"""
    <div class="post">
        <div class="date">{post['date'] or f"Post {post['id']}"}</div>
        <div class="post-text">{post['text'].replace('\n', '<br>')}</div>
"""
        if post['img_local']:
            html_content += f'        <img class="post-image" src="{post["img_local"]}" alt="image">\n'
        html_content += f'        <div class="post-link"><a href="{post["link"]}" target="_blank">View on Telegram</a></div>\n'
        html_content += '    </div>\n'
    
    html_content += '</body></html>'
    index_path = os.path.join(OUTPUT_DIR, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"HTML generated: {index_path}")

def main():
    print("Fetching posts...")
    posts = fetch_posts()
    print(f"Found {len(posts)} posts")
    for p in posts:
        p['img_local'] = download_image(p['img_url'], p['id'])
    generate_html(posts)
    print("Done. Output in 'output' folder.")

if __name__ == '__main__':
    main()
