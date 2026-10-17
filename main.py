import os, json, threading, base64, requests, random, string, io
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import qrcode

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport")

GH_TOK_KEY = "GIT" + "HUB_TOKEN"
GH_REPO_KEY = "GIT" + "HUB_REPO"
BTC_KEY = "BTC_WALLET"
CASH_KEY = "CASHAPP_TAG"

GH_TOKEN = os.getenv(GH_TOK_KEY)
GH_REPO = os.getenv(GH_REPO_KEY, "SaintSupport-hub/My-Telegram-Bot")
BTC_WALLET = os.getenv(BTC_KEY, "bc1q...")
CASHAPP_TAG = os.getenv(CASH_KEY, "$Saintlockecon")

CATEGORIES_FILE = "categories.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

DEFAULT_CATEGORIES = [
    {"id": "shop", "name": "🛒Shop CC", "file": "products.json"},
    {"id": "shop_tees", "name": "🥊Shop Accounts", "file": "products_tees.json"},
    {"id": "shop_accessories", "name": "🥇Shop BINs", "file": "products_accessories.json"}
]

def gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            pass
    if GH_TOKEN:
        try:
            url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
            r = requests.get(url, headers=gh_headers(), timeout=15)
            if r.status_code == 200:
                data = json.loads(base64.b64decode(r.json()["content"]).decode())
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                return data
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    if not GH_TOKEN:
        return False
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": f"Update {path}", "content": base64.b64encode(json.dumps(data, indent=2).encode()).decode()}
        if sha:
            payload["sha"] = sha
        resp = requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        return resp.status_code in [200,201]
    except Exception as e:
        print(f"save fail {e}")
        return False

def get_categories():
    cats = load_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)
    for c in cats:
        if "file" not in c:
            c["file"] = f"products_{c['id']}.json" if c['id'] != 'shop' else "products.json"
    if not os.path.exists(CATEGORIES_FILE):
        save_json(CATEGORIES_FILE, cats)
    return cats

def get_cat_by_id(cat_id):
    for c in get_categories():
        if c["id"] == cat_id:
            return c
    return None

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

def gen_id():
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

app = Flask(__name__)
@app.route("/")
def home():
    return "LIVE"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
def is_admin(uid): return uid == ADMIN_ID

async def post_init(app):
    await app.bot.set_my_commands([BotCommand("start", "Open Shop Menu")])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories()
    kb = []
    for c in cats:
        kb.append([InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")])
    kb.append([InlineKeyboardButton("Balance / Top Up", callback_data="balance")])
    kb.append([InlineKeyboardButton("SUPPORT", callback_data="support")])
    await update.message.reply_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

async def nudge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Click /start to open the shop menu.")

async def show_balance(q, uid):
    bal = get_user(uid).get("balance", 0)
    kb = [[InlineKeyboardButton("Top Up", callback_data="topup_choose")],[InlineKeyboardButton("Back", callback_data="back")]]
    await q.edit_message_text(f"Balance: ${bal:.2f}", reply_markup=InlineKeyboardMarkup(kb))

async def show_category(q, cat_id):
    cat = get_cat_by_id(cat_id)
    if not cat:
        await q.edit_message_text("Category not found", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
        return
    products = load_json(cat["file"], [])
    if not products:
        await q.edit_message_text(f"{cat['name']} is empty - /addproduct {cat_id} | Name | Price | Desc", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
        return
    kb = [[InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{cat_id}_{i}")] for i,p in enumerate(products)]
    kb.append([InlineKeyboardButton("Back", callback_data="back")])
    await q.edit_message_text(f"{cat['name']}:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    username = q.from_user.username or "no_username"

    if d.startswith("cat_"):
        cat_id = d.replace("cat_", "")
        await show_category(q, cat_id)
    elif d == "back":
        cats = get_categories()
        kb = []
        for c in cats:
            kb.append([InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")])
        kb.append([InlineKeyboardButton("Balance / Top Up", callback_data="balance")])
        kb.append([InlineKeyboardButton("SUPPORT", callback_data="support")])
        await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "balance":
        await show_balance(q, uid)
    elif d == "support":
        kb = [[InlineKeyboardButton("Message Support", url=f"tg://user?id={ADMIN_ID}")],[InlineKeyboardButton("Back", callback_data="back")]]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "topup_choose":
        kb = [
            [InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],
            [InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],
            [InlineKeyboardButton("Back", callback_data="balance")]
        ]
        await q.edit_message_text("Choose Top Up amount:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_amount_"):
        context.user_data["topup_amount"] = d.replace("topup_amount_", "")
        kb = [[InlineKeyboardButton("BTC", callback_data="topup_method_btc"), InlineKeyboardButton("CashApp", callback_data="topup_method_cash")]]
        await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_method_"):
        method = d.replace("topup_method_", "")
        amount = context.user_data.get("topup_amount", "20")
        order_id = gen_id()
        orders = load_json(ORDERS_FILE, [])
        orders.append({"order_id": order_id,"user_id": uid,"username": username,"product": f"TOPUP ${amount}","price": amount,"method": method,"status": "pending"})
        save_json(ORDERS_FILE, orders)
        if method == "btc":
            try:
                img = qrcode.make(BTC_WALLET)
                bio = io.BytesIO()
                img.save(bio, 'PNG')
                bio.seek(0)
                await q.message.reply_photo(photo=bio, caption=f"TOP UP Order {order_id} - ${amount}\nBTC: {BTC_WALLET}")
            except:
                await q.message.reply_text(f"Order {order_id} - ${amount} BTC: {BTC_WALLET}")
        else:
            await q.message.reply_text(f"Order {order_id} - ${amount} CashApp: {CASHAPP_TAG} Note: {order_id}")
        admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Approve {order_id}", callback_data=f"approve_{order_id}"), InlineKeyboardButton(f"Decline {order_id}", callback_data=f"decline_{order_id}")]])
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"NEW TOP UP\nUser: @{username} ({uid})\nOrder: {order_id}\nAmount: ${amount}\nMethod: {method}", reply_markup=admin_kb)
        except:
            pass
    elif d.startswith("view_"):
        try:
            parts = d.replace("view_", "").rsplit("_", 1)
            cat_id = parts[0]
            idx = int(parts[1])
            cat = get_cat_by_id(cat_id)
            if not cat:
                await q.message.reply_text("Category not found")
                return
            products = load_json(cat["file"], [])
            p = products[idx]
            order_id = gen_id()
            orders = load_json(ORDERS_FILE, [])
            orders.append({"order_id": order_id,"user_id": uid,"username": username,"product": p["name"],"price": p["price"],"status": "pending"})
            save_json(ORDERS_FILE, orders)
            msg = f"**{p['name']}**\nPrice: ${p['price']}\nDesc: {p['desc']}\n\n--- PAYMENT ---\nOrder ID: `{order_id}`\nAmount: ${p['price']}\n\nBTC: `{BTC_WALLET}`\nCashApp: `{CASHAPP_TAG}`"
            await q.message.reply_text(msg, parse_mode="Markdown")
            admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Approve {order_id}", callback_data=f"approve_{order_id}"), InlineKeyboardButton(f"Decline {order_id}", callback_data=f"decline_{order_id}")]])
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"NEW SALE\nUser: @{username} ({uid})\nOrder: {order_id}\nProduct: {p['name']}\nPrice: ${p['price']}\nCategory: {cat['name']}", reply_markup=admin_kb)
            except:
                pass
        except Exception as e:
            await q.message.reply_text(f"Error: {e}")
    elif d.startswith("approve_"):
        if not is_admin(uid): return
        order_id = d.replace("approve_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id:
                o["status"] = "approved"
                save_json(ORDERS_FILE, orders)
                if "TOPUP" in o.get("product",""):
                    add_balance(o["user_id"], float(o["price"]))
                await q.edit_message_text(f"Approved {order_id}")
                try:
                    await context.bot.send_message(chat_id=o["user_id"], text=f"Order {order_id} APPROVED!")
                except:
                    pass
                break
    elif d.startswith("decline_"):
        if not is_admin(uid): return
        order_id = d.replace("decline_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id:
                o["status"] = "declined"
                save_json(ORDERS_FILE, orders)
                await q.edit_message_text(f"Declined {order_id}")
                try:
                    await context.bot.send_message(chat_id=o["user_id"], text=f"Order {order_id} DECLINED.")
                except:
                    pass
                break

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) == 4:
            cat_id, name, price, desc = parts[0].lower(), parts[1], parts[2], parts[3]
        else:
            cat_id, name, price, desc = "shop", parts[0], parts[1], parts[2]
        cat = get_cat_by_id(cat_id)
        if not cat:
            await update.message.reply_text(f"Category {cat_id} not found. Use /listcategories")
            return
        prods = load_json(cat["file"], [])
        prods.append({"name": name, "price": price.replace("$",""), "desc": desc})
        save_json(cat["file"], prods)
        await update.message.reply_text(f"Saved {name} to {cat['name']} ({cat['file']})")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct category_id | Name | Price | Desc - {e}")

async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]
        cat_id, name = [x.strip() for x in raw.split("|", 1)]
        cat_id = cat_id.lower().replace(" ", "_")
        cats = get_categories()
        if any(c["id"] == cat_id for c in cats):
            await update.message.reply_text(f"Category {cat_id} already exists. Use /renamecategory")
            return
        file_name = f"products_{cat_id}.json" if cat_id != "shop" else "products.json"
        new_cat = {"id": cat_id, "name": name, "file": file_name}
        cats.append(new_cat)
        save_json(CATEGORIES_FILE, cats)
        save_json(file_name, [])
        await update.message.reply_text(f"Added category {name} with id {cat_id}")
    except Exception as e:
        await update.message.reply_text(f"Use: /addcategory id | Display Name\nError: {e}")

async def rename_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]
        cat_id, new_name = [x.strip() for x in raw.split("|", 1)]
        cats = get_categories()
        for c in cats:
            if c["id"] == cat_id.lower():
                c["name"] = new_name
                save_json(CATEGORIES_FILE, cats)
                await update.message.reply_text(f"Renamed {cat_id} to {new_name}")
                return
        await update.message.reply_text(f"Category {cat_id} not found")
    except Exception as e:
        await update.message.reply_text(f"Use: /renamecategory id | New Name - {e}")

async def remove_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        cat_id = update.message.text.split(" ", 1)[1].strip().lower()
        cats = get_categories()
        new_cats = [c for c in cats if c["id"] != cat_id]
        if len(new_cats) == len(cats):
            await update.message.reply_text("Not found")
            return
        save_json(CATEGORIES_FILE, new_cats)
        await update.message.reply_text(f"Removed {cat_id}. File products_{cat_id}.json still on GH but not shown.")
    except Exception as e:
        await update.message.reply_text(f"Use: /removecategory id - {e}")

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    cats = get_categories()
    txt = "Categories:\n" + "\n".join([f"{c['id']} -> {c['name']} ({c['file']})" for c in cats])
    await update.message.reply_text(txt)

def run_bot():
    b = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    b.add_handler(CommandHandler("start", start))
    b.add_handler(CommandHandler("addproduct", add_product))
    b.add_handler(CommandHandler("addcategory", add_category))
    b.add_handler(CommandHandler("renamecategory", rename_category))
    b.add_handler(CommandHandler("removecategory", remove_category))
    b.add_handler(CommandHandler("listcategories", list_categories))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, nudge_start))
    b.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
