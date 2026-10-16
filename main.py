import os, json, threading, random, string, io
from datetime import datetime
from flask import Flask
import qrcode
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BTC_WALLET = os.getenv("BTC_WALLET", "bc1qftk75wjqwutjczsth2axmgnj8a03rdgu0htd39")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport") # <--- PUT YOUR TG USERNAME HERE

genai.configure(api_key=GEMINI_KEY)

FILES = {
    "shop": "products.json",
    "shop_tees": "products_tees.json",
    "shop_accessories": "products_accessories.json"
}
USERS_FILE = "users.json"
ORDERS_FILE = "topup_orders.json"

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r") as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2)

def get_user(user_id):
    users = load_json(USERS_FILE, {})
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"balance": 0.0, "username": ""}
        save_json(USERS_FILE, users)
    return users[uid]

def add_balance(user_id, amount):
    users = load_json(USERS_FILE, {})
    uid = str(user_id)
    if uid not in users: users[uid] = {"balance": 0.0}
    users[uid]["balance"] = float(users[uid].get("balance", 0)) + float(amount)
    save_json(USERS_FILE, users)

app = Flask(__name__)
@app.route("/")
def home(): return "SAINTLOCK LIVE"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
def is_admin(uid): return uid == ADMIN_ID

def gen_order_id():
    return "TOPUP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🛒 Shop CC", callback_data="shop")],
        [InlineKeyboardButton("🥊 Shop Accounts", callback_data="shop_tees")],
        [InlineKeyboardButton("🥇 Shop BINs", callback_data="shop_accessories")],
        [InlineKeyboardButton("💰 Balance / Top Up", callback_data="balance")],
        [InlineKeyboardButton("💬 SUPPORT", callback_data="support")]
    ]
    await update.message.reply_text("Welcome to SAINTLOCK CC 🔒", reply_markup=InlineKeyboardMarkup(kb))

async def show_category(query, cat_key, title):
    products = load_json(FILES[cat_key], [])
    if not products:
        kb = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await query.edit_message_text(f"{title} empty.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = []
    for i, p in enumerate(products):
        kb.append([InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{cat_key}_{i}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    await query.edit_message_text(f"{title}:", reply_markup=InlineKeyboardMarkup(kb))

async def show_balance(query_or_update, user_id):
    user = get_user(user_id)
    bal = user.get("balance", 0)
    text = f"💰 Your Balance: ${bal:.2f}\n\nTop up to buy with balance."
    kb = [
        [InlineKeyboardButton("➕ Top Up", callback_data="topup_choose")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query_or_update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    if d in FILES:
        names = {"shop": "🛒 Shop CC", "shop_tees": "🥊 Shop Accounts", "shop_accessories": "🥇 Shop BINs"}
        await show_category(q, d, names[d])
    elif d == "back":
        kb = [
            [InlineKeyboardButton("🛒 Shop CC", callback_data="shop")],
            [InlineKeyboardButton("🥊 Shop Accounts", callback_data="shop_tees")],
            [InlineKeyboardButton("🥇 Shop BINs", callback_data="shop_accessories")],
            [InlineKeyboardButton("💰 Balance / Top Up", callback_data="balance")],
            [InlineKeyboardButton("💬 SUPPORT", callback_data="support")]
        ]
        await q.edit_message_text("Welcome to SAINTLOCK CC 🔒", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "balance":
        await show_balance(q, uid)
    elif d == "support":
        # SUPPORT NOW LINKS TO YOUR TELEGRAM
        kb = [
            [InlineKeyboardButton("📩 Message Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]
        await q.edit_message_text(f"💬 SUPPORT\n\nClick below to message support:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "topup_choose":
        kb = [
            [InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],
            [InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],
            [InlineKeyboardButton("⬅️ Back", callback_data="balance")]
        ]
        await q.edit_message_text("Choose amount to Top Up:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_amount_"):
        amount = d.replace("topup_amount_", "")
        context.user_data["topup_amount"] = amount
        kb = [
            [InlineKeyboardButton("₿ BTC", callback_data="topup_method_btc"), InlineKeyboardButton("💵 CashApp", callback_data="topup_method_cash")],
            [InlineKeyboardButton("⬅️ Back", callback_data="topup_choose")]
        ]
        await q.edit_message_text(f"Top Up ${amount}\nChoose payment method:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_method_"):
        method = d.replace("topup_method_", "")
        amount = context.user_data.get("topup_amount", "20")
        order_id = gen_order_id()

        orders = load_json(ORDERS_FILE, [])
        orders.append({"order_id": order_id, "user_id": uid, "amount": float(amount), "method": method, "status": "pending", "username": q.from_user.username})
        save_json(ORDERS_FILE, orders)

        if method == "btc":
            # Generate QR for BTC wallet
            img = qrcode.make(BTC_WALLET)
            bio = io.BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            caption = f"💰 TOP UP REQUEST\n\nOrder ID: {order_id}\nAmount: ${amount}\nMethod: BTC\n\nSend ${amount} BTC to:\n`{BTC_WALLET}`\n\nAfter you send, admin will verify and add to your balance."
            await q.message.reply_photo(photo=bio, caption=caption, parse_mode="Markdown")
        else:
            caption = f"💰 TOP UP REQUEST\n\nOrder ID: {order_id}\nAmount: ${amount}\nMethod: CashApp\n\nSend ${amount} to CashApp:\n`{CASHAPP_TAG}`\n\nInclude Order ID in note: {order_id}\n\nAfter you send, admin will verify and add to your balance."
            await q.message.reply_text(caption, parse_mode="Markdown")

        # Notify ADMIN with Verify/Decline
        admin_kb = [
            [InlineKeyboardButton(f"✅ Verify {order_id}", callback_data=f"admin_verify_{order_id}"), InlineKeyboardButton(f"❌ Decline {order_id}", callback_data=f"admin_decline_{order_id}")]
        ]
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 NEW TOP UP\nUser: @{q.from_user.username} ({uid})\nOrder: {order_id}\nAmount: ${amount}\nMethod: {method}\n\nCheck {method} then Verify.", reply_markup=InlineKeyboardMarkup(admin_kb))
        except: pass

        await q.message.reply_text("✅ Request sent to admin. Your balance will update after verification. Check /balance")

    elif d.startswith("admin_verify_"):
        if not is_admin(uid): return
        order_id = d.replace("admin_verify_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["status"] == "pending":
                o["status"] = "verified"
                add_balance(o["user_id"], o["amount"])
                save_json(ORDERS_FILE, orders)
                await q.edit_message_text(f"✅ Verified {order_id} - Added ${o['amount']} to {o['user_id']}")
                try:
                    await context.bot.send_message(chat_id=o["user_id"], text=f"✅ Top Up Verified!\nOrder {order_id}\n${o['amount']} added to your balance.\nNew Balance: ${get_user(o['user_id'])['balance']:.2f}")
                except: pass
                return
    elif d.startswith("admin_decline_"):
        if not is_admin(uid): return
        order_id = d.replace("admin_decline_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["status"] == "pending":
                o["status"] = "declined"
                save_json(ORDERS_FILE, orders)
                await q.edit_message_text(f"❌ Declined {order_id}")
                try:
                    await context.bot.send_message(chat_id=o["user_id"], text=f"❌ Top Up Declined\nOrder {order_id}\nContact support: @{SUPPORT_USERNAME}")
                except: pass
                return
    elif d.startswith("view_"):
        rest = d.replace("view_", "")
        if rest.startswith("shop_tees_"):
            cat_key = "shop_tees"; idx = int(rest.replace("shop_tees_", ""))
        elif rest.startswith("shop_accessories_"):
            cat_key = "shop_accessories"; idx = int(rest.replace("shop_accessories_", ""))
        else:
            cat_key = "shop"; idx = int(rest.replace("shop_", ""))
        p = load_json(FILES[cat_key], [])[idx]
        user = get_user(uid)
        kb = [
            [InlineKeyboardButton(f"💰 Pay with Balance (${user['balance']:.2f})", callback_data=f"pay_balance_{cat_key}_{idx}")],
            [InlineKeyboardButton("₿ Pay BTC", callback_data="pay_crypto"), InlineKeyboardButton("💵 CashApp", callback_data="pay_cash")],
            [InlineKeyboardButton("⬅️ Back", callback_data=cat_key)]
        ]
        await q.message.reply_text(f"{p['name']} - ${p['price']}\n{p['desc']}", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("pay_balance_"):
        _, cat_key, idx = d.split("_")[2], "_".join(d.split("_")[2:4]) if "tees" in d or "accessories" in d else d.split("_")[2], d.split("_")[-1]
        # parse again safely
        parts = d.replace("pay_balance_", "").split("_")
        if parts[0] == "shop" and parts[1] in ["tees", "accessories"]:
            cat_key = f"shop_{parts[1]}"; idx = int(parts[2])
        else:
            cat_key = "shop"; idx = int(parts[1])
        p = load_json(FILES[cat_key], [])[idx]
        price = float(p["price"])
        user = get_user(uid)
        if user["balance"] >= price:
            add_balance(uid, -price)
            await q.message.reply_text(f"✅ Purchased {p['name']} with balance! New balance ${get_user(uid)['balance']:.2f}")
        else:
            await q.message.reply_text(f"❌ Not enough balance. You have ${user['balance']:.2f}, need ${price}. Top up in Balance menu.")
    elif d == "pay_crypto":
        img = qrcode.make(BTC_WALLET)
        bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
        await q.message.reply_photo(photo=bio, caption=f"₿ BTC: `{BTC_WALLET}`", parse_mode="Markdown")
    elif d == "pay_cash":
        await q.message.reply_text(f"💵 CashApp: `{CASHAPP_TAG}`", parse_mode="Markdown")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        cat_key, name, price, desc = (parts[0].lower(), parts[1], parts[2], parts[3]) if len(parts)==4 else ("shop", parts[0], parts[1], parts[2])
        if cat_key not in FILES: cat_key="shop"
        price = price.replace("$","").strip()
        prods = load_json(FILES[cat_key], [])
        prods.append({"name": name, "price": price, "desc": desc})
        save_json(FILES[cat_key], prods)
        await update.message.reply_text(f"✅ Added to {cat_key}: {name}")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_balance(update, update.effective_user.id)

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("balance", balance_cmd))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
