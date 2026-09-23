import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ----------------- CONFIGURATION -----------------
# Render এর Environment Variable থেকে টোকেন নেবে, না থাকলে এখানে ডাইরেক্ট বসাতে পারেন
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
ADMIN_ID = 6929905808  # আপনার এডমিন আইডি

# ----------------- GLOBAL DATABASE -----------------
users = set()                # বট স্টার্ট করা ইউজার
channels_to_force_join = []  # বাধ্যতামূলক জয়েন চ্যানেল
rate_per_100 = 1.0           # ১০০ জন এপ্রুভে ১ টাকা
payment_number = "017XXXXXXXX"  # বিকাশ নম্বর

# চ্যাট ও মেসেজ ট্র্যাকিং
user_support_state = {}  # {user_id: True/False}
admin_reply_target = {}  # {admin_message_id: user_id}
user_approval_data = {}  # {user_id: {'chat_id': None, 'target_count': 0}}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ----------------- HELPER FUNCTIONS -----------------
async def is_user_joined(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """চেক করে ইউজার বাধ্যতামূলক চ্যানেলগুলোতে যুক্ত আছে কিনা"""
    for ch in channels_to_force_join:
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True

def get_main_keyboard(is_admin=False):
    """প্রধান মেনু কিবোর্ড"""
    kb = [
        ["✈️ Approve Requests", "➕ Add Group/Channel"],
        ["💰 Balance & Rates", "💬 Contact Admin"]
    ]
    if is_admin:
        kb.append(["⚙️ Admin Panel"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ----------------- COMMAND HANDLERS -----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users.add(user_id)
    
    # ফোর্স জয়েন চেক
    if channels_to_force_join and not await is_user_joined(user_id, context):
        keyboard = []
        for ch in channels_to_force_join:
            clean_ch = str(ch).replace('@','')
            keyboard.append([InlineKeyboardButton(f"Join Channel", url=f"https://t.me/{clean_ch}")])
        keyboard.append([InlineKeyboardButton("✅ Verify Join", callback_data="verify_join")])
        
        await update.message.reply_text(
            "⚠️ **বট ব্যবহার করতে নিচের চ্যানেল/গ্রুপগুলোতে আগে জয়েন করুন:**\n\n"
            "জয়েন শেষ হলে 'Verify Join' বাটনে ক্লিক করুন।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    is_admin = (user_id == ADMIN_ID)
    await update.message.reply_text(
        f"👋 স্বাগতম **{update.effective_user.first_name}**!\n"
        "এটি অটো রিকোয়েস্ট এপ্রুভাল বট। যেকোনো চ্যানেলের ঝুলে থাকা মেম্বারদের অটোমেটিক এপ্রুভ করতে নিচের বাটন ব্যবহার করুন:",
        reply_markup=get_main_keyboard(is_admin),
        parse_mode="Markdown"
    )

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if await is_user_joined(user_id, context):
        await query.delete_message()
        is_admin = (user_id == ADMIN_ID)
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ **সফলভাবে ভেরিফাই করা হয়েছে!**\nএখন আপনি সার্ভিস ব্যবহার করতে পারবেন।",
            reply_markup=get_main_keyboard(is_admin),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ **আপনি এখনও সব চ্যানেলে জয়েন করেননি!**\nদয়া করে সবগুলো চ্যানেলে জয়েন করে 'Verify Join'-এ চাপ দিন।",
            reply_markup=query.message.reply_markup
        )

# ----------------- JOIN REQUEST EVENT HANDLER -----------------
# যারা নতুন রিকোয়েস্ট পাঠাবে বা আগে থেকে পেন্ডিং আছে তাদের রেকর্ড এপ্রুভ করার ব্যাকগ্রাউন্ড প্রসেস
pending_requests_queue = {} # {chat_id: [user_ids]}

async def chat_join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """যখনই কেউ গ্রুপে নতুন রিকোয়েস্ট দেয় বা আগে থেকে থাকে, বট এখানে ডাটা জমা করে"""
    chat_id = update.chat_join_request.chat.id
    user_id = update.chat_join_request.from_user.id
    
    if chat_id not in pending_requests_queue:
        pending_requests_queue[chat_id] = []
    
    if user_id not in pending_requests_queue[chat_id]:
        pending_requests_queue[chat_id].append(user_id)

# ----------------- ADMIN & USER MESSAGE HANDLER -----------------

async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state')

    # ১. ইউজার সাপোর্ট মেসেজ (ইউজার থেকে এডমিনের কাছে পাঠাবে)
    if user_support_state.get(user_id):
        user_support_state[user_id] = False
        sent_msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 **ইউজার থেকে সাপোর্ট মেসেজ [{user_id}]:**\n\n{text}\n\n_(উত্তরের জন্য এই মেসেজটিতে Reply দিন)_",
            parse_mode="Markdown"
        )
        admin_reply_target[sent_msg.message_id] = user_id
        await update.message.reply_text("✅ আপনার মেসেজ এডমিনের কাছে চলে গেছে! শীঘ্রই উত্তর দেওয়া হবে।")
        return

    # ২. এডমিন মেসেজের রিপ্লাই দেওয়া
    if user_id == ADMIN_ID and update.message.reply_to_message:
        target_msg_id = update.message.reply_to_message.message_id
        target_user = admin_reply_target.get(target_msg_id)
        if target_user:
            await context.bot.send_message(
                chat_id=target_user,
                text=f"👨‍💻 **এডমিন রিপ্লাই:**\n\n{text}"
            )
            await update.message.reply_text("✅ ইউজারকে উত্তর পাঠানো হয়েছে!")
            return

    # ৩. পেন্ডিং মেম্বার এপ্রুভাল ইনপুট নেওয়া
    if state == 'WAITING_APPROVE_COUNT':
        try:
            target_count = int(text)
            if target_count < 1:
                await update.message.reply_text("❌ অন্তত ১ বা তার বেশি সংখ্যা লিখুন।")
                return
            
            context.user_data['state'] = None
            msg = await update.message.reply_text("🚀 **ঝুলে থাকা রিকোয়েস্টগুলো এপ্রুভ করা শুরু হচ্ছে...**", parse_mode="Markdown")
            
            approved_count = 0
            # যেসকল গ্রুপে বট যুক্ত আছে সেখান থেকে পেন্ডিং মেম্বার এপ্রুভ করবে
            for chat_id, user_list in pending_requests_queue.items():
                to_remove = []
                for p_user_id in user_list:
                    if approved_count >= target_count:
                        break
                    try:
                        # টেলিগ্রাম API দিয়ে রিয়েল এপ্রুভ
                        await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=p_user_id)
                        approved_count += 1
                        to_remove.append(p_user_id)
                    except Exception as e:
                        # যদি মেম্বার ক্যানসেল করে থাকে বা কোনো এরর হয়
                        to_remove.append(p_user_id)
                
                # এপ্রুভ হয়ে যাওয়া ইউজারদের লিস্ট থেকে বাদ দেওয়া
                for r in to_remove:
                    pending_requests_queue[chat_id].remove(r)
                
                if approved_count >= target_count:
                    break

            await msg.edit_text(
                f"✅ **BATCH COMPLETED!**\n\n"
                f"সফলভাবে ঝুলে থাকা **{approved_count}** জন মেম্বারের রিকোয়েস্ট এপ্রুভ করা হয়েছে!",
                parse_mode="Markdown"
            )
            return
        except ValueError:
            await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন (যেমন: 50, 100)!")
            return

    # ৪. এডমিন সেটিংস ইনপুট
    if user_id == ADMIN_ID and state:
        global rate_per_100, payment_number
        if state == 'WAITING_RATE':
            try:
                rate_per_100 = float(text)
                await update.message.reply_text(f"✅ নতুন রেট সেভ হয়েছে: ৳{rate_per_100} / ১০০ জন")
            except ValueError:
                await update.message.reply_text("❌ নম্বর লিখুন!")
        elif state == 'WAITING_BKASH':
            payment_number = text
            await update.message.reply_text(f"✅ বিকাশ নম্বর আপডেট হয়েছে: `{payment_number}`", parse_mode="Markdown")
        elif state == 'WAITING_ADD_FORCE':
            channels_to_force_join.append(text)
            await update.message.reply_text(f"✅ নতুন বাধ্যবাধকতার চ্যানেল যুক্ত হয়েছে: {text}")
        elif state == 'WAITING_BC_USERS':
            cnt = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u, text=f"📢 **অ্যানাউন্সমেন্ট:**\n\n{text}", parse_mode="Markdown")
                    cnt += 1
                except Exception:
                    pass
            await update.message.reply_text(f"✅ মোট {cnt} জন ইউজারকে মেসেজ পাঠানো হয়েছে!")

        context.user_data['state'] = None
        return

    # ৫. বাটন নেভিগেশন
    if text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("📢 Broadcast Users", callback_data="bc_users")],
            [InlineKeyboardButton("➕ Add Force Channel", callback_data="add_force_ch")],
            [InlineKeyboardButton("💵 Change Rate", callback_data="set_rate"), InlineKeyboardButton("📱 Change Bkash", callback_data="set_bkash")]
        ]
        await update.message.reply_text(
            f"⚙️ **Admin Control Panel**\n\n"
            f"👥 মোট ইউজার: {len(users)}\n"
            f"💵 রেট: ৳{rate_per_100} / ১০০ জন\n"
            f"📱 বিকাশ: `{payment_number}`\n"
            f"📢 ফোর্স চ্যানেল: {len(channels_to_force_join)} টি",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    elif text == "💬 Contact Admin":
        user_support_state[user_id] = True
        await update.message.reply_text("✏️ আপনার প্রশ্ন বা বক্তব্য লিখে দিন, এডমিন সরাসরি আপনার উত্তরে মেসেজ পাঠাবে:")
    elif text == "💰 Balance & Rates":
        await update.message.reply_text(
            f"💰 **সার্ভিস ফি ও তথ্য:**\n\n"
            f"• প্রতি ১০০ জন এপ্রুভে: ৳{rate_per_100}\n"
            f"• বিকাশ পেমেন্ট নম্বর: `{payment_number}`\n\n"
            "ব্যালেন্স রিচার্জ করতে এডমিনের সাথে চ্যাট অপশনে কথা বলুন।",
            parse_mode="Markdown"
        )
    elif text == "✈️ Approve Requests":
        context.user_data['state'] = 'WAITING_APPROVE_COUNT'
        await update.message.reply_text("✍️ কতজন ঝুলে থাকা (Pending) মেম্বার এপ্রুভ করতে চান সংখ্যা লিখুন (যেমন: 50, 100):")
    elif text == "➕ Add Group/Channel":
        await update.message.reply_text(
            "📌 **চ্যানেল/গ্রুপ যুক্ত করার উপায়:**\n\n"
            "১. আপনার চ্যানেল/গ্রুপে এই বটকে **Admin** হিসেবে যুক্ত করুন।\n"
            "২. বটকে **'Add New Admins'** বা **'Invite Users via Link'** পারমিশনটি চালু করে দিন।\n\n"
            "এর পর থেকেই সমস্ত পেন্ডিং রিকোয়েস্ট বট অটোমেটিক ফিল্টার করে এপ্রুভ করতে পারবে!"
        )

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if data == "set_rate":
        context.user_data['state'] = 'WAITING_RATE'
        await query.message.reply_text("✏️ ১০০ জনের জন্য নতুন রেট/টাকা লিখুন:")
    elif data == "set_bkash":
        context.user_data['state'] = 'WAITING_BKASH'
        await query.message.reply_text("✏️ নতুন বিকাশ নম্বর লিখুন:")
    elif data == "add_force_ch":
        context.user_data['state'] = 'WAITING_ADD_FORCE'
        await query.message.reply_text("✏️ জয়েন করানোর জন্য নতুন চ্যানেলের Username লিখুন (যেমন: `@mychannel`):")
    elif data == "bc_users":
        context.user_data['state'] = 'WAITING_BC_USERS'
        await query.message.reply_text("✏️ সব ইউজারকে পাঠানোর জন্য ব্রডকাস্ট মেসেজটি লিখুন:")

# ----------------- MAIN BOT START -----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(admin_buttons))
    
    # নতুন বা আগে থেকে আসা জয়েন রিকোয়েস্ট ক্যাচ করার জন্য
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_CREATED, chat_join_request_handler))
    
    # সাধারণ টেক্সট এবং কমান্ড মেসেজ
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_input))

    print("🤖 Bot started successfully! Admin ID: 6929905808")
    app.run_polling()

if __name__ == "__main__":
    main()
