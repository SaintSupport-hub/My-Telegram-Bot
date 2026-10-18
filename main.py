import os, json, threading, base64, requests, random, string, io, time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import qrcode

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport")
BTC_WALLET = os.getenv("BTC_WALLET", "bc1q...")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "SaintSupport-hub/My-Telegram-Bot")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")

CATEGORIES_FILE = "categories.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

DEFAULT_CATEGORIES = [
    {"id": "shop", "name": "🛒Shop CC", "file": "products.json"},
    {"id": "shop_tees", "name": "🥊Shop Accounts", "file": "products_tees.json"},
    {"id": "shop_accessories", "name": "🥇Shop BINs", "file": "products_accessories.json"}
]

def gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd. github.v3+json"}

def load_json(path, default):
    local = None
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                local = json.load(f)
        except:
            pass
    gh = None
    if GITHUB_TOKEN:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
            r = requests.get(url, headers=gh_headers(), timeout=15)
            if r.status_code == 200:
                gh = json.loads(base64.b64decode(r.json()["content"]).decode())
        except:
            pass
    if path == USERS_FILE and local and gh:
        merged = gh.copy()
        for uid, info in local.items():
            if uid not in merged or float(info.get("balance",0)) > float(merged[uid].get("balance",0)):
                merged[uid] = info
        with open(path, "w") as f:
            json.dump(merged, f, indent=2)
        return merged
    if local is not None:
        return local
    if gh is not None:
        with open(path, "w") as f:
            json.dump(gh, f, indent=2)
        return gh
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    if not GITHUB_TOKEN:
        return True
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": f"Update {path}", "content": base64.b64encode(json.dumps(data, indent=2).encode()).decode()}
        if sha:
            payload["sha"] = sha
        resp = requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        return resp.status_code in [200,201]
    except:
        return False

def get_categories():
    cats = load_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)
    for c in cats:
        if "file" not in c:
            c["file"] = f"products_{c['id']}.json" if c['id'] != 'shop' else "products.json"
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
    return users[s]["balance"]

def deduct_balance(uid, amt):
    users = load_json(USERS_FILE, {})
    s = str(uid)
    if s not in users:
        return 0
    if float(users[s].get("balance",0)) < float(amt):
        return None
    users[s]["balance"] = float(users[s].get("balance", 0)) - float(amt)
    save_json(USERS_FILE, users)
    return users[s]["balance"]

def gen_id():
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def keep_alive_loop():
    while True:
        time.sleep(600)
        try:
            if RENDER_URL:
                requests.get(RENDER_URL, timeout=10)
            requests.get("http://localhost:10000/", timeout=5)
        except:
            pass

def get_order_complete_message(order_id, username, user_id, product_name):
    return f"""✅ PURCHASE SUCCESSFUL!

Order #: {order_id}
Username: @{username}
User ID: {user_id}
Product: {product_name}

Please contact @Saintlocksupport with your order # and screenshot of the receipt to receive your order. Happy Shopping!!!"""

app = Flask(__name__)
@app.route("/")
def home():
    return "LIVE - SAINTLOCK CC BOT RUNNING 24/7"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
def is_admin(uid): return uid == ADMIN_ID

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Open Shop Menu"),
        BotCommand("listproducts", "List products"),
        BotCommand("addbalance", "Add balance")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories()
    kb = [[InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")] for c in cats]
    kb.append([InlineKeyboardButton("Balance / Top Up", callback_data="balance")])
    kb.append([InlineKeyboardButton("SUPPORT", callback_data="support")])
    await update.message.reply_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

async def show_balance(q, uid):
    bal = get_user(uid).get("balance", 0)
    kb = [[InlineKeyboardButton("Top Up", callback_data="topup_choose")],[InlineKeyboardButton("Back", callback_data="back")]]
    await q.edit_message_text(f"Balance: ${bal:.2f}", reply_markup=InlineKeyboardMarkup(kb))

async def show_category(q, cat_id, is_admin_view=False):
    cat = get_cat_by_id(cat_id)
    products = load_json(cat["file"], [])
    if not products:
        await q.edit_message_text(f"{cat['name']} is empty", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
        return
    kb = []
    for i, p in enumerate(products):
        kb.append([InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{cat_id}_{i}")])
        if is_admin_view:
            kb.append([InlineKeyboardButton(f"Edit {i}", callback_data=f"admin_edit_{cat_id}_{i}"), InlineKeyboardButton(f"Del {i}", callback_data=f"admin_del_{cat_id}_{i}")])
    kb.append([InlineKeyboardButton("Back", callback_data="back")])
    await q.edit_message_text(f"{cat['name']} - {len(products)} items:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    username = q.from_user.username or "no_username"
    admin_view = is_admin(uid)

    if d.startswith("cat_"):
        await show_category(q, d.replace("cat_", ""), is_admin_view=admin_view)
    elif d == "back":
        cats = get_categories()
        kb = [[InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")] for c in cats]
        kb.append([InlineKeyboardButton("Balance / Top Up", callback_data="balance")])
        kb.append([InlineKeyboardButton("SUPPORT", callback_data="support")])
        await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "balance":
        await show_balance(q, uid)
    elif d == "support":
        kb = [[InlineKeyboardButton("Message Support", url=f"tg://user?id={ADMIN_ID}")],[InlineKeyboardButton("Back", callback_data="back")]]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "topup_choose":
        kb = [[InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],[InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],[InlineKeyboardButton("Back", callback_data="balance")]]
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
        parts = d.replace("view_", "").rsplit("_", 1)
        cat_id = parts[0]
        idx = int(parts[1])
        cat = get_cat_by_id(cat_id)
        products = load_json(cat["file"], [])
        p = products[idx]
        bal = get_user(uid).get("balance", 0)
        order_id = gen_id()
        orders = load_json(ORDERS_FILE, [])
        orders.append({"order_id": order_id,"user_id": uid,"username": username,"product": p["name"],"price": p["price"],"status": "pending", "category": cat_id, "product_idx": idx})
        save_json(ORDERS_FILE, orders)
        text = f"*{p['name']}*\n\nPrice: ${p['price']}\n\nDesc: {p['desc']}\n\nYour Balance: ${bal:.2f}\n\nOrder ID: `{order_id}`\n\nChoose payment method:"
        kb = [
            [InlineKeyboardButton(f"Pay with Balance (${bal:.2f})", callback_data=f"paybal_{order_id}")],
            [InlineKeyboardButton("Pay with Bitcoin", callback_data=f"paybtc_{order_id}")],
            [InlineKeyboardButton("Pay with CashApp", callback_data=f"paycash_{order_id}")],
            [InlineKeyboardButton("Back", callback_data=f"cat_{cat_id}")]
        ]
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("paybal_"):
        order_id = d.replace("paybal_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["user_id"] == uid:
                price = float(o["price"])
                bal = get_user(uid).get("balance", 0)
                if bal < price:
                    await q.message.reply_text(f"Not enough balance. You have ${bal:.2f}, need ${price:.2f}.")
                    return
                new_bal = deduct_balance(uid, price)
                o["status"] = "approved_balance"
                save_json(ORDERS_FILE, orders)
                cat = get_cat_by_id(o.get("category","shop"))
                prod = load_json(cat["file"], [])[o.get("product_idx",0)] if o.get("product_idx") is not None else {"name": o["product"]}
                complete_msg = get_order_complete_message(order_id, username, uid, prod['name'])
                await q.message.reply_text(complete_msg)
                try:
                    await context.bot.send_message(chat_id=ADMIN_ID, text=f"BALANCE PURCHASE\n{complete_msg}\nNew Bal: ${new_bal:.2f}")
                except:
                    pass
                break
    elif d.startswith("paybtc_"):
        order_id = d.replace("paybtc_", "")
        await q.message.reply_text(f"Order {order_id}\nBTC: `{BTC_WALLET}`\nNote: {order_id}", parse_mode="Markdown")
    elif d.startswith("paycash_"):
        order_id = d.replace("paycash_", "")
        await q.message.reply_text(f"Order {order_id}\nCashApp: `{CASHAPP_TAG}`\nNote: {order_id}", parse_mode="Markdown")
    elif d.startswith("admin_del_"):
        if not is_admin(uid): return
        full = d.replace("admin_del_", "")
        cat_id, idx = full.rsplit("_", 1)
        cat = get_cat_by_id(cat_id)
        prods = load_json(cat["file"], [])
        removed = prods.pop(int(idx))
        save_json(cat["file"], prods)
        await q.edit_message_text(f"Deleted {removed['name']}")
    elif d.startswith("admin_edit_"):
        if not is_admin(uid): return
        full = d.replace("admin_edit_", "")
        cat_id, idx = full.rsplit("_", 1)
        p = load_json(get_cat_by_id(cat_id)["file"], [])[int(idx)]
        await q.message.reply_text(f"/editproduct {cat_id} | {idx} | {p['name']} | {p['price']} | {p['desc']}")
    elif d.startswith("approve_"):
        if not is_admin(uid): return
        order_id = d.replace("approve_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id:
                o["status"] = "approved"
                save_json(ORDERS_FILE, orders)
                if "TOPUP" in str(o.get("product","")):
                    amt = o.get("price") or o.get("amount") or 0
                    new_bal = add_balance(o["user_id"], float(amt))
                    await q.edit_message_text(f"Approved {order_id} - New bal: ${new_bal:.2f}")
                    try:
                        await context.bot.send_message(chat_id=o["user_id"], text=f"Approved! ${amt} added!\nNew Balance: ${new_bal:.2f}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Check Balance", callback_data="balance")]]))
                    except:
                        pass
                else:
                    cat = get_cat_by_id(o.get("category","shop"))
                    prod = load_json(cat["file"], [])[o.get("product_idx",0)] if o.get("product_idx") is not None else {"name": o["product"]}
                    await q.edit_message_text(f"Approved {order_id}")
                    try:
                        complete_msg = get_order_complete_message(order_id, o.get("username","no_username"), o["user_id"], prod['name'])
                        await context.bot.send_message(chat_id=o["user_id"], text=complete_msg)
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
                break

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    raw = update.message.text.split(" ", 1)[1]
    parts = [x.strip() for x in raw.split("|")]
    if len(parts) == 4:
        cat_id, name, price, desc = parts[0].lower(), parts[1], parts[2], parts[3]
    else:
        cat_id, name, price, desc = "shop", parts[0], parts[1], parts[2]
    cat = get_cat_by_id(cat_id)
    prods = load_json(cat["file"], [])
    prods.append({"name": name, "price": price.replace("$",""), "desc": desc})
    save_json(cat["file"], prods)
    await update.message.reply_text(f"Saved {name} - Total {len(prods)}")

async def add_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    raw = update.message.text.split(" ", 1)[1]
    uid_str, amt = [x.strip() for x in raw.split("|")]
    new_bal = add_balance(int(uid_str) if uid_str.isdigit() else uid_str, float(amt))
    await update.message.reply_text(f"Added ${amt} to {uid_str} - New bal ${new_bal:.2f}")

def run_bot():
    b = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    b.add_handler(CommandHandler("start", start))
    b.add_handler(CommandHandler("addproduct", add_product))
    b.add_handler(CommandHandler("addbalance", add_balance_cmd))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: None))
    b.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=keep_alive_loop, daemon=True).start()
    run_bot()
