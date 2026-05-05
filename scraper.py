import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def fetch_latest_posts(channel, last_id=0):
    url = f"https://t.me/s/{channel}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    posts = []
    # Each message is inside a div with class 'tgme_widget_message'
    for msg_div in soup.find_all('div', class_='tgme_widget_message'):
        # Extract message ID (data-post attribute)
        data_post = msg_div.get('data-post')
        if not data_post:
            continue
        # data-post format: "channel_username/12345"
        msg_id = int(data_post.split('/')[-1])

        # Skip if already processed
        if msg_id <= last_id:
            continue

        # Extract text
        text_div = msg_div.find('div', class_='tgme_widget_message_text')
        text = text_div.get_text(strip=True) if text_div else ''

        # Extract media URLs (images, videos, documents)
        media_urls = []
        # Photos: <a class="tgme_widget_message_photo_wrap" href="...">
        for photo in msg_div.find_all('a', class_='tgme_widget_message_photo_wrap'):
            href = photo.get('href')
            if href:
                media_urls.append(href)
        # Videos: <video> tag with src
        for video in msg_div.find_all('video'):
            src = video.get('src')
            if src:
                media_urls.append(urljoin('https://t.me', src))
        # Documents: <a class="tgme_widget_message_document_wrap" href="...">
        for doc in msg_div.find_all('a', class_='tgme_widget_message_document_wrap'):
            href = doc.get('href')
            if href:
                media_urls.append(href)

        posts.append({
            'id': msg_id,
            'text': text,
            'media': media_urls,
            'link': f"https://t.me/{channel}/{msg_id}"
        })

    # Sort by msg_id ascending (oldest first)
    posts.sort(key=lambda x: x['id'])
    return posts

def send_to_rubika(bot_token, chat_id, text, media_urls):
    # Send text first (with link)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Text message sent -> {r.status_code}")
    except Exception as e:
        print(f"Failed to send text: {e}")

    # For each media URL, send as a separate message (Rubika bot API via Telegram API style)
    for media_url in media_urls:
        # If it's a photo
        if 'photo' in media_url or media_url.endswith(('.jpg', '.png', '.jpeg', '.webp')):
            send_photo_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            try:
                r = requests.post(send_photo_url, data={'chat_id': chat_id, 'photo': media_url}, timeout=15)
                print(f"Photo sent -> {r.status_code}")
            except Exception as e:
                print(f"Failed to send photo: {e}")
        # If it's a video
        elif 'video' in media_url or media_url.endswith(('.mp4', '.mov', '.mkv')):
            send_video_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
            try:
                r = requests.post(send_video_url, data={'chat_id': chat_id, 'video': media_url}, timeout=30)
                print(f"Video sent -> {r.status_code}")
            except Exception as e:
                print(f"Failed to send video: {e}")
        # Otherwise send as document
        else:
            send_doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            try:
                r = requests.post(send_doc_url, data={'chat_id': chat_id, 'document': media_url}, timeout=20)
                print(f"Document sent -> {r.status_code}")
            except Exception as e:
                print(f"Failed to send document: {e}")

def main():
    channel = os.getenv('TELEGRAM_CHANNEL')
    rubika_token = os.getenv('RUBIKA_BOT_TOKEN')
    recipients_str = os.getenv('RUBIKA_RECIPIENTS')
    if not recipients_str:
        print("No recipients")
        return
    recipients = [r.strip() for r in recipients_str.split(',')]

    # Read last processed message ID
    state_file = 'last_msg_id.txt'
    last_id = 0
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            last_id = int(f.read().strip())

    # Fetch posts
    print(f"Fetching from https://t.me/s/{channel}")
    posts = fetch_latest_posts(channel, last_id)

    if not posts:
        print("No new posts.")
        return

    print(f"Found {len(posts)} new posts.")

    # For each post, send to each recipient
    for post in posts:
        # Prepare message text
        msg_text = f"📢 <b>New from {channel}</b>\n\n{post['text'][:3000]}\n\n🔗 <a href='{post['link']}'>Original</a>"
        for uid in recipients:
            send_to_rubika(rubika_token, uid, msg_text, post['media'])

        # Update last_id to this post's id
        last_id = max(last_id, post['id'])

    # Save updated state
    with open(state_file, 'w') as f:
        f.write(str(last_id))
    print(f"Saved last_id = {last_id}")

if __name__ == '__main__':
    import os
    main()
