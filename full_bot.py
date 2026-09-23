import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# ---------------- Web Server for Render ----------------
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Running Alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"Web server running on port {port}")
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# ---------------- Bot Configuration ----------------
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = 6929905808  # আপনার প্রদত্ত অ্যাডমিন আইডেন্টিটি

# Global Memory Database
user_balance = {}  # টাকা (Taka Wallet)
user_free_quota = {}
user_selected_target = {}

# Admin Dynamic Config
payment_config = {
    "bkash": "017XXXXXXXX",  # ডিফল্ট নাম্বার
    "nagad": "018XXXXXXXX",   # ডিফল্ট নাম্বার
    "rate_per_member": 0.01  # ১০০ মেম্বার = ১ টাকা
}

# Conversation States
WAITING_FOR_AMOUNT, WAITING_FOR_DEPOSIT_AMOUNT, WAITING_FOR_SCREENSHOT, WAITING_FOR_DIGITS = range(4)

# ---------------- Keyboards ----------------
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚡ Approve Requests", callback_data="approve_req")],
        [
            InlineKeyboardButton("➕ Add New Channel", callback_data="add_channel"),
            InlineKeyboardButton("➕ Add New Group", callback_data="add_group"),
        ],
        [
            InlineKeyboardButton("💰 Deposit Money", callback_data="deposit_money"),
            InlineKeyboardButton("📊 Account / Balance", callback_data="account_info"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def deposit_amounts_keyboard():
    keyboard = [
        [InlineKeyboardButton("💵 ২০ টাকা", callback_data="dep_20"), InlineKeyboardButton("💵 ৫০ টাকা", callback_data="dep_50")],
        [InlineKeyboardButton("💵 ১০০ টাকা", callback_data="dep_100"), InlineKeyboardButton("💵 ২০০ টাকা", callback_data="dep_200")],
        [InlineKeyboardButton("💵 ৫০০ টাকা", callback_data="dep_500")],
        [InlineKeyboardButton("🔙 Back Home", callback_data="back_home")],
    ]
    return InlineKeyboardMarkup(keyboard)

def payment_methods_keyboard():
    keyboard = [
        [InlineKeyboardButton("🌸 বিকাশ (bKash)", callback_data="pay_bkash")],
        [InlineKeyboardButton("🟠 নগদ (Nagad)", callback_data="pay_nagad")],
        [InlineKeyboardButton("🔙 Back", callback_data="deposit_money")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_free_quota:
        user_free_quota[user_id] = 50  # ৫০ জন ফ্রি ট্রায়াল
        user_balance[user_id] = 0.0   # ওয়ালেট ব্যালেন্স (টাকায়)

    welcome_text = (
        "🚀 **AUTO REQUEST MANAGER BOT**\n\n"
        "⚙️ **How To Use:**\n"
        "1. Make Me ADMIN In Your Channel/Group.\n"
        "2. Give Add {New Admin Permission} To The Bot.\n\n"
        "⚡ Old Pending Join Requests Approve Speed Is 10,000/min\n"
        "💰 **Rate:** 100 Members Approval = 1 Taka"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "approve_req":
        target = user_selected_target.get(user_id, "Not Selected")
        balance = user_balance.get(user_id, 0.0)
        free_quota = user_free_quota.get(user_id, 50)

        msg = (
            f"✅ **Target Selected:** {target}\n"
            f"💰 **Wallet Balance:** {balance:.2f} BDT\n"
            f"🎁 **Free Quota Left:** {free_quota} Members\n\n"
            f"*Rate: 100 Members = 1 Taka*\n"
            f"*Note: Minimum 50 requests approval is mandatory.*"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Custom Amount", callback_data="enter_custom_amount")],
            [InlineKeyboardButton("🔙 Back Home", callback_data="back_home")]
        ])
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    elif query.data == "enter_custom_amount":
        await query.edit_message_text("📝 **Enter amount of requests to approve (Minimum 50):**")
        return WAITING_FOR_AMOUNT

    elif query.data == "account_info":
        balance = user_balance.get(user_id, 0.0)
        free_quota = user_free_quota.get(user_id, 50)
        msg = (
            f"👤 **Account Information**\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"💵 Main Balance: `{balance:.2f} BDT`\n"
            f"🎁 Remaining Free Trial: `{free_quota} Members`"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Home", callback_data="back_home")]])
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    elif query.data == "deposit_money":
        await query.edit_message_text("💳 **ডিপোজিট করার পরিমাণ সিলেক্ট করুন:**", reply_markup=deposit_amounts_keyboard(), parse_mode="Markdown")

    elif query.data.startswith("dep_"):
        amount = int(query.data.split("_")[1])
        context.user_data["deposit_amount"] = amount
        await query.edit_message_text(f"আপনি **{amount} টাকা** ডিপোজিট করতে চাচ্ছেন।\n\nঅনুগ্রহ করে পেমেন্ট মেথড নির্বাচন করুন:", reply_markup=payment_methods_keyboard(), parse_mode="Markdown")

    elif query.data in ["pay_bkash", "pay_nagad"]:
        method = "বিকাশ" if query.data == "pay_bkash" else "নগদ"
        context.user_data["pay_method"] = method
        number = payment_config["bkash"] if query.data == "pay_bkash" else payment_config["nagad"]
        amount = context.user_data.get("deposit_amount", 0)

        msg = (
            f"📲 **{method} Personal Number:** `{number}`\n"
            f"💵 **Amount:** `{amount} Taka`\n\n"
            f"১. উপরে উল্লেখিত নম্বরে **{amount} টাকা** Send Money করুন।\n"
            f"২. টাকা পাঠানোর পর পেমেন্টের একটি **স্ক্রিনশট (Screenshot)** নিচে পাঠান।"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
        return WAITING_FOR_SCREENSHOT

    elif query.data == "back_home":
        await start(update, context)

# ---------------- Calculation & Approval Handler ----------------
async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not text.isdigit():
        await update.message.reply_text("❌ অনুগ্রহ করে সঠিক সংখ্যা লিখুন (যেমন: 100)।")
        return WAITING_FOR_AMOUNT

    req_count = int(text)
    if req_count < 50:
        await update.message.reply_text("⚠️ Minimum 50 requests approval is mandatory. আবার লিখুন:")
        return WAITING_FOR_AMOUNT

    free_left = user_free_quota.get(user_id, 0)
    current_balance = user_balance.get(user_id, 0.0)

    if free_left >= req_count:
        user_free_quota[user_id] -= req_count
        await run_approval_animation(update, req_count)
        return ConversationHandler.END

    needed_requests = req_count - free_left
    cost = needed_requests * payment_config["rate_per_member"]

    if current_balance >= cost:
        user_free_quota[user_id] = 0
        user_balance[user_id] -= cost
        await run_approval_animation(update, req_count)
    else:
        needed_money = cost - current_balance
        await update.message.reply_text(
            f"❌ **অপর্যাপ্ত ব্যালেন্স!**\n\n"
            f"• মোট রিকোয়েস্ট: {req_count} জন\n"
            f"• প্রয়োজনীয় খরচ: {cost:.2f} টাকা\n"
            f"• আপনার বর্তমান ব্যালেন্স: {current_balance:.2f} টাকা\n\n"
            f"আপনাকে আরও **{needed_money:.2f} টাকা** ডিপোজিট করতে হবে। /start থেকে **Deposit Money** অপশনে যান।"
        )

    return ConversationHandler.END

async def run_approval_animation(update, amount):
    await update.message.reply_text("🚀 **Processing Engine Initiated...**")
    await asyncio.sleep(1.5)
    await update.message.reply_text("⚙️ **Booting Auxiliary Engine & Establishing Stealth Connection...**")
    await asyncio.sleep(1.5)
    await update.message.reply_text(f"✅ **BATCH COMPLETED**\nApproved: {amount}")

# ---------------- Payment Flow Handlers ----------------
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ অনুগ্রহ করে পেমেন্টের একটি **স্ক্রিনশট (Photo)** পাঠান।")
        return WAITING_FOR_SCREENSHOT

    context.user_data["screenshot"] = update.message.photo[-1].file_id
    method = context.user_data.get("pay_method", "পেমেন্ট")
    
    await update.message.reply_text(
        f"✅ স্ক্রিনশট পাওয়া গেছে!\n\n"
        f"এখন যে {method} নাম্বার থেকে টাকা পাঠিয়েছেন তার **শেষ ৪টি ডিজিট (Last 4 Digits)** লিখে পাঠান:"
    )
    return WAITING_FOR_DIGITS

async def handle_digits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    digits = update.message.text
    user = update.effective_user
    method = context.user_data.get("pay_method", "Payment")
    amount = context.user_data.get("deposit_amount", 0)
    photo_id = context.user_data.get("screenshot")

    await update.message.reply_text(
        "🎉 **আপনার ডিপোজিট রিকোয়েস্ট সফলভাবে জমা হয়েছে!**\n\n"
        "এডমিন ভেরিফাই করে অল্প কিছুক্ষণের মধ্যেই আপনার একাউন্টে টাকা যোগ করে দেবেন।"
    )

    admin_msg = (
        f"🔔 **New Deposit Request!**\n\n"
        f"👤 User: {user.full_name} (@{user.username})\n"
        f"🆔 User ID: `{user.id}`\n"
        f"💵 Amount: `{amount} Taka`\n"
        f"💳 Method: {method}\n"
        f"🔢 Last 4 Digits: `{digits}`\n\n"
        f"👉 **ব্যালেন্স এড করার কমান্ড:**\n"
        f"`/add_balance {user.id} {amount}`"
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_msg, parse_mode="Markdown")
    return ConversationHandler.END

# ---------------- Admin Commands ----------------
async def set_bkash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        payment_config["bkash"] = context.args[0]
        await update.message.reply_text(f"✅ বিকাশ নম্বর আপডেট করা হয়েছে: `{context.args[0]}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("বিকাশ নম্বর সেট করতে লিখুন: `/set_bkash 017XXXXXXXX`", parse_mode="Markdown")

async def set_nagad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        payment_config["nagad"] = context.args[0]
        await update.message.reply_text(f"✅ নগদ নম্বর আপডেট করা হয়েছে: `{context.args[0]}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("নগদ নম্বর সেট করতে লিখুন: `/set_nagad 018XXXXXXXX`", parse_mode="Markdown")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        target_user = int(context.args[0])
        amount = float(context.args[1])
        user_balance[target_user] = user_balance.get(target_user, 0.0) + amount
        
        await update.message.reply_text(f"✅ User `{target_user}` এর একাউন্টে **{amount} টাকা** যোগ করা হয়েছে।", parse_mode="Markdown")
        
        await context.bot.send_message(
            chat_id=target_user,
            text=f"🎉 আপনার ডিপোজিট সফল হয়েছে!\n💵 **{amount} টাকা** আপনার একাউন্টে যোগ করা হয়েছে।"
        )
    except Exception as e:
        await update.message.reply_text("❌ ফরম্যাট সঠিক নয়! লিখুন: `/add_balance USER_ID AMOUNT`")

# ---------------- Main App Setup ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(callback_handler, pattern="^(enter_custom_amount|pay_bkash|pay_nagad)$")
        ],
        states={
            WAITING_FOR_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_amount)],
            WAITING_FOR_SCREENSHOT: [MessageHandler(filters.PHOTO, handle_screenshot)],
            WAITING_FOR_DIGITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_digits)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_bkash", set_bkash))
    app.add_handler(CommandHandler("set_nagad", set_nagad))
    app.add_handler(CommandHandler("add_balance", add_balance))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
