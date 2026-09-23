import time
import requests
import sqlite3

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8218359551:AAFXGZTkEqqid-bu56kxGngqCZ6SggWfPSo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DB_NAME = "bot_data.db"

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==================== HELPER FUNCTIONS ====================
def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

def approve_join_request(chat_id, user_id):
    url = f"{BASE_URL}/approveChatJoinRequest"
    payload = {
        "chat_id": chat_id,
        "user_id": user_id
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        print(f"Error approving request: {e}")
        return False

# ==================== MAIN BOT LOOP ====================
def main():
    print("🤖 Bot is starting via Pure HTTP Polling...")
    offset = 0

    # Fetch Bot Username
    bot_info = requests.get(f"{BASE_URL}/getMe").json()
    bot_username = bot_info.get("result", {}).get("username", "GroupzoneAutoAcceptBot")

    while True:
        try:
            response = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=25)
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # Handle /start Command
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        if msg["text"].startswith("/start"):
                            user_id = msg["from"]["id"]
                            first_name = msg["from"].get("first_name", "User")
                            username = msg["from"].get("username", "")

                            # Save to DB
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                                (user_id, username, first_name)
                            )
                            conn.commit()
                            conn.close()

                            welcome_text = (
                                f"👋 **Hello, {first_name}!**\n\n"
                                "Welcome to **Groupzone Auto Accept Bot**! 🤖\n"
                                "I can automatically approve pending join requests for your Telegram Channels and Groups instantly.\n\n"
                                "⚠️ **Required Permissions:**\n"
                                "1. Invite Users via Link\n"
                                "2. Add New Admins (optional)\n"
                                "3. Manage Chat/Channel\n\n"
                                "Add me as an Admin in your Group or Channel to get started!"
                            )

                            keyboard = {
                                "inline_keyboard": [
                                    [
                                        {"text": "➕ Add to Channel", "url": f"https://t.me/{bot_username}?startchannel=true"},
                                        {"text": "➕ Add to Group", "url": f"https://t.me/{bot_username}?startgroup=true"}
                                    ],
                                    [
                                        {"text": "📞 Contact Admin", "url": "https://t.me/Kawser"}
                                    ]
                                ]
                            }

                            send_message(user_id, welcome_text, keyboard)

                    # Handle Auto Join Requests
                    if "chat_join_request" in update:
                        req = update["chat_join_request"]
                        chat_id = req["chat"]["id"]
                        chat_title = req["chat"].get("title", "Private Chat")
                        user_id = req["from"]["id"]

                        if approve_join_request(chat_id, user_id):
                            # Save Chat to DB
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT OR IGNORE INTO chats (chat_id, chat_title) VALUES (?, ?)",
                                (chat_id, chat_title)
                            )
                            conn.commit()
                            conn.close()

                            # Notify User
                            welcome_msg = (
                                f"🎉 **Your request to join '{chat_title}' has been approved!**\n\n"
                                "Welcome to the community!"
                            )
                            send_message(user_id, welcome_msg)

        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
