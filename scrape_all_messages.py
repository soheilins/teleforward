import os
import re
import time
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
from fpdf import FPDF
from PIL import Image
import io

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES = 100               # Number of latest messages to include
OUTPUT_DIR = 'output'
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

PDF_FILE = os.path.join(OUTPUT_DIR, 'telegram_archive.pdf')
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
    return posts   # newest first

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
        return filepath
    try:
        r = requests.get(img_url, timeout=10)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return filepath
    except Exception as e:
        print(f"Image download failed for {post_id}: {e}")
    return None

def create_pdf(posts):
    """Generate PDF with all posts (oldest first) and embedded images."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # Title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Telegram Channel: @{CHANNEL}", ln=1, align='C')
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=1, align='C')
    pdf.ln(10)
    
    # Process posts from oldest to newest (they are already sorted)
    for p in posts:
        # Date
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, p.get('date', f"Post ID: {p['id']}"), ln=1)
        pdf.set_text_color(0, 0, 0)
        # Text
        pdf.set_font("Arial", "", 11)
        # MultiCell handles line breaks
        pdf.multi_cell(0, 6, p['text'])
        pdf.ln(2)
        # Image
        if p.get('img_local'):
            try:
                # Resize image if needed (max width 180 mm, keep ratio)
                img_path = p['img_local']
                pdf.image(img_path, w=pdf.w - 20)
                pdf.ln(5)
            except Exception as e:
                print(f"Could not embed image for post {p['id']}: {e}")
        # Link to original
        pdf.set_font("Arial", "U", 8)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 6, f"View original: {p['link']}", ln=1, link=p['link'])
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)
    pdf.output(PDF_FILE)
    print(f"PDF saved: {PDF_FILE}")

def main():
    print(f"[{datetime.now()}] Fetching up to {MAX_MESSAGES} latest messages from @{CHANNEL}...")
    all_posts = []
    oldest_id = None
    page_count = 0

    while len(all_posts) < MAX_MESSAGES:
        page_count += 1
        print(f"Fetching page {page_count} (before={oldest_id})...")
        page_posts = fetch_messages_page(before_id=oldest_id)
        if not page_posts:
            print("No more messages.")
            break
        print(f"  Got {len(page_posts)} messages.")
        all_posts.extend(page_posts)
        ids_on_page = [int(p['id']) for p in page_posts]
        if ids_on_page:
            oldest_id = min(ids_on_page)
        else:
            break
        if len(all_posts) >= MAX_MESSAGES:
            break
        time.sleep(1)

    if not all_posts:
        print("No posts retrieved.")
        return

    # Remove duplicates and keep only the latest MAX_MESSAGES
    unique = {}
    for p in all_posts:
        unique[p['id']] = p
    sorted_by_id_desc = sorted(unique.values(), key=lambda x: int(x['id']), reverse=True)
    limited_posts = sorted_by_id_desc[:MAX_MESSAGES]
    print(f"Collected {len(limited_posts)} unique posts (latest {MAX_MESSAGES}).")

    # Download images for these posts
    for p in limited_posts:
        p['img_local'] = download_image(p['img_url'], p['id'])

    # Sort chronologically (oldest first) for PDF
    sorted_chrono = sorted(limited_posts, key=lambda x: int(x['id']))

    # Generate PDF
    create_pdf(sorted_chrono)

    # Save metadata (optional)
    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump({p['id']: p for p in limited_posts}, f, ensure_ascii=False, indent=2)
    print("Done.")

if __name__ == "__main__":
    main()
