import os, json, threading, base64, requests, random, string, io, time, re
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import qrcode

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport")
BTC_WALLET = os.getenv("BTC_WALLET", "bc1q...")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")
GH_TOKEN = os.getenv("GITHUB_"+"TOKEN")
GH_REPO = os.getenv("GITHUB_"+"REPO", "SaintSupport-hub/My-Telegram-Bot")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")

CATEGORIES_FILE = "categories.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"
CARTS_FILE = "carts.json"

DEFAULT_CATEGORIES = [
    {"id": "shop", "name": "🛒Shop CC", "file": "products.json"},
    {"id": "shop_low", "name": "⬇️SHOP LOW % SNIFF [Med-Low Bal]", "file": "products_low.json"},
    {"id": "shop_high", "name": "⬆️SHOP HIGH % SNIFF [High Bal]", "file": "products_high.json"},
    {"id": "shop_tees", "name": "🥊Shop Accounts", "file": "products_tees.json"},
    {"id": "shop_accessories", "name": "🥇Shop BINs", "file": "products_accessories.json"},
    {"id": "shop_food", "name": "🥙Shop Food", "file": "products_food.json"}
]

MAIN_MENU_IDS = ["shop", "shop_tees", "shop_accessories", "shop_food"]

def gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_json(path, default):
    local = None
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                local = json.load(f)
        except:
            pass
    gh = None
    if GH_TOKEN:
        try:
            url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
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
    if path == CATEGORIES_FILE and local and gh:
        final = []
        seen = set()
        for src in [gh, local, DEFAULT_CATEGORIES]:
            for c in src:
                if c["id"] not in seen:
                    final.append(c)
                    seen.add(c["id"])
        for c in final:
            if c["id"] == "shop_low":
                c["file"] = "products_low.json"
            if c["id"] == "shop_high":
                c["file"] = "products_high.json"
        with open(path, "w") as f:
            json.dump(final, f, indent=2)
        return final
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
    if not GH_TOKEN:
        return True
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

def get_categories():
    cats = load_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)
    for dc in DEFAULT_CATEGORIES:
        if not any(c["id"] == dc["id"] for c in cats):
            cats.append(dc)
    for c in cats:
        if c["id"] == "shop_low":
            c["file"] = "products_low.json"
        elif c["id"] == "shop_high":
            c["file"] = "products_high.json"
        elif c["id"] == "shop":
            c["file"] = "products.json"
        elif "file" not in c:
            c["file"] = f"products_{c['id']}.json"
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

def get_cart(uid):
    carts = load_json(CARTS_FILE, {})
    return carts.get(str(uid), [])

def save_cart(uid, items):
    carts = load_json(CARTS_FILE, {})
    carts[str(uid)] = items
    save_json(CARTS_FILE, carts)

def add_to_cart(uid, item):
    carts = load_json(CARTS_FILE, {})
    s = str(uid)
    if s not in carts:
        carts[s] = []
    carts[s].append(item)
    save_json(CARTS_FILE, carts)
    return len(carts[s])

def clear_cart(uid):
    carts = load_json(CARTS_FILE, {})
    s = str(uid)
    carts[s] = []
    save_json(CARTS_FILE, carts)

def get_cart_total(uid):
    cart = get_cart(uid)
    total = 0
    for it in cart:
        total += float(it.get("total", 0))
    return total, len(cart)

def parse_options_string(opts_raw):
    if not opts_raw:
        return []
    result = []
    parts = [p.strip() for p in opts_raw.split(",") if p.strip()]
    for part in parts:
        if ":" in part:
            name_part, price_part = part.rsplit(":", 1)
            price_part = price_part.replace("$","").strip()
            try:
                price = float(price_part)
                if name_part.strip().replace(" ","").replace("-","").replace(":","").isdigit():
                    continue
                result.append({"name": name_part.strip(), "price": price})
                continue
            except:
                pass
        if "$" in part:
            name_part, price_part = part.rsplit("$", 1)
            price_part = price_part.strip()
            try:
                price = float(price_part)
                result.append({"name": name_part.strip(), "price": price})
                continue
            except:
                pass
        if re.match(r"^\d+\s*[:\-]\s*\d+$", part) or part.isdigit():
            continue
        result.append({"name": part.strip(), "price": None})
    return result

def parse_minmax_string(s):
    s = s.strip()
    if not s:
        return 1, 999
    s = s.replace(" ", "")
    if ":" in s:
        a,b = s.split(":",1)
        try:
            return int(float(a)), int(float(b))
        except:
            return 1,999
    if "-" in s:
        a,b = s.split("-",1)
        try:
            return int(float(a)), int(float(b))
        except:
            return 1,999
    try:
        min_q = int(float(s))
        return min_q, 999
    except:
        return 1,999

def is_minmax_string(s):
    s = s.strip()
    if not s:
        return False
    if re.match(r"^\d+$", s):
        return True
    if re.match(r"^\d+\s*[:\-]\s*\d+$", s):
        return True
    return False

app = Flask(__name__)
@app.route("/")
def home():
    return "LIVE - SAINTLOCK CC BOT RUNNING 24/7 - CART EDITION"
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
def is_admin(uid): return uid == ADMIN_ID

async def post_init(app):
    await app.bot.set_my_commands([BotCommand("start", "Open Shop Menu")])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories()
    total, count = get_cart_total(update.effective_user.id)
    kb = []
    for c in cats:
        if c["id"] in MAIN_MENU_IDS:
            kb.append([InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")])
    kb.append([InlineKeyboardButton(f"Cart ({count}) - ${total:.2f}" if count>0 else "Cart (0)", callback_data="viewcart")])
    kb.append([InlineKeyboardButton("Balance / Top Up", callback_data="balance")])
    kb.append([InlineKeyboardButton("SUPPORT", callback_data="support")])
    await update.message.reply_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

async def show_balance(q, uid):
    bal = get_user(uid).get("balance", 0)
    kb = [[InlineKeyboardButton("Top Up", callback_data="topup_choose")],[InlineKeyboardButton("Back", callback_data="back")]]
    await q.edit_message_text(f"Balance: ${bal:.2f}", reply_markup=InlineKeyboardMarkup(kb))

async def show_category(q, cat_id, is_admin_view=False):
    cat = get_cat_by_id(cat_id)
    if not cat:
        await q.edit_message_text(f"Category {cat_id} not found", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
        return
    products = load_json(cat["file"], [])
    if not products:
        await q.edit_message_text(f"{cat['name']} is empty - No products yet\nFile: {cat['file']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
        return
    kb = []
    for i, p in enumerate(products):
        opts = p.get("options", [])
        min_q = p.get("min_qty",1)
        qty_info = f" Min:{min_q}" if min_q > 1 else ""
        opts_text = f" ({len(opts)} opts)" if opts else ""
        kb.append([InlineKeyboardButton(f"{p['name']} - ${p['price']}{opts_text}{qty_info}", callback_data=f"view_{cat_id}_{i}")])
        if is_admin_view:
            kb.append([InlineKeyboardButton(f"Edit {i}", callback_data=f"admin_edit_{cat_id}_{i}"), InlineKeyboardButton(f"Del {i}", callback_data=f"admin_del_{cat_id}_{i}")])
    kb.append([InlineKeyboardButton("Back", callback_data="back")])
    await q.edit_message_text(f"{cat['name']} - {len(products)} items:", reply_markup=InlineKeyboardMarkup(kb))

async def show_cart(q, uid):
    cart = get_cart(uid)
    bal = get_user(uid).get("balance", 0)
    if not cart:
        kb = [[InlineKeyboardButton("Back", callback_data="back")]]
        await q.edit_message_text("Cart is empty.\nAdd items from shop first.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    total = 0
    lines = []
    for idx, it in enumerate(cart):
        total += float(it.get("total",0))
        lines.append(f"{idx+1}. {it['name']} {it.get('option','')} x{it['qty']} = ${it['total']:.2f}")
    txt = "Your Cart:\n\n" + "\n".join(lines) + f"\n\nTotal: ${total:.2f}\nBalance: ${bal:.2f}"
    kb = []
    for idx in range(len(cart)):
        kb.append([InlineKeyboardButton(f"Remove {idx+1}", callback_data=f"cartdel_{idx}")])
    kb.append([InlineKeyboardButton("Clear Cart", callback_data="cartclear")])
    kb.append([InlineKeyboardButton(f"Pay ${total:.2f} with Balance (${bal:.2f})", callback_data="cartpay_bal")])
    kb.append([InlineKeyboardButton(f"Pay ${total:.2f} Bitcoin", callback_data="cartpay_btc")])
    kb.append([InlineKeyboardButton(f"Pay ${total:.2f} CashApp", callback_data="cartpay_cash")])
    kb.append([InlineKeyboardButton("Back to Shop", callback_data="back")])
    await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    username = q.from_user.username or "no_username"
    admin_view = is_admin(uid)

    if d == "cat_shop":
        kb = [
            [InlineKeyboardButton("SHOP LOW % SNIFF [Med-Low Bal]", callback_data="cat_shop_low")],
            [InlineKeyboardButton("SHOP HIGH % SNIFF [High Bal]", callback_data="cat_shop_high")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        await q.edit_message_text("Shop CC - Choose Type:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("cat_"):
        await show_category(q, d.replace("cat_", ""), is_admin_view=admin_view)
        return
    elif d == "back":
        cats = get_categories()
        total, count = get_cart_total(uid)
        kb = []
        for c in cats:
            if c["id"] in MAIN_MENU_IDS:
                kb.append([InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")])
        kb.append([InlineKeyboardButton(f"Cart ({count}) - ${total:.2f}" if count>0 else "Cart (0)", callback_data="viewcart")])
        kb.append([InlineKeyboardButton("Balance / Top Up", callback_data="balance")])
        kb.append([InlineKeyboardButton("SUPPORT", callback_data="support")])
        await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))
        return
    elif d == "balance":
        await show_balance(q, uid)
        return
    elif d == "viewcart":
        await show_cart(q, uid)
        return
    elif d == "support":
        kb = [[InlineKeyboardButton("Message Support", url=f"tg://user?id={ADMIN_ID}")],[InlineKeyboardButton("Back", callback_data="back")]]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
        return
    elif d == "topup_choose":
        kb = [[InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],[InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],[InlineKeyboardButton("Back", callback_data="balance")]]
        await q.edit_message_text("Choose Top Up amount:", reply_markup=InlineKeyboardMarkup(kb))
        return
    elif d.startswith("topup_amount_"):
        context.user_data["topup_amount"] = d.replace("topup_amount_", "")
        kb = [[InlineKeyboardButton("BTC", callback_data="topup_method_btc"), InlineKeyboardButton("CashApp", callback_data="topup_method_cash")]]
        await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
        return
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
        return
    elif d.startswith("cartdel_"):
        idx = int(d.replace("cartdel_", ""))
        carts = load_json(CARTS_FILE, {})
        s = str(uid)
        if s in carts and 0 <= idx < len(carts[s]):
            carts[s].pop(idx)
            save_json(CARTS_FILE, carts)
        await show_cart(q, uid)
        return
    elif d == "cartclear":
        clear_cart(uid)
        await show_cart(q, uid)
        return
    elif d.startswith("cartpay_"):
        method = d.replace("cartpay_", "")
        cart = get_cart(uid)
        if not cart:
            await q.edit_message_text("Cart empty", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
            return
        total = sum(float(it.get("total",0)) for it in cart)
        order_id = gen_id()
        orders = load_json(ORDERS_FILE, [])
        item_list = "\n".join([f"- {it['name']} {it.get('option','')} x{it['qty']} = ${it['total']:.2f}" for it in cart])
        orders.append({"order_id": order_id,"user_id": uid,"username": username,"product": f"CART {len(cart)} items","price": total,"method": method,"status": "pending_cart" if method!="bal" else "approved_balance_cart","items": cart, "total": total})
        save_json(ORDERS_FILE, orders)
        if method == "bal":
            bal = get_user(uid).get("balance",0)
            if bal < total:
                await q.message.reply_text(f"Not enough balance. You have ${bal:.2f}, need ${total:.2f}")
                return
            new_bal = deduct_balance(uid, total)
            clear_cart(uid)
            msg = f"CART PURCHASE SUCCESSFUL!\n\nOrder #: {order_id}\nUser: @{username} ({uid})\nItems:\n{item_list}\n\nTotal Paid: ${total:.2f}\nNew Balance: ${new_bal:.2f}\n\nContact @Saintlocksupport with order #"
            await q.message.reply_text(msg)
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"CART BALANCE PURCHASE\n{msg}")
            except:
                pass
        elif method == "btc":
            clear_cart(uid)
            await q.message.reply_text(f"Order {order_id}\nTotal: ${total:.2f}\nItems:\n{item_list}\n\nBTC: {BTC_WALLET}\nNote: {order_id}", parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"CART BTC ORDER {order_id}\nUser @{username} ({uid})\nTotal ${total:.2f}\n{item_list}")
            except:
                pass
        else:
            clear_cart(uid)
            await q.message.reply_text(f"Order {order_id}\nTotal: ${total:.2f}\nItems:\n{item_list}\n\nCashApp: {CASHAPP_TAG}\nNote: {order_id}", parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"CART CASHAPP ORDER {order_id}\nUser @{username} ({uid})\nTotal ${total:.2f}\n{item_list}")
            except:
                pass
        return

    if d.startswith("view_"):
        parts = d.replace("view_", "").rsplit("_", 1)
        cat_id = parts[0]
        idx = int(parts[1])
        cat = get_cat_by_id(cat_id)
        products = load_json(cat["file"], [])
        if idx >= len(products):
            await q.message.reply_text("Product not found")
            return
        p = products[idx]
        min_q = int(p.get("min_qty",1))
        context.user_data[f"qty_{cat_id}_{idx}"] = min_q
        context.user_data[f"opt_{cat_id}_{idx}"] = ""
        context.user_data[f"optprice_{cat_id}_{idx}"] = float(p["price"])
        await send_product_view(q, cat_id, idx, context, uid)
        return

    if d.startswith("seloptview_"):
        rest = d.replace("seloptview_", "")
        try:
            cat_part, idx_part, opt_name = rest.split("|", 2)
            cat_id = cat_part
            idx = int(idx_part)
            cat = get_cat_by_id(cat_id)
            prod = load_json(cat["file"], [])[idx]
            opt_price = float(prod["price"])
            for o in prod.get("options", []):
                if isinstance(o, dict) and o["name"] == opt_name:
                    if o.get("price") is not None:
                        opt_price = float(o["price"])
                    break
            context.user_data[f"opt_{cat_id}_{idx}"] = opt_name
            context.user_data[f"optprice_{cat_id}_{idx}"] = opt_price
            await send_product_view(q, cat_id, idx, context, uid)
        except Exception as e:
            await q.answer(f"Error {e}")
        return

    if d.startswith("qtyviewminus_") or d.startswith("qtyviewplus_"):
        is_plus = d.startswith("qtyviewplus_")
        rest = d.replace("qtyviewminus_", "").replace("qtyviewplus_", "")
        try:
            cat_id, idx_str = rest.rsplit("|",1)
            idx = int(idx_str)
            cat = get_cat_by_id(cat_id)
            prod = load_json(cat["file"], [])[idx]
            min_q = int(prod.get("min_qty",1))
            max_q = int(prod.get("max_qty",999))
            key = f"qty_{cat_id}_{idx}"
            qty = int(context.user_data.get(key, min_q))
            if is_plus:
                if qty < max_q:
                    qty += 1
                else:
                    await q.answer(f"Max is {max_q}", show_alert=True)
                    return
            else:
                if qty > min_q:
                    qty -= 1
                else:
                    await q.answer(f"Min is {min_q}", show_alert=True)
                    return
            context.user_data[key] = qty
            await send_product_view(q, cat_id, idx, context, uid)
        except Exception as e:
            await q.answer(f"Error {e}")
        return

    if d.startswith("addcart_"):
        rest = d.replace("addcart_", "")
        cat_id, idx_str = rest.rsplit("|",1)
        idx = int(idx_str)
        cat = get_cat_by_id(cat_id)
        prod = load_json(cat["file"], [])[idx]
        qty = int(context.user_data.get(f"qty_{cat_id}_{idx}", int(prod.get("min_qty",1))))
        opt = context.user_data.get(f"opt_{cat_id}_{idx}", "")
        unit = float(context.user_data.get(f"optprice_{cat_id}_{idx}", float(prod["price"])))
        total = unit * qty
        item = {"name": prod["name"], "category": cat_id, "product_idx": idx, "option": opt, "unit_price": unit, "qty": qty, "total": total}
        count = add_to_cart(uid, item)
        await q.answer(f"Added to cart! Cart now {count} items", show_alert=False)
        await send_product_view(q, cat_id, idx, context, uid, added=True)
        return

    if d.startswith("buynow_"):
        rest = d.replace("buynow_", "")
        cat_id, idx_str = rest.rsplit("|",1)
        idx = int(idx_str)
        cat = get_cat_by_id(cat_id)
        prod = load_json(cat["file"], [])[idx]
        qty = int(context.user_data.get(f"qty_{cat_id}_{idx}", int(prod.get("min_qty",1))))
        opt = context.user_data.get(f"opt_{cat_id}_{idx}", "")
        unit = float(context.user_data.get(f"optprice_{cat_id}_{idx}", float(prod["price"])))
        total = unit * qty
        bal = get_user(uid).get("balance", 0)
        order_id = gen_id()
        orders = load_json(ORDERS_FILE, [])
        orders.append({"order_id": order_id,"user_id": uid,"username": username,"product": prod["name"],"price": unit,"quantity": qty,"total": total,"selected_option": opt,"selected_price": unit,"category": cat_id,"product_idx": idx,"method": "buynow","status": "pending"})
        save_json(ORDERS_FILE, orders)
        txt = f"{prod['name']}\nOpt: {opt}\nQty: {qty} x ${unit:.2f} = ${total:.2f}\n\nOrder ID: {order_id}"
        kb = [
            [InlineKeyboardButton(f"Pay ${total:.2f} with Balance (${bal:.2f})", callback_data=f"paybalnow_{order_id}")],
            [InlineKeyboardButton(f"Pay ${total:.2f} Bitcoin", callback_data=f"paybtcnow_{order_id}")],
            [InlineKeyboardButton(f"Pay ${total:.2f} CashApp", callback_data=f"paycashnow_{order_id}")],
            [InlineKeyboardButton("Back", callback_data=f"cat_{cat_id}")]
        ]
        await q.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("paybalnow_") or d.startswith("paybtcnow_") or d.startswith("paycashnow_"):
        order_id = d.split("_",1)[1].replace("balnow_","").replace("btcnow_","").replace("cashnow_","")
        method = "bal" if "balnow" in d else "btc" if "btcnow" in d else "cash"
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id:
                total = float(o.get("total", o.get("price",0)))
                if method == "bal":
                    bal = get_user(uid).get("balance",0)
                    if bal < total:
                        await q.message.reply_text(f"Need ${total:.2f}, you have ${bal:.2f}")
                        return
                    new_bal = deduct_balance(uid, total)
                    o["status"] = "approved_balance"
                    save_json(ORDERS_FILE, orders)
                    await q.message.reply_text(f"BUY NOW SUCCESS!\nOrder {order_id}\n{ o['product']} {o.get('selected_option','')} x{o.get('quantity',1)} = ${total:.2f}\nNew Bal ${new_bal:.2f}\nContact @Saintlocksupport")
                    try:
                        await context.bot.send_message(chat_id=ADMIN_ID, text=f"BUY NOW BAL {order_id} @{username} ${total:.2f}")
                    except:
                        pass
                elif method == "btc":
                    o["status"] = "pending_btc"
                    save_json(ORDERS_FILE, orders)
                    await q.message.reply_text(f"Order {order_id} Total ${total:.2f} BTC: {BTC_WALLET} Note: {order_id}", parse_mode="Markdown")
                else:
                    o["status"] = "pending_cash"
                    save_json(ORDERS_FILE, orders)
                    await q.message.reply_text(f"Order {order_id} Total ${total:.2f} CashApp: {CASHAPP_TAG} Note: {order_id}", parse_mode="Markdown")
                break
        return

    if d.startswith("admin_del_"):
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
        opts = ", ".join([f"{o['name']}:{o['price']}" if isinstance(o, dict) and o.get('price') is not None else o['name'] if isinstance(o, dict) else str(o) for o in p.get("options",[])])
        minmax = f"{p.get('min_qty',1)}:{p.get('max_qty',999)}"
        await q.message.reply_text(f"/editproduct {cat_id} | {idx} | {p['name']} | {p['price']} | {p['desc']} | {opts} | {minmax}")
    elif d.startswith("approve_"):
        if not is_admin(uid): return
        order_id = d.replace("approve_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id:
                o["status"] = "approved"
                save_json(ORDERS_FILE, orders)
                if "TOPUP" in str(o.get("product","")):
                    amt = o.get("price") or 0
                    new_bal = add_balance(o["user_id"], float(amt))
                    await q.edit_message_text(f"Approved {order_id} - New bal: ${new_bal:.2f}")
                    try:
                        await context.bot.send_message(chat_id=o["user_id"], text=f"Approved! ${amt} added! New Balance: ${new_bal:.2f}")
                    except:
                        pass
                else:
                    await q.edit_message_text(f"Approved {order_id}")
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

async def send_product_view(q, cat_id, idx, context, uid, added=False):
    cat = get_cat_by_id(cat_id)
    prod = load_json(cat["file"], [])[idx]
    min_q = int(prod.get("min_qty",1))
    max_q = int(prod.get("max_qty",999))
    qty = int(context.user_data.get(f"qty_{cat_id}_{idx}", min_q))
    opt = context.user_data.get(f"opt_{cat_id}_{idx}", "")
    unit = float(context.user_data.get(f"optprice_{cat_id}_{idx}", float(prod["price"])))
    total = unit * qty
    bal = get_user(uid).get("balance", 0)
    cart_total, cart_count = get_cart_total(uid)
    options = prod.get("options", [])
    opt_text = ""
    if options:
        lines = []
        for o in options:
            if isinstance(o, dict):
                if o.get("price") is not None:
                    lines.append(f"• {o['name']} - ${o['price']:.2f}")
                else:
                    lines.append(f"• {o['name']}")
            else:
                lines.append(f"• {o}")
        opt_text = "\n\nAvailable Options:\n" + "\n".join(lines)
    sel_text = f"\nSelected: {opt} - ${unit:.2f}" if opt else ""
    added_text = "\n\nAdded to cart!" if added else ""
    text = f"{prod['name']}{sel_text}\n\nUnit: ${unit:.2f}\nDesc: {prod['desc']}\nMin: {min_q} | Max: {max_q}{opt_text}\n\nQty: {qty} x ${unit:.2f} = ${total:.2f}\nBalance: ${bal:.2f} | Cart: {cart_count} items ${cart_total:.2f}{added_text}"
    kb = []
    if options:
        for o in options:
            name = o["name"] if isinstance(o, dict) else str(o)
            price_show = f" ${o['price']:.2f}" if isinstance(o, dict) and o.get("price") is not None else ""
            kb.append([InlineKeyboardButton(f"{name}{price_show}", callback_data=f"seloptview_{cat_id}|{idx}|{name}")])
    kb.append([
        InlineKeyboardButton("-", callback_data=f"qtyviewminus_{cat_id}|{idx}"),
        InlineKeyboardButton(f"Qty: {qty}", callback_data="noop"),
        InlineKeyboardButton("+", callback_data=f"qtyviewplus_{cat_id}|{idx}")
    ])
    kb.append([InlineKeyboardButton(f"Add to Cart - ${total:.2f}", callback_data=f"addcart_{cat_id}|{idx}")])
    kb.append([InlineKeyboardButton(f"Buy Now - ${total:.2f}", callback_data=f"buynow_{cat_id}|{idx}")])
    kb.append([InlineKeyboardButton(f"View Cart ({cart_count})", callback_data="viewcart"), InlineKeyboardButton("Back", callback_data=f"cat_{cat_id}")])
    try:
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except:
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    try:
        raw = update.message.text.split(" ", 1)[1] if " " in update.message.text else ""
        if "|" not in raw:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"Use pipes | \n/addproduct shop_low | Name | Price | Desc | [Options] | [Min:Max]")
            return
        parts = [x.strip() for x in raw.split("|")]
        cat_id = parts[0].lower()
        name = parts[1] if len(parts) > 1 else ""
        price = parts[2] if len(parts) > 2 else "0"
        desc = parts[3] if len(parts) > 3 else ""
        options_raw = ""
        minmax_raw = ""
        if len(parts) == 5:
            if is_minmax_string(parts[4]):
                minmax_raw = parts[4]
            else:
                options_raw = parts[4]
        elif len(parts) >= 6:
            options_raw = parts[4]
            minmax_raw = parts[5]
        options = parse_options_string(options_raw)
        min_q, max_q = parse_minmax_string(minmax_raw) if minmax_raw else (1, 999)
        cat = get_cat_by_id(cat_id)
        if not cat:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"Category {cat_id} not found")
            return
        prods = load_json(cat["file"], [])
        new_prod = {"name": name, "price": price.replace("$",""), "desc": desc, "min_qty": min_q, "max_qty": max_q}
        if options:
            new_prod["options"] = options
        prods.append(new_prod)
        save_json(cat["file"], prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Saved '{name}' to {cat['name']} ({cat['file']}) Min {min_q} Max {max_q} Total {len(prods)}")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def set_quantity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    try:
        raw = update.message.text.split(" ", 1)[1]
        cat_id, idx, minmax_raw = [x.strip() for x in raw.split("|", 2)]
        idx = int(idx)
        min_q, max_q = parse_minmax_string(minmax_raw)
        cat = get_cat_by_id(cat_id.lower())
        prods = load_json(cat["file"], [])
        prods[idx]["min_qty"] = min_q
        prods[idx]["max_qty"] = max_q
        save_json(cat["file"], prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Set qty for {prods[idx]['name']}: Min {min_q} Max {max_q}")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Use: /setquantity shop_low | 0 | 5:50 - {e}")

async def add_options_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    try:
        raw = update.message.text.split(" ", 1)[1]
        cat_id, idx, opts_raw = [x.strip() for x in raw.split("|", 2)]
        idx = int(idx)
        options = parse_options_string(opts_raw)
        cat = get_cat_by_id(cat_id.lower())
        prods = load_json(cat["file"], [])
        prods[idx]["options"] = options
        save_json(cat["file"], prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Added options to {prods[idx]['name']}: {options}")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        cat_id = parts[0].lower()
        idx = int(parts[1])
        name = parts[2]
        price = parts[3]
        desc = parts[4]
        options_raw = parts[5] if len(parts) > 5 else ""
        minmax_raw = parts[6] if len(parts) > 6 else ""
        cat = get_cat_by_id(cat_id)
        prods = load_json(cat["file"], [])
        old = prods[idx]
        new_data = {"name": name, "price": price.replace("$",""), "desc": desc, "min_qty": old.get("min_qty",1), "max_qty": old.get("max_qty",999)}
        if options_raw:
            if is_minmax_string(options_raw) and not minmax_raw:
                minmax_raw = options_raw
            else:
                new_data["options"] = parse_options_string(options_raw)
        else:
            if "options" in old:
                new_data["options"] = old["options"]
        if minmax_raw:
            min_q, max_q = parse_minmax_string(minmax_raw)
            new_data["min_qty"] = min_q
            new_data["max_qty"] = max_q
        prods[idx] = new_data
        save_json(cat["file"], prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Edited #{idx}")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    cat_id = update.message.text.split(" ", 1)[1].strip().lower() if len(update.message.text.split()) > 1 else "shop_low"
    cat = get_cat_by_id(cat_id)
    if not cat:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Category {cat_id} not found")
        return
    prods = load_json(cat["file"], [])
    txt = "\n".join([f"{i}: {p['name']} - ${p['price']} Min:{p.get('min_qty',1)} Max:{p.get('max_qty',999)}" for i, p in enumerate(prods)])
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"{cat['name']} ({cat['file']}) {len(prods)} items:\n{txt[:3500]}")

async def add_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    try:
        raw = update.message.text.split(" ", 1)[1]
        uid_str, amt = [x.strip() for x in raw.split("|")]
        new_bal = add_balance(int(uid_str) if uid_str.isdigit() else uid_str, float(amt))
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Added ${amt} to {uid_str} - New bal ${new_bal:.2f}")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def saveall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        await update.message.delete()
    except:
        pass
    cats = get_categories()
    files_to_save = [CATEGORIES_FILE, ORDERS_FILE, USERS_FILE, CARTS_FILE]
    for c in cats:
        files_to_save.append(c["file"])
    saved = []
    for f in set(files_to_save):
        if os.path.exists(f):
            try:
                with open(f, "r") as file:
                    data = json.load(file)
                save_json(f, data)
                saved.append(f)
            except:
                pass
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"Force saved {len(saved)} files: {', '.join(saved)}")

def run_bot():
    b = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    b.add_handler(CommandHandler("start", start))
    b.add_handler(CommandHandler("addproduct", add_product))
    b.add_handler(CommandHandler("addoptions", add_options_cmd))
    b.add_handler(CommandHandler("setquantity", set_quantity_cmd))
    b.add_handler(CommandHandler("editproduct", edit_product))
    b.add_handler(CommandHandler("listproducts", list_products))
    b.add_handler(CommandHandler("addbalance", add_balance_cmd))
    b.add_handler(CommandHandler("saveall", saveall_cmd))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: None))
    b.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=keep_alive_loop, daemon=True).start()
    run_bot()
