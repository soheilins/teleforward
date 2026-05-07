import os
import time
import io
import requests
import json

# ========== CONFIGURATION ==========
# Read tokens from environment variables (set in GitHub Secrets)
RUBIKA_TOKEN = os.environ.get("RUBIKA_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_OWNER = "soheilins"
REPO_NAME = "teleforward"
WORKFLOW_FILE = "scrape_and_commit.yml"

AUTHORIZED_USERS = {
    "u0JWE2R02172d15a02bb742a785ac9f8",   # Your Rubika user ID
    # add more if needed
}

# Rubika API endpoints
BASE_API = f"https://botapi.rubika.ir/v3/{RUBIKA_TOKEN}"
GET_UPDATES_URL = f"{BASE_API}/getUpdates"
SEND_MESSAGE_URL = f"{BASE_API}/sendMessage"
REQUEST_SEND_FILE_URL = f"{BASE_API}/requestSendFile"
SEND_FILE_URL = f"{BASE_API}/sendFile"

# GitHub API
GITHUB_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
COMMITS_URL = f"{GITHUB_API}/commits/main"
DISPATCH_URL = f"{GITHUB_API}/actions/workflows/{WORKFLOW_FILE}/dispatches"

# Use a path that will be cached by GitHub Actions
OFFSET_FILE = "rubika_offset.txt"

def load_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_offset(offset):
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(offset))

def send_rubika_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(SEND_MESSAGE_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Send message error: {e}")

def send_rubika_document(chat_id, file_bytes, filename):
    """Send a PDF file to Rubika using the two-step upload process."""
    try:
        # Step 1: Request upload URL
        req_payload = {"type": "File"}
        resp = requests.post(REQUEST_SEND_FILE_URL, json=req_payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            print(f"requestSendFile error: {data}")
            return None
        upload_url = data["data"]["upload_url"]

        # Step 2: Upload the file
        files = {"file": (filename, file_bytes, "application/pdf")}
        upload_resp = requests.post(upload_url, files=files, timeout=30)
        upload_resp.raise_for_status()
        upload_result = upload_resp.json()
        if upload_result.get("status") != "OK":
            print(f"Upload error: {upload_result}")
            return None
        file_id = upload_result["data"]["file_id"]
        print(f"Uploaded {filename}, file_id={file_id}")

        # Step 3: Send the file to chat
        send_payload = {
            "chat_id": chat_id,
            "file_id": file_id,
            "text": f"📄 {filename}"
        }
        send_resp = requests.post(SEND_FILE_URL, json=send_payload, timeout=15)
        send_resp.raise_for_status()
        return send_resp.json()
    except Exception as e:
        print(f"Send document error: {e}")
        return None

def get_last_commit_sha():
    try:
        resp = requests.get(COMMITS_URL, headers={"Authorization": f"token {GITHUB_TOKEN}"})
        resp.raise_for_status()
        return resp.json()["sha"]
    except Exception as e:
        print(f"Failed to get commit SHA: {e}")
        return None

def trigger_workflow():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"ref": "main"}
    try:
        r = requests.post(DISPATCH_URL, json=data, headers=headers)
        return r.status_code == 204
    except Exception as e:
        print(f"Trigger workflow error: {e}")
        return False

def wait_for_new_commit(old_sha, timeout=300, poll_interval=5):
    start = time.time()
    while time.time() - start < timeout:
        new_sha = get_last_commit_sha()
        if new_sha and new_sha != old_sha:
            return new_sha
        time.sleep(poll_interval)
    return None

def download_pdf():
    """Download the PDF from the GitHub repository (raw URL)."""
    pdf_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/output/telegram_archive.pdf"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        resp = requests.get(pdf_url, headers=headers)
        if resp.status_code == 200:
            return io.BytesIO(resp.content)
        else:
            print(f"PDF not found, status {resp.status_code}")
            return None
    except Exception as e:
        print(f"Download PDF error: {e}")
        return None

def main():
    # Check that tokens are present
    if not RUBIKA_TOKEN or RUBIKA_TOKEN == "LRFE":
        print("❌ RUBIKA_TOKEN is not set or invalid")
        return
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN is not set")
        return

    offset_id = load_offset()
    print("🤖 Rubika controller bot started (PDF mode).")
    print(f"Loaded offset: {offset_id}")
    
    # Optional: stop gracefully after 5 hours 50 minutes to avoid being killed mid‑conversation
    start_time = time.time()
    MAX_RUNTIME = 5.83 * 3600  # 5 hours 50 minutes (just under 6h)

    while True:
        # Check if we should shut down before the 6h timeout
        if time.time() - start_time > MAX_RUNTIME:
            print("⏰ Reached 5h50m runtime, exiting gracefully. Will be restarted by cron.")
            break

        try:
            payload = {"limit": 10}
            if offset_id:
                payload["offset_id"] = offset_id
            response = requests.post(GET_UPDATES_URL, json=payload, timeout=15)
            result = response.json()
            if result.get("status") == "OK":
                data = result.get("data", {})
                updates = data.get("updates", [])
                for update in updates:
                    if update.get("type") == "NewMessage":
                        chat_id = update.get("chat_id")
                        msg = update.get("new_message", {})
                        text = msg.get("text", "").strip()
                        sender = msg.get("sender_id", "")
                        if text == "/start":
                            print(f"🆕 /start from: sender={sender}, chat_id={chat_id}")
                        elif text == "/update":
                            if sender not in AUTHORIZED_USERS:
                                print(f"⛔ Unauthorized /update from {sender}")
                                send_rubika_message(chat_id, "⛔ You are not authorized.")
                                continue
                            print(f"✅ Authorized /update from {sender}")
                            send_rubika_message(chat_id, "🔄 Triggering update workflow...")
                            old_sha = get_last_commit_sha()
                            if not old_sha:
                                send_rubika_message(chat_id, "❌ Could not get current commit SHA.")
                                continue
                            if not trigger_workflow():
                                send_rubika_message(chat_id, "❌ Failed to trigger GitHub workflow.")
                                continue
                            send_rubika_message(chat_id, "✅ Workflow triggered. Waiting for completion...")
                            new_sha = wait_for_new_commit(old_sha)
                            if not new_sha:
                                send_rubika_message(chat_id, "❌ Timeout waiting for workflow.")
                                continue
                            send_rubika_message(chat_id, "📥 Downloading PDF...")
                            pdf_data = download_pdf()
                            if pdf_data:
                                send_rubika_document(chat_id, pdf_data.read(), "telegram_archive.pdf")
                                send_rubika_message(chat_id, "✅ PDF sent!")
                            else:
                                send_rubika_message(chat_id, "❌ Could not download PDF.")
                if data.get("next_offset_id"):
                    new_offset = data["next_offset_id"]
                    if new_offset != offset_id:
                        offset_id = new_offset
                        save_offset(offset_id)
                        print(f"Updated offset to {offset_id}")
            else:
                print(f"API error: {result}")
        except Exception as e:
            print(f"Exception: {e}")
        time.sleep(2)

if __name__ == "__main__":
    main()
