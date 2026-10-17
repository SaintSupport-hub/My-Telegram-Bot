import os, json, threading, base64, requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Use split keys to avoid auto-tag breaking the code
TOKEN_KEY = "BOT_" + "TOKEN"
ADMIN_KEY = "ADMIN_" + "ID"
GH_TOK_KEY = "GITHUB_" + "TOKEN"
GH_REPO_KEY = "GITHUB_" + "REPO"
SUPP_KEY = "SUPPORT_" + "USERNAME"

BOT_TOKEN = os.getenv(TOKEN_KEY)
ADMIN_ID = int(os.getenv(ADMIN_KEY, "0") or "0")
SUPPORT_USERNAME = os.getenv(SUPP_KEY, "SaintSupport")
GH_TOKEN = os.getenv(GH_TOK_KEY)
GH_REPO = os.getenv(GH_REPO_KEY, "SaintSupport-hub/My-Telegram-Bot")

FILES = {"shop": "products.json","shop_tees": "products_tees.json","shop_accessories": "products_accessories.json"}

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
                print(f"Restored {path} from GH: {len(data)}")
                return data
        except Exception as e:
            print(f"GH load err: {e}")
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    if not GH_TOKEN:
        print("NO GH TOKEN - will be lost on redeploy")
        return False
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": f"Update {path}", "content": base64.b64encode(json.dumps(data, indent=2).encode()).decode()}
        if sha:
            payload["sha"] = sha
        resp = requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        print(f"GH save {path} -> {resp.status_code}")
        return resp.status_code in [200,201]
    except Exception as e:
        print(f"GH save failed: {e}")
        return False

app = Flask(__name__)
@app.route("/")
def home():
    return "LIVE"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def is_admin(uid): return uid == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
          [InlineKeyboardButton("🥊Shop Accounts", callback_data="shop_tees")],
          [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
          [InlineKeyboardButton("SUPPORT", callback_data="support")]]
    await update.message.reply_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d in FILES:
        products = load_json(FILES[d], [])
        if not products:
            await q.edit_message_text(f"{d} empty. /addproduct", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
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
        cat = "shop"
        if "shop_tees" in d: cat = "shop_tees"
        elif "shop_accessories" in d: cat = "shop_accessories"
        idx = int(d.split("_")[-1])
        p = load_json(FILES[cat], [])[idx]
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
        prods = load_json(FILES[cat_key], [])
        prods.append({"name": name, "price": price.replace("$",""), "desc": desc})
        ok = save_json(FILES[cat_key], prods)
        if ok:
            await update.message.reply_text(f"✅ Saved to GH: {name}")
        else:
            await update.message.reply_text(f"⚠️ Saved locally only - GH token missing or bad. Will delete on redeploy!")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc - {e}")

async def checkgh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(f"Token set: {bool(GH_TOKEN)}\nRepo: {GH_REPO}")

def run_bot():
    b = ApplicationBuilder().token(BOT_TOKEN).build()
    b.add_handler(CommandHandler("start", start))
    b.add_handler(CommandHandler("addproduct", add_product))
    b.add_handler(CommandHandler("checkgh", checkgh))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
