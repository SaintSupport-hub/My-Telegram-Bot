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

FILES = {
    "shop": "products.json",
    "shop_tees": "products_tees.json",
    "shop_accessories": "products_accessories.json"
}
USERS_FILE = "users.json"
ORDERS_FILE = "topup_orders.json"

def gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.【entity-github¦canonical_name=GitHub】.v3+json"}

def fetch_from_github_api(file_path):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        r = requests.get(url, headers=gh_headers(), timeout=10)
        if r.status_code == 200:
            content = r.json().get("content")
            if content:
                return json.loads(base64.b64decode(content).decode())
    except Exception as e:
        print(f"【entity-GitHub¦canonical_name=GitHub】 fetch error {file_path}: {e}")
    return None

def commit_to_github(file_path, content_str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("MISSING GITHUB_TOKEN or GITHUB_REPO - NOT SAVING TO 【entity-GITHUB¦canonical_name=【entity-GitHub¦canonical_name=GitHub】】")
        return False
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        r = requests.get(url, headers=gh_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        data = {"message": f"Update {file_path}", "content": base64.b64encode(content_str.encode()).decode()}
        if sha:
            data["sha"] = sha
        resp = requests.put(url, headers=gh_headers(), json=data)
        print(f"GitHub commit {file_path} -> {resp.status_code}")
        return resp.status_code in [200, 201]
    except Exception as e:
        print(f"GitHub commit failed: {e}")
        return False

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            pass
    gh = fetch_from_github_api(path)
    if gh is not None:
        print(f"Restored {path} from GitHub")
        with open(path, "w") as f:
            json.dump(gh, f, indent=2)
        return gh
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    ok = commit_to_github(path, json.dumps(data, indent=2))
    print(f"Saved {path} local=True github={ok}")

def get_user(uid):
    users = load_json(USERS_FILE, {})
    s = str(uid)
    if s not in users:
        users[s] = {"balance": 0.0}
        save_json(USERS_FILE, users)
    return users[s]

def add_balance(uid, amt):
    users = load_json(USERS_FILE, {})
    s = str(uid)
    if s not in users:
        users[s] = {"balance": 0.0}
    users[s]["balance"] = float(users[s].get("balance", 0)) + float(amt)
    save_json(USERS_FILE, users)

app = Flask(__name__)
@app.route("/")
def home():
    return "SAINTLOCK LIVE"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def is_admin(uid):
    return uid == ADMIN_ID

def gen_order_id():
    return "TOPUP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🛒 Shop CC", callback_data="shop")],
        [InlineKeyboardButton("🥊 Shop Accounts", callback_data="shop_tees")],
        [InlineKeyboardButton("🥇 Shop BINs", callback_data="shop_accessories")],
        [InlineKeyboardButton("Balance / Top Up", callback_data="balance")],
        [InlineKeyboardButton("SUPPORT", callback_data="support")]
    ]
    await update.message.reply_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

async def show_category(query, cat_key, title):
    products = load_json(FILES[cat_key], [])
    if not products:
        kb = [[InlineKeyboardButton("Back", callback_data="back")]]
        await query.edit_message_text(f"{title} empty.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = []
    for i, p in enumerate(products):
        kb.append([InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{cat_key}_{i}")])
    kb.append([InlineKeyboardButton("Back", callback_data="back")])
    await query.edit_message_text(f"{title}:", reply_markup=InlineKeyboardMarkup(kb))

async def show_balance(q, uid):
    bal = get_user(uid).get("balance", 0)
    kb = [[InlineKeyboardButton("Top Up", callback_data="topup_choose")], [InlineKeyboardButton("Back", callback_data="back")]]
    await q.edit_message_text(f"Balance: ${bal:.2f}", reply_markup=InlineKeyboardMarkup(kb))

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
            [InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
            [InlineKeyboardButton("🥊 Shop Accounts", callback_data="shop_tees")],
            [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
            [InlineKeyboardButton("Balance / Top Up", callback_data="balance")],
            [InlineKeyboardButton("SUPPORT", callback_data="support")]
        ]
        await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "balance":
        await show_balance(q, uid)
    elif d == "support":
        kb = [
            [InlineKeyboardButton("Message Support", url=f"tg://user?id={ADMIN_ID}")],
            [InlineKeyboardButton("Open in Browser", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "topup_choose":
        kb = [
            [InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],
            [InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],
            [InlineKeyboardButton("Back", callback_data="balance")]
        ]
        await q.edit_message_text("Choose amount:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_amount_"):
        context.user_data["topup_amount"] = d.replace("topup_amount_", "")
        kb = [[InlineKeyboardButton("BTC", callback_data="topup_method_btc"), InlineKeyboardButton("CashApp", callback_data="topup_method_cash")]]
        await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_method_"):
        method = d.replace("topup_method_", "")
        amount = context.user_data.get("topup_amount", "20")
        order_id = gen_order_id()
        orders = load_json(ORDERS_FILE, [])
        orders.append({"order_id": order_id, "user_id": uid, "amount": float(amount), "method": method, "status": "pending", "username": q.from_user.username})
        save_json(ORDERS_FILE, orders)
        if method == "btc":
            img = qrcode.make(BTC_WALLET)
            bio = io.BytesIO()
            img.save(bio, 'PNG')
