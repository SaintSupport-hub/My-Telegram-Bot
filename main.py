import os, json, random, threading
from datetime import datetime
from flask import Flask
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BTC_WALLET = os.getenv("BTC_WALLET", "bc1qftk75wjqwutjczsth2axmgnj8a03rdgu0htd39")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

PRODUCTS_FILE = "products.json"

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

app = Flask(__name__)
@app.route("/")
def home(): return "SAINTLOCK CC LIVE"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def is_admin(uid):
    return uid == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🛒 Shop CC", callback_data="shop")]]
    await update.message.reply_text("Welcome to SAINTLOCK CC 🔒", reply_markup=InlineKeyboardMarkup(kb))

async def show_shop(q, c):
    products = load_json(PRODUCTS_FILE, [])
    if not products:
        await q.edit_message_text("Shop empty. Add with /addproduct")
        return
    kb = [[InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"prod_{i}")] for i,p in enumerate(products)]
    await q.edit_message_text("🛒 Shop:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "shop":
        await show_shop(query, context)
    elif query.data.startswith("prod_"):
        idx = int(query.data.split("_")[1])
        products = load_json(PRODUCTS_FILE, [])
        p = products[idx]
        await query.message.reply_text(f"✅ You selected: {p['name']} - ${p['price']}\nDesc: {p['desc']}")
        pay_kb = [[InlineKeyboardButton("₿ Pay BTC", callback_data="pay_crypto")],[InlineKeyboardButton("💵 CashApp", callback_data="pay_cash")]]
        await query.message.reply_text("Choose payment:", reply_markup=InlineKeyboardMarkup(pay_kb))
    elif query.data == "pay_crypto":
        await query.message.reply_text(f"₿ Send BTC to:\n`{BTC_WALLET}`\n\nNetwork: Bitcoin", parse_mode="Markdown")
    elif query.data == "pay_cash":
        await query.message.reply_text(f"💵 Send CashApp to:\n`{CASHAPP_TAG}`", parse_mode="Markdown")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(f"Not admin. Your ID is {update.effective_user.id}")
    try:
        raw = update.message.text
        content = raw.split(" ", 1)[1]
        parts = [x.strip() for x in content.split("|")]
        name = parts[0]
        price = parts[1].replace("$","").strip()
        desc = parts[2]
        products = load_json(PRODUCTS_FILE, [])
        products.append({"name": name, "price": price, "desc": desc})
        save_json(PRODUCTS_FILE, products)
        await update.message.reply_text(f"✅ Added: {name} - ${price}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}\nUse: /addproduct Name | Price | Description")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_json(PRODUCTS_FILE, [])
    txt = "\n".join([f"{p['name']} - ${p['price']}" for p in products]) or "No products"
    await update.message.reply_text(txt)

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CommandHandler("listproducts", list_products))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
