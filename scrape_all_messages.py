import os
import re
import time
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import arabic_reshaper
from bidi.algorithm import get_display

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES = 100
OUTPUT_DIR = 'output'
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

PDF_FILE = os.path.join(OUTPUT_DIR, 'telegram_archive.pdf')
POSTS_FILE = os.path.join(OUTPUT_DIR, 'posts.json')

# Path to the pre-installed DejaVu Sans font on GitHub Actions Ubuntu runners
SYSTEM_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def reshape_persian_text(text):
    """Reshape Persian/Arabic text and apply bidi for correct RTL display."""
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        return bidi_text
    except:
        return text

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
        r = requests.get(img_url, timeout=10)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return filepath
    except Exception as e:
        print(f"Image download failed for {post_id}: {e}")
    return None

def create_pdf(posts):
    """Generate PDF with correct RTL Persian/Arabic text using ReportLab."""
    c = canvas.Canvas(PDF_FILE, pagesize=A4)
    width, height = A4
    # Register the Unicode font
    pdfmetrics.registerFont(TTFont('DejaVu', SYSTEM_FONT_PATH))
    c.setFont('DejaVu', 10)
    
    y = height - 20  # start from top
    line_height = 14
    margin = 20
    
    # Title
    c.setFont('DejaVu', 16)
    title = reshape_persian_text(f"Telegram Channel: @{CHANNEL}")
    c.drawString(margin, y, title)
    y -= line_height + 5
    c.setFont('DejaVu', 10)
    date_str = reshape_persian_text(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(margin, y, date_str)
    y -= line_height * 2
    
    for p in posts:
        # Date
        date_text = p.get('date')
        if date_text is None:
            date_text = "Date unknown"
        date_text = reshape_persian_text(date_text)
        c.setFont('DejaVu', 9)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(margin, y, date_text)
        y -= line_height
        c.setFillColorRGB(0, 0, 0)
        
        # Message text (may be multi-line)
        c.setFont('DejaVu', 11)
        text_content = p.get('text', '')
        if text_content:
            reshaped_text = reshape_persian_text(text_content)
            # Split into lines that fit the page width
            lines = []
            current_line = ""
            for word in reshaped_text.split():
                # crude wrapping, but works for RTL because strings are already visual
                test_line = current_line + (" " if current_line else "") + word
                if c.stringWidth(test_line, 'DejaVu', 11) < width - 2*margin:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            for line in lines:
                if y - line_height < margin:
                    c.showPage()
                    c.setFont('DejaVu', 11)
                    y = height - margin
                c.drawString(margin, y, line)
                y -= line_height
        y -= 4  # small gap after text
        
        # Image
        if p.get('img_local'):
            try:
                img = ImageReader(p['img_local'])
                img_width, img_height = img.getSize()
                # Scale image to fit width
                max_width = width - 2*margin
                scale = max_width / img_width
                draw_height = img_height * scale
                if y - draw_height < margin:
                    c.showPage()
                    y = height - margin
                c.drawImage(img, margin, y - draw_height, width=max_width, height=draw_height, preserveAspectRatio=True)
                y -= draw_height + 5
            except Exception as e:
                print(f"Could not embed image for post {p['id']}: {e}")
        
        # Link (English, no reshaping needed)
        link_text = f"View original: {p['link']}"
        c.setFont('DejaVu', 8)
        c.setFillColorRGB(0, 0, 0.8)
        if y - line_height < margin:
            c.showPage()
            y = height - margin
            c.setFont('DejaVu', 8)
        c.drawString(margin, y, link_text)
        y -= line_height + 8
        c.setFillColorRGB(0, 0, 0)
        
        # New page if needed
        if y < margin:
            c.showPage()
            y = height - margin
            c.setFont('DejaVu', 11)
    
    c.save()
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
