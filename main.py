import os, json, threading, random, string, io, base64, requests
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
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "SaintSupport-hub/My-Telegram-Bot")

genai.configure(api_key=GEMINI_KEY)

DATA_DIR = "."
FILES = {
    "shop": f"{DATA_DIR}/products.json",
    "shop_tees": f"{DATA_DIR}/products_tees.json",
    "shop_accessories": f"{DATA_DIR}/products_accessories.json"
}
USERS_FILE = f"{DATA_DIR}/users.json"
ORDERS_FILE = f"{DATA_DIR}/topup_orders.json"

def github_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.【entity-github¦canonical_name=GitHub】.v3+json"} if GITHUB_TOKEN else {}

def fetch_from_github(file_path):
    if not GITHUB_REPO: return None
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{file_path}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return json.loads(r.text)
    except: pass
    return None

def commit_to_github(file_path, content_str):
    if not GITHUB_TOKEN or not GITHUB_REPO: 
        print("No GITHUB_TOKEN set - skipping GitHub save")
        return
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        r = requests.get(url, headers=github_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        data = {"message": f"Update {file_path}", "content": base64.b64encode(content_str.encode()).decode()}
        if sha: data["sha"] = sha
        resp = requests.put(url, headers=github_headers(), json=data)
        print(f"GitHub commit {file_path}: {resp.status_code}")
    except Exception as e:
        print(f"GitHub commit failed: {e}")

def load_json(path, default):
    # 1. Try local
    if os.path.exists(path):
        try:
            with open(path, "r") as f: return json.load(f)
        except: pass
    # 2. Try GitHub raw (restore after redeploy)
    gh_data = fetch_from_github(path)
    if gh_data is not None:
        # save locally for next time
        with open(path, "w") as f: json.dump(gh_data, f, indent=2)
        return gh_data
    return default

def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2)
    commit_to_github(path, json.dumps(data, indent=2))

def get_user(user_id):
    users = load_json(USERS_FILE, {})
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"balance": 0.0}
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
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
def is_admin(uid): return uid == ADMIN_ID
def gen_order_id(): return "TOPUP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

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

async def show_balance(q, uid):
    bal = get_user(uid).get("balance", 0)
    kb = [[InlineKeyboardButton("➕ Top Up", callback_data="topup_choose")],[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    await q.edit_message_text(f"💰 Balance: ${bal:.2f}", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    if d in FILES:
        names = {"shop": "🛒 Shop CC", "shop_tees": "🥊 Shop Accounts", "shop_accessories": "🥇 Shop BINs"}
        await show_category(q, d, names[d])
    elif d == "back":
        kb = [[InlineKeyboardButton("🛒 Shop CC", callback_data="shop")],[InlineKeyboardButton("🥊 Shop Accounts", callback_data="shop_tees")],[InlineKeyboardButton("🥇 Shop BINs", callback_data="shop_accessories")],[InlineKeyboardButton("💰 Balance / Top Up", callback_data="balance")],[InlineKeyboardButton("💬 SUPPORT", callback_data="support")]]
        await q.edit_message_text("Welcome to SAINTLOCK CC 🔒", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "balance":
        await show_balance(q, uid)
    elif d == "support":
        kb = [[InlineKeyboardButton("📩 Message Support", url=f"https://t.me/{SUPPORT_USERNAME}")],[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await q.edit_message_text("💬 SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "topup_choose":
        kb = [[InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],[InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],[InlineKeyboardButton("⬅️ Back", callback_data="balance")]]
        await q.edit_message_text("Choose amount:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_amount_"):
        context.user_data["topup_amount"] = d.replace("topup_amount_", "")
        kb = [[InlineKeyboardButton("₿ BTC", callback_data="topup_method_btc"), InlineKeyboardButton("💵 CashApp", callback_data="topup_method_cash")]]
        await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_method_"):
        method = d.replace("topup_method_", ""); amount = context.user_data.get("topup_amount", "20"); order_id = gen_order_id()
        orders = load_json(ORDERS_FILE, []); orders.append({"order_id": order_id, "user_id": uid, "amount": float(amount), "method": method, "status": "pending", "username": q.from_user.username}); save_json(ORDERS_FILE, orders)
        if method == "btc":
            img = qrcode.make(BTC_WALLET); bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
            await q.message.reply_photo(photo=bio, caption=f"Order {order_id} - ${amount} BTC to:\n`{BTC_WALLET}`", parse_mode="Markdown")
        else:
            await q.message.reply_text(f"Order {order_id} - ${amount} CashApp: `{CASHAPP_TAG}` Note: {order_id}", parse_mode="Markdown")
        if uid != ADMIN_ID:
            admin_kb = [[InlineKeyboardButton(f"✅ Verify {order_id}", callback_data=f"admin_verify_{order_id}"), InlineKeyboardButton(f"❌ Decline", callback_data=f"admin_decline_{order_id}")]]
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 NEW TOP UP\nUser: @{q.from_user.username} ({uid})\nOrder: {order_id}\nAmount: ${amount}\nMethod: {method}", reply_markup=InlineKeyboardMarkup(admin_kb))
            except: pass
    elif d.startswith("admin_verify_"):
        if not is_admin(uid): return
        order_id = d.replace("admin_verify_", ""); orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["status"] == "pending":
                o["status"] = "verified"; add_balance(o["user_id"], o["amount"]); save_json(ORDERS_FILE, orders)
                await q.edit_message_text(f"✅ Verified {order_id}")
                try: await context.bot.send_message(chat_id=o["user_id"], text=f"✅ Verified {order_id} - ${o['amount']} added!")
                except: pass
    elif d.startswith("admin_decline_"):
        if not is_admin(uid): return
        order_id = d.replace("admin_decline_", ""); orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["status"] == "pending":
                o["status"] = "declined"; save_json(ORDERS_FILE, orders); await q.edit_message_text(f"❌ Declined {order_id}")
    elif d.startswith("view_"):
        rest = d.replace("view_", "")
        if rest.startswith("shop_tees_"): cat_key="shop_tees"; idx=int(rest.replace("shop_tees_",""))
        elif rest.startswith("shop_accessories_"): cat_key="shop_accessories"; idx=int(rest.replace("shop_accessories_",""))
        else: cat_key="shop"; idx=int(rest.replace("shop_",""))
        p = load_json(FILES[cat_key], [])[idx]
        await q.message.reply_text(f"{p['name']} - ${p['price']}\n{p['desc']}")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]; parts = [x.strip() for x in raw.split("|")]
        cat_key, name, price, desc = (parts[0].lower(), parts[1], parts[2], parts[3]) if len(parts)==4 else ("shop", parts[0], parts[1], parts[2])
        if cat_key not in FILES: cat_key="shop"
        price = price.replace("$","").strip()
        prods = load_json(FILES[cat_key], []); prods.append({"name": name, "price": price, "desc": desc}); save_json(FILES[cat_key], prods)
        await update.message.reply_text(f"✅ Saved to GitHub forever: {name}")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc")

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    # This fixes the Conflict error
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
