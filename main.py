import os, json, threading, random, string, io, base64, requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "SaintSupport-hub/My-Telegram-Bot")

FILES = {
    "shop": "products.json",
    "shop_tees": "products_tees.json",
    "shop_accessories": "products_accessories.json"
}
USERS_FILE = "users.json"

def gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.【entity-github¦canonical_name=GitHub】.v3+json"}

def fetch_github(path):
    if not GITHUB_TOKEN:
        return None
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers(), timeout=10)
        if r.status_code == 200:
            import base64
            return json.loads(base64.b64decode(r.json()["content"]).decode())
    except:
        pass
    return None

def commit_github(path, data_str):
    if not GITHUB_TOKEN:
        return
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": f"Update {path}", "content": base64.b64encode(data_str.encode()).decode()}
        if sha:
            payload["sha"] = sha
        requests.put(url, headers=gh_headers(), json=payload)
    except Exception as e:
        print(f"【entity-GitHub¦canonical_name=GitHub】 error: {e}")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            pass
    gh = fetch_github(path)
    if gh is not None:
        with open(path, "w") as f:
            json.dump(gh, f, indent=2)
        return gh
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    commit_github(path, json.dumps(data, indent=2))

def get_user(uid):
    users = load_json(USERS_FILE, {})
    s = str(uid)
    if s not in users:
        users[s] = {"balance": 0.0}
        save_json(USERS_FILE, users)
    return users[s]

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
        [InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
        [InlineKeyboardButton("🥊Shop Accounts", callback_data="shop_tees")],
        [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
        [InlineKeyboardButton("SUPPORT", callback_data="support")]
    ]
    await update.message.reply_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d in FILES:
        products = load_json(FILES[d], [])
        if not products:
            await q.edit_message_text(f"{d} empty - add with /addproduct", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
            return
        kb = []
        for i, p in enumerate(products):
            kb.append([InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{d}_{i}")])
        kb.append([InlineKeyboardButton("Back", callback_data="back")])
        await q.edit_message_text(f"{d}:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "back":
        kb = [
            [InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
            [InlineKeyboardButton("🥊Shop Accounts", callback_data="shop_tees")],
            [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
            [InlineKeyboardButton("SUPPORT", callback_data="support")]
        ]
        await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "support":
        kb = [
            [InlineKeyboardButton("Message Support", url=f"tg://user?id={ADMIN_ID}")],
            [InlineKeyboardButton("Open in Browser", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("view_"):
        _, cat, idx = d.split("_", 2)
        if cat == "shop":
            # view_shop_0
            cat_key = "shop"
            idx = int(d.replace("view_shop_", ""))
        else:
            # view_shop_tees_0 or view_shop_accessories_0
            if "shop_tees" in d:
                cat_key = "shop_tees"
                idx = int(d.replace("view_shop_tees_", ""))
            else:
                cat_key = "shop_accessories"
                idx = int(d.replace("view_shop_accessories_", ""))
        products = load_json(FILES[cat_key], [])
        p = products[idx]
        await q.message.reply_text(f"{p['name']} - ${p['price']}\n{p['desc']}")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) == 4:
            cat_key, name, price, desc = parts[0].lower(), parts[1], parts[2], parts[3]
        else:
            cat_key, name, price, desc = "shop", parts[0], parts[1], parts[2]
        if cat_key not in FILES:
            cat_key = "shop"
        price = price.replace("$", "").strip()
        prods = load_json(FILES[cat_key], [])
        prods.append({"name": name, "price": price, "desc": desc})
        save_json(FILES[cat_key], prods)
        await update.message.reply_text(f"Saved: {name} to {FILES[cat_key]}")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc - {e}")

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
