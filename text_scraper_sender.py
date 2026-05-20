import requests
from bs4 import BeautifulSoup

CHANNEL = "IranintlTV"
url = f"https://t.me/s/{CHANNEL}"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
soup = BeautifulSoup(resp.text, 'html.parser')
messages = soup.find_all('div', class_='tgme_widget_message')

print(f"Found {len(messages)} message divs\n")
for idx, msg in enumerate(messages):
    data_post = msg.get('data-post')
    if not data_post:
        print(f"{idx}: No data-post")
        continue
    post_id = int(data_post.split('/')[-1])
    text_div = msg.find('div', class_='tgme_widget_message_text')
    has_text = text_div is not None
    print(f"{idx}: ID={post_id}, has_text={has_text}")
    if has_text:
        print(f"    Text preview: {text_div.get_text(strip=True)[:80]}...")
    print()
