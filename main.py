import os, json, threading
from flask import Flask
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BTC_WALLET = os.getenv("BTC_WALLET", "bc1qftk75wjqwutjczsth2axmgnj8a03rdgu0htd39")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")

genai.configure(api_key=GEMINI_KEY)

# KEEP YOUR 3 OLD ITEMS - they are in products.json
FILES = {
    "shop": "products.json",
    "shop_tees": "products_tees.json",
    "shop_accessories": "products_accessories.json"
}

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
def home():
    return "SAINTLOCK LIVE"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def is_admin(uid):
    return uid == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🛒 Shop CC", callback_data="shop")],
        [InlineKeyboardButton("🥊 Shop Accounts", callback_data="shop_tees")],
        [InlineKeyboardButton("🥇 Shop BINs", callback_data="shop_accessories")],
        [InlineKeyboardButton("💬 SUPPORT", callback_data="support")]
    ]
    await update.message.reply_text("Welcome to SAINTLOCK CC 🔒", reply_markup=InlineKeyboardMarkup(kb))

async def show_category(query, cat_key, title):
    products = load_json(FILES[cat_key], [])
    if not products:
        kb = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await query.edit_message_text(f"{title} empty.\nAdd: /addproduct {cat_key} | Name | Price | Desc", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = []
    for i, p in enumerate(products):
        kb.append([InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{cat_key}_{i}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    await query.edit_message_text(f"{title}:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d in FILES:
        names = {"shop": "🛒 Shop CC", "shop_tees": "👕 Shop Tees", "shop_accessories": "🏷️ Shop Accessories"}
        await show_category(q, d, names[d])
    elif d == "back":
        kb = [
            [InlineKeyboardButton("🛒 Shop CC", callback_data="shop")],
            [InlineKeyboardButton("👕 Shop Tees", callback_data="shop_tees")],
            [InlineKeyboardButton("🏷️ Shop Accessories", callback_data="shop_accessories")],
            [InlineKeyboardButton("💬 SUPPORT", callback_data="support")]
        ]
        await q.edit_message_text("Welcome to SAINTLOCK CC 🔒", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "support":
        kb = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await q.edit_message_text(f"💬 SUPPORT\n\nCashApp: {CASHAPP_TAG}\nBTC: {BTC_WALLET}", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("view_"):
        # view_shop_0 or view_shop_tees_0
        rest = d.replace("view_", "")
        if rest.startswith("shop_tees_"):
            cat_key = "shop_tees"
            idx = int(rest.replace("shop_tees_", ""))
        elif rest.startswith("shop_accessories_"):
            cat_key = "shop_accessories"
            idx = int(rest.replace("shop_accessories_", ""))
        else:
            cat_key = "shop"
            idx = int(rest.replace("shop_", ""))
        p = load_json(FILES[cat_key], [])[idx]
        await q.message.reply_text(f"✅ {p['name']} - ${p['price']}\n{p['desc']}")
        pay_kb = [[InlineKeyboardButton("₿ BTC", callback_data="pay_crypto")], [InlineKeyboardButton("💵 CashApp", callback_data="pay_cash")]]
        await q.message.reply_text("Choose payment:", reply_markup=InlineKeyboardMarkup(pay_kb))
    elif d == "pay_crypto":
        await q.message.reply_text(f"₿ Send BTC:\n`{BTC_WALLET}`", parse_mode="Markdown")
    elif d == "pay_cash":
        await q.message.reply_text(f"💵 CashApp:\n`{CASHAPP_TAG}`", parse_mode="Markdown")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(f"Not admin. Your ID: {update.effective_user.id}")
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) == 4:
            cat_key, name, price, desc = parts
        else:
            cat_key = "shop"
            name, price, desc = parts
        cat_key = cat_key.lower()
        if cat_key not in FILES:
            cat_key = "shop"
        price = price.replace("$", "").strip()
        products = load_json(FILES[cat_key], [])
        products.append({"name": name, "price": price, "desc": desc})
        save_json(FILES[cat_key], products)
        await update.message.reply_text(f"✅ Added to {cat_key}: {name} - ${price}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}\nUse: /addproduct shop | Name | Price | Desc")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = ""
    for k, path in FILES.items():
        ps = load_json(path, [])
        txt += f"{k}: {len(ps)} items\n"
    await update.message.reply_text(txt)

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CommandHandler("listproducts", list_products))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.run_polling()

if __name__ == "__main__":
    threading.Thread(target=ru
