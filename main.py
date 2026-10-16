import os, json, random, threading
from datetime import datetime
from flask import Flask
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# YOUR PAYMENTS - hardcoded as backup
BTC_WALLET = os.getenv("BTC_WALLET", "bc1qftk75wjqwutjczsth2axmgnj8a03rdgu0htd39")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r") as f: return json.load(f)
    except: return default
def save_json(path, data):
    with open(path, "w") as f: json.dump(f, data, indent=2)

app = Flask(__name__)
@app.route("/")
def home(): return "SAINTLOCK CC - CLAPCakes Live"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def is_admin(uid): return uid == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🛒 Shop CLAPCakes", callback_data="shop")],[InlineKeyboardButton("💰 Prices", callback_data="prices")],[InlineKeyboardButton("📞 Support", callback_data="support")],[InlineKeyboardButton("🤖 Ask AI", callback_data="ai")]]
    await update.message.reply_text("Welcome to SAINTLOCK CC 🔒\nCLAPCakes Clothing Brand\nChoose an option:", reply_markup=InlineKeyboardMarkup(kb))

async def show_shop(update_or_query, context):
    products = load_json(PRODUCTS_FILE, [])
    if not products:
        text = "Shop empty - Admin add products with /addproduct"
        if hasattr(update_or_query, 'edit_message_text'): await update_or_query.edit_message_text(text)
        else: await update_or_query.message.reply_text(text)
        return
    kb = [[InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"prod_{i}")] for i, p in enumerate(products)]
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    if hasattr(update_or_query, 'edit_message_text'): await update_or_query.edit_message_text("🛒 Tap an item to order:", reply_markup=InlineKeyboardMarkup(kb))
    else: await update_or_query.message.reply_text("🛒 Tap an item to order:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "shop": await show_shop(query, context)
    elif data == "back":
        kb = [[InlineKeyboardButton("🛒 Shop CLAPCakes", callback_data="shop")],[InlineKeyboardButton("💰 Prices", callback_data="prices")],[InlineKeyboardButton("📞 Support", callback_data="support")],[InlineKeyboardButton("🤖 Ask AI", callback_data="ai")]]
        await query.edit_message_text("Welcome to SAINTLOCK CC 🔒\nCLAPCakes Clothing Brand\nChoose an option:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "prices":
        products = load_json(PRODUCTS_FILE, [])
        txt = "\n".join([f"• {p['name']}: ${p['price']}" for p in products]) or "No prices yet"
        await query.edit_message_text(f"💰 Prices:\n{txt}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif data == "support":
        await query.edit_message_text("📞 Support: @Saintlockecon", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif data == "ai":
        await query.edit_message_text("🤖 AI Mode: Type any question!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif data.startswith("prod_"):
        idx = int(data.split("_")[1])
        products = load_json(PRODUCTS_FILE, [])
        p = products[idx]
        order_num = f"SL-{random.randint(10000,99999)}"
        orders = load_json(ORDERS_FILE, [])
        orders.append({"order": order_num, "user": query.from_user.id, "product": p, "time": str(datetime.now())})
        save_json(ORDERS_FILE, orders)
        copy_text = f"ORDER REQUEST\nProduct: {p['name']}\nPrice: ${p['price']}\nInfo: {p['desc']}\nOrder: {order_num}"
        await query.message.reply_text(f"✅ You selected:\n\n`{copy_text}`\n\n👆 Hold to COPY then SEND to confirm order.", parse_mode="Markdown")
        pay_kb = [[InlineKeyboardButton("💳 Pay with Balance", callback_data=f"pay_bal_{order_num}")],[InlineKeyboardButton("₿ Crypto (BTC)", callback_data=f"pay_crypto_{order_num}")],[InlineKeyboardButton("💵 CashApp", callback_data=f"pay_cash_{order_num}")]]
        await query.message.reply_text(f"Order {order_num} for {p['name']} - Choose payment:", reply_markup=InlineKeyboardMarkup(pay_kb))
    elif data.startswith("pay_"):
        _, method, order_num = data.split("_", 2)
        if method == "bal":
            users = load_json(USERS_FILE, {})
            bal = users.get(str(query.from_user.id), {}).get("balance", 0)
            await query.message.reply_text(f"💳 Balance Payment for {order_num}\nYour balance: ${bal}\nReply YES to confirm.")
        elif method == "crypto":
            await query.message.reply_text(f"₿ Crypto Payment for {order_num}\n\nSend BTC to:\n`{BTC_WALLET}`\n\nNetwork: Bitcoin (BTC)\nAfter sending, reply with TX ID.", parse_mode="Markdown")
        elif method == "cash":
            await query.message.reply_text(f"💵 CashApp Payment for {order_num}\n\nSend to:\n`{CASHAPP_TAG}`\n\nAfter sending, reply with screenshot.", parse_mode="Markdown")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return await update.message.reply_text("Not admin")
    try:
        text = update.message.text.replace("/addproduct","").strip()
        name, price, desc = [x.strip() for x in text.split("|")]
        products = load_json(PRODUCTS_FILE, [])
        products.append({"name": name, "price": price, "desc": desc})
        save_json(PRODUCTS_FILE, products)
        await update.message.reply_text(f"✅ Added: {name} - ${price}")
    except:
        await update.message.reply_text("Use: /addproduct Name | Price | Description")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_json(PRODUCTS_FILE, [])
    await update.message.reply_text("\n".join([f"{i}: {p['name']} - ${p['price']}" for i, p in enumerate(products)]) or "No products")

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.startswith("/"): return
    try:
        r = model.generate_content(update.message.text)
        await update.message.reply_text(r.text)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CommandHandler("listproducts", list_products))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))
    app_bot.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
