import os, json, threading, base64, requests, random, string
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

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

FILES = {"shop": "products.json","shop_tees": "products_tees.json","shop_accessories": "products_accessories.json"}
ORDERS_FILE = "orders.json"

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
    except:
        return False

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
    # This makes the blue Menu button show /start
    await app.bot.set_my_commands([BotCommand("start", "Open Shop Menu")])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
          [InlineKeyboardButton("🥊Shop Accounts", callback_data="shop_tees")],
          [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
          [InlineKeyboardButton("SUPPORT", callback_data="support")]]
    await update.message.reply_text("Welcome to SAINTLOCK CC - Click a category below:", reply_markup=InlineKeyboardMarkup(kb))

async def nudge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # if user types anything else, tell them to hit start
    await update.message.reply_text("👋 Welcome! Click /start to open the shop menu.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    username = q.from_user.username or "no_username"

    if d in FILES:
        products = load_json(FILES[d], [])
        if not products:
            await q.edit_message_text(f"{d} empty", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
            return
        kb = [[InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{d}_{i}")] for i,p in enumerate(products)]
        kb.append([InlineKeyboardButton("Back", callback_data="back")])
        await q.edit_message_text(f"{d}:", reply_markup=InlineKeyboardMarkup(kb))

    elif d == "back":
        kb = [[InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
              [InlineKeyboardButton("🥊Shop Accounts", callback_data="shop_tees")],
              [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
              [InlineKeyboardButton("SUPPORT", callback_data="support")]]
        await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

    elif d == "support":
        kb = [[InlineKeyboardButton("Message Support", url=f"tg://user?id={ADMIN_ID}")],
              [InlineKeyboardButton("Back", callback_data="back")]]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("view_"):
        try:
            rest = d.replace("view_", "")
            cat_key = "shop"
            if "shop_tees" in rest:
                cat_key = "shop_tees"
                idx = int(rest.replace("shop_tees_", ""))
            elif "shop_accessories" in rest:
                cat_key = "shop_accessories"
                idx = int(rest.replace("shop_accessories_", ""))
            else:
                idx = int(rest.replace("shop_", ""))
            
            products = load_json(FILES[cat_key], [])
            p = products[idx]
            order_id = gen_id()
            
            orders = load_json(ORDERS_FILE, [])
            orders.append({"order_id": order_id,"user_id": uid,"username": username,"product": p["name"],"price": p["price"],"status": "pending"})
            save_json(ORDERS_FILE, orders)

            msg = f"**{p['name']}**\nPrice: ${p['price']}\nDesc: {p['desc']}\n\n--- PAYMENT ---\nOrder ID: `{order_id}`\nAmount: ${p['price']}\n\nBTC: `{BTC_WALLET}`\nCashApp: `{CASHAPP_TAG}`\n\nSend proof with Order ID."
            await q.message.reply_text(msg, parse_mode="Markdown")

            admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Approve {order_id}", callback_data=f"approve_{order_id}"), InlineKeyboardButton(f"Decline {order_id}", callback_data=f"decline_{order_id}")]])
            admin_msg = f"NEW SALE\nUser: @{username} ({uid})\nOrder: {order_id}\nProduct: {p['name']}\nPrice: ${p['price']}"
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=admin_kb)
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
                await q.edit_message_text(f"Approved {order_id} - @{o['username']}")
                try:
                    await context.bot.send_message(chat_id=o["user_id"], text=f"Order {order_id} APPROVED! Contact @{SUPPORT_USERNAME}")
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
                    await context.bot.send_message(chat_id=o["user_id"], text=f"Order {order_id} DECLINED. Contact @{SUPPORT_USERNAME}")
                except:
                    pass
                break

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        cat_key, name, price, desc = (parts[0].lower(), parts[1], parts[2], parts[3]) if len(parts)==4 else ("shop", parts[0], parts[1], parts[2])
        if cat_key not in FILES: cat_key = "shop"
        prods = load_json(FILES[cat_key], [])
        prods.append({"name": name, "price": price.replace("$",""), "desc": desc})
        save_json(FILES[cat_key], prods)
        await update.message.reply_text(f"Saved {name}")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc - {e}")

def run_bot():
    b = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    b.add_handler(CommandHandler("start", start))
    b.add_handler(CommandHandler("addproduct", add_product))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, nudge_start))
    b.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
