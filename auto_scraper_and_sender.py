#!/usr/bin/env python3
import sys
import os

sys.stdout.reconfigure(line_buffering=True)

print("=== AUTO SCRAPER STARTING ===", flush=True)

try:
    import traceback
    import time
    import re
    import requests
    from bs4 import BeautifulSoup
    from datetime import datetime
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader
    import arabic_reshaper
    from bidi.algorithm import get_display
    print("All modules imported successfully.", flush=True)
except Exception as e:
    print(f"IMPORT ERROR: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

# ========== CONFIGURATION ==========
CHANNEL = os.getenv('CHANNEL', 'IranintlTV')
MAX_MESSAGES = 100

# ✅ YOUR CORRECT CHAT_ID (from the test)
RUBIKA_USER_ID = "b0JWE2R0bQW0eae5690fa217ebebf122"

RUBIKA_TOKEN = os.environ.get("RUBIKA_TOKEN", "")
if not RUBIKA_TOKEN:
    print("❌ FATAL: RUBIKA_TOKEN environment variable not set.", flush=True)
    sys.exit(1)

print(f"Token present: YES, CHANNEL: {CHANNEL}, USER_ID: {RUBIKA_USER_ID}", flush=True)

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
    except Exception as e:
        print(f"  ⚠️ Reshaping error: {e}")
        return text

def fetch_messages():
    print(f"📡 Fetching up to {MAX_MESSAGES} messages from @{CHANNEL}...", flush=True)
    url = f"https://t.me/s/{CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        print("  ✅ HTTP request successful", flush=True)
    except Exception as e:
        print(f"  ❌ HTTP error: {e}", flush=True)
        raise

    soup = BeautifulSoup(resp.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message')
    print(f"  📄 Found {len(messages)} message blocks on page", flush=True)
    if not messages:
        return []

    posts = []
    for idx, msg in enumerate(messages[:MAX_MESSAGES]):
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
        if idx < 3:
            print(f"  - Post {post_id}: {text[:50]}...", flush=True)
    print(f"  ✅ Collected {len(posts)} posts", flush=True)
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
        print(f"  🖼️ Image {filename} already cached", flush=True)
        return filepath
    try:
        r = requests.get(img_url, timeout=10)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            print(f"  🖼️ Downloaded image {filename}", flush=True)
            return filepath
    except Exception as e:
        print(f"  ⚠️ Image download error: {e}", flush=True)
    return None

def generate_pdf(posts, filename="telegram_archive.pdf"):
    print(f"📄 Generating PDF with {len(posts)} posts...", flush=True)
    try:
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4
        pdfmetrics.registerFont(TTFont('DejaVu', SYSTEM_FONT_PATH))
        c.setFont('DejaVu', 10)
        margin = 20
        y = height - margin
        line_height = 14

        c.setFont('DejaVu', 16)
        title = reshape_persian_text(f"Telegram Channel: @{CHANNEL}")
        c.drawString(margin, y, title)
        y -= line_height + 5
        c.setFont('DejaVu', 10)
        date_str = reshape_persian_text(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(margin, y, date_str)
        y -= line_height * 2

        for p in posts:
            date_text = p.get('date') or "Date unknown"
            date_text = reshape_persian_text(date_text)
            c.setFont('DejaVu', 9)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(margin, y, date_text)
            y -= line_height
            c.setFillColorRGB(0, 0, 0)

            c.setFont('DejaVu', 11)
            text_content = p.get('text', '')
            if text_content:
                reshaped = reshape_persian_text(text_content)
                words = reshaped.split()
                line = ""
                for word in words:
                    test_line = line + (" " + word if line else word)
                    if c.stringWidth(test_line, 'DejaVu', 11) < width - 2*margin:
                        line = test_line
                    else:
                        if y - line_height < margin:
                            c.showPage()
                            y = height - margin
                            c.setFont('DejaVu', 11)
                        c.drawString(margin, y, line)
                        y -= line_height
                        line = word
                if line:
                    if y - line_height < margin:
                        c.showPage()
                        y = height - margin
                        c.setFont('DejaVu', 11)
                    c.drawString(margin, y, line)
                    y -= line_height
            y -= 4

            if p.get('img_local'):
                try:
                    img = ImageReader(p['img_local'])
                    img_width, img_height = img.getSize()
                    max_width = width - 2*margin
                    scale = max_width / img_width
                    draw_height = img_height * scale
                    if y - draw_height < margin:
                        c.showPage()
                        y = height - margin
                    c.drawImage(img, margin, y - draw_height, width=max_width, height=draw_height, preserveAspectRatio=True)
                    y -= draw_height + 5
                except Exception as e:
                    print(f"  ⚠️ Could not embed image: {e}", flush=True)

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

            if y < margin:
                c.showPage()
                y = height - margin
                c.setFont('DejaVu', 11)

        c.save()
        print(f"  ✅ PDF saved: {filename}", flush=True)
        return filename
    except Exception as e:
        print(f"  ❌ PDF generation failed: {e}", flush=True)
        traceback.print_exc()
        raise

def send_rubika_document(chat_id, file_bytes, filename):
    print(f"📤 Sending PDF to chat_id {chat_id}...", flush=True)
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
        print(f"  ❌ Send document error: {e}", flush=True)
        traceback.print_exc()
        return False

def send_rubika_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
        print(f"  📨 Sent status message: {text[:50]}", flush=True)
    except Exception as e:
        print(f"  ⚠️ Could not send status message: {e}", flush=True)

def main():
    print("="*60, flush=True)
    print("🤖 AUTO SCRAPER & SENDER STARTED", flush=True)
    print(f"Channel: @{CHANNEL}", flush=True)
    print(f"Max messages per PDF: {MAX_MESSAGES}", flush=True)
    print(f"Target Rubika chat_id: {RUBIKA_USER_ID}", flush=True)
    print(f"Token present: {'YES' if RUBIKA_TOKEN else 'NO'}", flush=True)
    if not RUBIKA_TOKEN:
        print("❌ Missing RUBIKA_TOKEN. Exiting.", flush=True)
        sys.exit(1)
    print("="*60, flush=True)

    start_time = time.time()
    MAX_RUNTIME = 5.9 * 3600
    iteration = 0

    while time.time() - start_time < MAX_RUNTIME:
        iteration += 1
        loop_start = datetime.now()
        print(f"\n{'='*60}", flush=True)
        print(f"🔄 ITERATION {iteration} at {loop_start.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"   Runtime so far: {(time.time() - start_time)/3600:.2f} hours", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            posts = fetch_messages()
            if not posts:
                print("⚠️ No posts retrieved. Skipping this iteration.", flush=True)
            else:
                print("🖼️ Downloading images...", flush=True)
                for p in posts:
                    p['img_local'] = download_image(p['img_url'], p['id'])

                pdf_file = generate_pdf(posts, "telegram_archive.pdf")
                with open(pdf_file, 'rb') as f:
                    pdf_bytes = f.read()
                success = send_rubika_document(RUBIKA_USER_ID, pdf_bytes, "telegram_archive.pdf")
                if success:
                    send_rubika_message(RUBIKA_USER_ID, f"✅ New PDF sent ({len(posts)} posts)")
                else:
                    send_rubika_message(RUBIKA_USER_ID, "❌ Failed to send PDF")
        except Exception as e:
            print("💥 CRITICAL ERROR IN ITERATION:", flush=True)
            traceback.print_exc()
            send_rubika_message(RUBIKA_USER_ID, f"⚠️ Scraper error: {str(e)[:100]}")

        elapsed = time.time() - loop_start.timestamp()
        # Wait 30 seconds between iterations
        sleep_time = max(0, 60 - elapsed)
        if sleep_time > 0:
            print(f"⏳ Waiting {sleep_time:.1f} seconds until next iteration...", flush=True)
            time.sleep(sleep_time)
        else:
            print("⚠️ Iteration took longer than 30 seconds, starting next immediately.", flush=True)

    print("\n" + "="*60, flush=True)
    print("🏁 6-hour runtime completed. Exiting gracefully.", flush=True)
    print("="*60, flush=True)

if __name__ == "__main__":
    main()
