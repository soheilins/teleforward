#!/usr/bin/env python3
import sys
import os
import time
import re
import requests
import traceback
from bs4 import BeautifulSoup
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import arabic_reshaper
from bidi.algorithm import get_display

sys.stdout.reconfigure(line_buffering=True)

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES = 40
SORT_OLDEST_FIRST = True               # True = oldest first
RUBIKA_USER_ID = "b0JWE2R0bQW0eae5690fa217ebebf122"
RUBIKA_TOKEN = os.environ.get("RUBIKA_TOKEN", "")

if not RUBIKA_TOKEN:
    print("❌ RUBIKA_TOKEN not set", flush=True)
    sys.exit(1)

BASE_API = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}"
SEND_MESSAGE_URL = f"{BASE_API}/sendMessage"
REQUEST_SEND_FILE_URL = f"{BASE_API}/requestSendFile"
SEND_FILE_URL = f"{BASE_API}/sendFile"

OUTPUT_DIR = 'output'
IMAGES_DIR = os.path.join(OUTPUT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)
SYSTEM_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def reshape_persian_text(text):
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

def fetch_messages():
    print(f"📡 Fetching up to {MAX_MESSAGES} messages from @{CHANNEL}...", flush=True)
    all_posts = []
    oldest_id = None
    page_count = 0

    while len(all_posts) < MAX_MESSAGES:
        page_count += 1
        url = f"https://t.me/s/{CHANNEL}"
        if oldest_id:
            url += f"?before={oldest_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=30)  # increased timeout
            resp.raise_for_status()
        except Exception as e:
            print(f"  ❌ HTTP error on page {page_count}: {e}", flush=True)
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message')
        if not messages:
            print(f"  ⚠️ No messages on page {page_count}, stopping.", flush=True)
            break

        print(f"  📄 Page {page_count}: {len(messages)} messages", flush=True)
        page_posts = []
        for msg in messages:
            data_post = msg.get('data-post')
            if not data_post:
                continue
            post_id = int(data_post.split('/')[-1])
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
            page_posts.append({
                'id': post_id,
                'text': text,
                'date': date_str,
                'img_url': img_url,
                'link': link
            })

        if page_posts:
            oldest_id = min(p['id'] for p in page_posts)
            all_posts.extend(page_posts)
            print(f"  ➕ Added {len(page_posts)} (total {len(all_posts)})", flush=True)
        else:
            break
        time.sleep(1)

    if len(all_posts) > MAX_MESSAGES:
        all_posts = all_posts[:MAX_MESSAGES]

    if SORT_OLDEST_FIRST:
        all_posts.sort(key=lambda x: x['id'])
        print("  🔄 Sorted oldest first", flush=True)
    else:
        print("  🔄 Keeping newest first", flush=True)

    print(f"  ✅ Final: {len(all_posts)} posts", flush=True)
    return all_posts

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
            print(f"  🖼️ Downloaded {filename}", flush=True)
            return filepath
    except Exception as e:
        print(f"  ⚠️ Image error: {e}", flush=True)
    return None

def generate_pdf(posts, filename="telegram_archive.pdf"):
    print(f"📄 Generating PDF with {len(posts)} posts...", flush=True)
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    pdfmetrics.registerFont(TTFont('DejaVu', SYSTEM_FONT_PATH))
    margin = 20
    line_height = 14
    text_width = width - 2 * margin
    y = height - margin

    def draw_text(text, font_size, is_date=False, link=None):
        nonlocal y
        if is_date:
            c.setFont('DejaVu', 9)
            c.setFillColorRGB(0.4, 0.4, 0.4)
        else:
            c.setFont('DejaVu', font_size)
            c.setFillColorRGB(0, 0, 0)
        if not text:
            return
        words = text.split()
        line = ""
        for word in words:
            test_line = line + (" " + word if line else word)
            if c.stringWidth(test_line, 'DejaVu', font_size) < text_width:
                line = test_line
            else:
                if y - line_height < margin:
                    c.showPage()
                    y = height - margin
                    if is_date:
                        c.setFont('DejaVu', 9)
                        c.setFillColorRGB(0.4, 0.4, 0.4)
                    else:
                        c.setFont('DejaVu', font_size)
                        c.setFillColorRGB(0, 0, 0)
                if link:
                    c.linkURL(link, (margin, y - line_height, margin + c.stringWidth(line, 'DejaVu', font_size), y), relative=1)
                c.drawString(margin, y, line)
                y -= line_height
                line = word
        if line:
            if y - line_height < margin:
                c.showPage()
                y = height - margin
                if is_date:
                    c.setFont('DejaVu', 9)
                    c.setFillColorRGB(0.4, 0.4, 0.4)
                else:
                    c.setFont('DejaVu', font_size)
                    c.setFillColorRGB(0, 0, 0)
            if link:
                c.linkURL(link, (margin, y - line_height, margin + c.stringWidth(line, 'DejaVu', font_size), y), relative=1)
            c.drawString(margin, y, line)
            y -= line_height
        y -= 4

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
        date_text = p.get('date') or "Date unknown"
        date_text = reshape_persian_text(date_text)
        draw_text(date_text, 9, is_date=True)

        # Message text
        text_content = p.get('text', '')
        if text_content:
            reshaped = reshape_persian_text(text_content)
            draw_text(reshaped, 11, is_date=False)

        # Image
        if p.get('img_local'):
            try:
                img = ImageReader(p['img_local'])
                img_width, img_height = img.getSize()
                max_width = text_width
                scale = max_width / img_width
                draw_height = img_height * scale
                if y - draw_height < margin:
                    c.showPage()
                    y = height - margin
                c.drawImage(img, margin, y - draw_height, width=max_width, height=draw_height, preserveAspectRatio=True)
                y -= draw_height + 5
            except Exception as e:
                print(f"  ⚠️ Image embed error: {e}", flush=True)

        # Link
        link_text = f"View original: {p['link']}"
        c.setFont('DejaVu', 8)
        c.setFillColorRGB(0, 0, 0.8)
        if y - line_height < margin:
            c.showPage()
            y = height - margin
        c.drawString(margin, y, link_text)
        y -= line_height + 8

        if y < margin:
            c.showPage()
            y = height - margin

    c.save()
    print(f"  ✅ PDF saved: {filename}", flush=True)
    return filename

def send_rubika_document(chat_id, file_bytes, filename):
    print(f"📤 Sending PDF to {chat_id}...", flush=True)
    try:
        req_payload = {"type": "File"}
        resp = requests.post(REQUEST_SEND_FILE_URL, json=req_payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            print(f"  ❌ requestSendFile error: {data}", flush=True)
            return False
        upload_url = data["data"]["upload_url"]
        print("  ✅ Upload URL received", flush=True)

        files = {"file": (filename, file_bytes, "application/pdf")}
        upload_resp = requests.post(upload_url, files=files, timeout=30)
        upload_resp.raise_for_status()
        upload_result = upload_resp.json()
        if upload_result.get("status") != "OK":
            print(f"  ❌ Upload error: {upload_result}", flush=True)
            return False
        file_id = upload_result["data"]["file_id"]
        print(f"  ✅ PDF uploaded, file_id={file_id}", flush=True)

        send_payload = {
            "chat_id": chat_id,
            "file_id": file_id,
            "text": f"📄 {filename}"
        }
        send_resp = requests.post(SEND_FILE_URL, json=send_payload, timeout=15)
        send_resp.raise_for_status()
        print("  ✅ PDF successfully sent to Rubika", flush=True)
        return True
    except Exception as e:
        print(f"  ❌ Send error: {e}", flush=True)
        return False

def send_rubika_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
        print(f"  📨 Sent: {text[:50]}", flush=True)
    except Exception as e:
        print(f"  ⚠️ Message send error: {e}", flush=True)

def main():
    print("="*60, flush=True)
    print("🤖 AUTO SCRAPER & SENDER STARTED", flush=True)
    print(f"Channel: @{CHANNEL}", flush=True)
    print(f"Max messages: {MAX_MESSAGES}", flush=True)
    print(f"Target chat_id: {RUBIKA_USER_ID}", flush=True)
    print("="*60, flush=True)

    start_time = time.time()
    MAX_RUNTIME = 5.9 * 3600
    iteration = 0

    while time.time() - start_time < MAX_RUNTIME:
        iteration += 1
        loop_start = datetime.now()
        print(f"\n{'='*60}", flush=True)
        print(f"🔄 ITERATION {iteration} at {loop_start.strftime('%H:%M:%S')}", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            posts = fetch_messages()
            if not posts:
                print("⚠️ No posts retrieved.", flush=True)
            else:
                for p in posts:
                    p['img_local'] = download_image(p['img_url'], p['id'])
                pdf_file = generate_pdf(posts, "telegram_archive.pdf")
                with open(pdf_file, 'rb') as f:
                    pdf_bytes = f.read()
                success = send_rubika_document(RUBIKA_USER_ID, pdf_bytes, "telegram_archive.pdf")
                if success:
                    send_rubika_message(RUBIKA_USER_ID, f"✅ PDF sent ({len(posts)} posts)")
                else:
                    send_rubika_message(RUBIKA_USER_ID, "❌ PDF send failed")
        except Exception as e:
            print("💥 ERROR:", flush=True)
            traceback.print_exc()
            send_rubika_message(RUBIKA_USER_ID, f"⚠️ Scraper error: {str(e)[:100]}")

        elapsed = time.time() - loop_start.timestamp()
        sleep_time = max(0, 600 - elapsed)
        if sleep_time > 0:
            print(f"⏳ Waiting {sleep_time:.1f}s", flush=True)
            time.sleep(sleep_time)

    print("\n🏁 6-hour runtime completed.\n", flush=True)

if __name__ == "__main__":
    main()
