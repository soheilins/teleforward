import os
import re
import time
import requests
import json
import tarfile
import io
from bs4 import BeautifulSoup
from datetime import datetime
from fpdf import FPDF

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES = 100
OUTPUT_DIR = 'output'
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

PDF_FILE = os.path.join(OUTPUT_DIR, 'telegram_archive.pdf')
POSTS_FILE = os.path.join(OUTPUT_DIR, 'posts.json')

# Reliable working URL for DejaVuSans.ttf
UNICODE_FONT_URL = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf?raw=true"
UNICODE_FONT_FILE = "DejaVuSans.ttf"

def download_unicode_font():
    """Download DejaVuSans.ttf using the raw GitHub URL with proper LFS handling."""
    if os.path.exists(UNICODE_FONT_FILE):
        print("Font already exists locally.")
        return
    
    print("Downloading DejaVuSans.ttf...")
    headers = {"Accept": "application/octet-stream"}
    try:
        response = requests.get(UNICODE_FONT_URL, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Check if it's an LFS pointer file
        content = response.text
        if content.startswith("version https://git-lfs.github.com/spec"):
            print("Detected LFS pointer, fetching actual file...")
            # Extract the URL from the pointer file
            for line in content.split('\n'):
                if line.startswith("oid sha256:"):
                    oid = line.split(":")[1].strip()
                    # Use huggingface CDN which serves LFS files directly
                    lfs_url = f"https://huggingface.co/spaces/pyodide-demo/self-hosted/resolve/main/fonts/DejaVuSans.ttf"
                    response = requests.get(lfs_url, stream=True, timeout=30)
                    response.raise_for_status()
                    break
        
        # Save the font
        with open(UNICODE_FONT_FILE, 'wb') as f:
            f.write(response.content)
        print(f"Font downloaded successfully to {UNICODE_FONT_FILE}")
    except Exception as e:
        print(f"Failed to download font: {e}")
        raise

def fetch_messages_page(before_id=None):
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
        return filepath
    try:
        response = requests.get(img_url, timeout=10)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return filepath
    except Exception as e:
        print(f"Image download failed for {post_id}: {e}")
    return None

def create_pdf(posts):
    # Ensure Unicode font is available
    download_unicode_font()
    
    pdf = FPDF()
    pdf.add_page()
    
    # Register the Unicode TrueType font
    pdf.add_font('DejaVu', '', UNICODE_FONT_FILE, uni=True)
    pdf.set_font('DejaVu', '', 16)
    
    # Title
    pdf.cell(0, 10, f"Telegram Channel: @{CHANNEL}", new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('DejaVu', '', 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(10)
    
    for p in posts:
        # Date
        date_text = p.get('date')
        if date_text is None:
            date_text = "Date unknown"
        pdf.set_font('DejaVu', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, date_text, new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)
        
        # Message text
        pdf.set_font('DejaVu', '', 11)
        text_content = p.get('text', '')
        if text_content:
            pdf.multi_cell(0, 6, text_content)
        pdf.ln(2)
        
        # Image
        if p.get('img_local'):
            try:
                pdf.image(p['img_local'], w=pdf.w - 20)
                pdf.ln(5)
            except Exception as e:
                print(f"Could not embed image for post {p['id']}: {e}")
        
        # Link
        pdf.set_font('DejaVu', '', 8)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 6, f"View original: {p['link']}", new_x='LMARGIN', new_y='NEXT', link=p['link'])
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

    unique = {}
    for p in all_posts:
        unique[p['id']] = p
    sorted_by_id_desc = sorted(unique.values(), key=lambda x: int(x['id']), reverse=True)
    limited_posts = sorted_by_id_desc[:MAX_MESSAGES]
    print(f"Collected {len(limited_posts)} unique posts (latest {MAX_MESSAGES}).")

    for p in limited_posts:
        p['img_local'] = download_image(p['img_url'], p['id'])

    sorted_chrono = sorted(limited_posts, key=lambda x: int(x['id']))
    create_pdf(sorted_chrono)

    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump({p['id']: p for p in limited_posts}, f, ensure_ascii=False, indent=2)
    print("Done.")

if __name__ == "__main__":
    main()
