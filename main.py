import os, json, threading, base64, requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "SaintSupport")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "SaintSupport-hub/My-Telegram-Bot")

FILES = {"shop": "products.json","shop_tees": "products_tees.json","shop_accessories": "products_accessories.json"}

def gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_json(path, default):
    # 1. local first (Render current run)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                print(f"Loaded local {path}: {len(data)} items")
                return data
        except:
            pass
    # 2. 【entity-GitHub API¦canonical_name=GitHub】
    if 【entity-GITHUB_TOKEN¦canonical_name=GitHub】:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
            r = requests.get(url, headers=gh_headers(), timeout=15)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode()
                data = json.loads(content)
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"Restored {path} from 【entity-GitHub API¦canonical_name=GitHub】: {len(data)} items")
                return data
            else:
                print(f"【entity-GitHub API¦canonical_name=GitHub】 {path} failed {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"【entity-GitHub¦canonical_name=GitHub】 load error: {e}")
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    if not 【entity-GITHUB_TOKEN¦canonical_name=GitHub】:
        print("CRITICAL: NO 【entity-GITHUB_TOKEN¦canonical_name=GitHub】 - will be LOST on redeploy!")
        return False
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        r = requests.get(url, headers=gh_headers())
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {
            "message": f"Update {path}",
            "content": base64.b64encode(json.dumps(data, indent=2).encode()).decode()
        }
        if sha:
            payload["sha"] = sha
        resp = requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        print(f"【entity-GitHub¦canonical_name=GitHub】 save {path} -> {resp.status_code} {resp.text[:300]}")
        return resp.status_code in [200,201]
    except Exception as e:
        print(f"GitHub save failed: {e}")
        return False

def get_user(uid):
    return {"balance": 0}

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
            await q.edit_message_text(f"{d} is empty. Use /addproduct", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))
            return
        kb = [[InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"view_{d}_{i}")] for i,p in enumerate(products)]
        kb.append([InlineKeyboardButton("Back", callback_data="back")])
        await q.edit_message_text(f"{d}:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "back":
        await start(q, context)
        # hack to edit instead of new message
        kb = [[InlineKeyboardButton("🛒Shop CC", callback_data="shop")],
              [InlineKeyboardButton("🥊Shop BINs", callback_data="shop_tees")],
              [InlineKeyboardButton("🥇Shop BINs", callback_data="shop_accessories")],
              [InlineKeyboardButton("SUPPORT", callback_data="support")]]
        try:
            await q.edit_message_text("Welcome to SAINTLOCK CC", reply_markup=InlineKeyboardMarkup(kb))
        except:
            pass
    elif d == "support":
        kb = [[InlineKeyboardButton("Message Support", url= https://t.me/Saintlocksupport,
              [InlineKeyboardButton("Back", callback_data="back")]]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("view_"):
        try:
            cat_key = "shop"
            if "shop_tees" in d: cat_key = "shop_tees"
            elif "shop_accessories" in d: cat_key = "shop_accessories"
            idx = int(d.split("_")[-1])
            p = load_json(FILES[cat_key], [])[idx]
            await q.message.reply_text(f"{p['name']} - ${p['price']}\n{p['desc']}")
        except Exception as e:
            await q.message.reply_text(f"Error: {e}")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        raw = update.message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        cat_key, name, price, desc = (parts[0].lower(), parts[1], parts[2], parts[3]) if len(parts)==4 else ("shop", parts[0], parts[1], parts[2])
        if cat_key not in FILES: cat_key = "shop"
        prods = load_json(FILES[cat_key], [])
        prods.append({"name": name, "price": price.replace("$",""), "desc": desc})
        ok = save_json(FILES[cat_key], prods)
        # This save_json already tries GitHub
        # Now test if GitHub actually saved
        if ok:
            await update.message.reply_text(f"✅ SAVED & pushed to GitHub: {name} ({len(prods)} total in {FILES[cat_key]})")
        else:
            await update.message.reply_text(f"⚠️ SAVED LOCALLY ONLY - GITHUB FAILED! Check GITHUB_TOKEN in Render. It will DELETE on next deploy. Error logged.")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc\nError: {e}")

async def check_github(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(f"GITHUB_TOKEN set: {bool(【entity-GITHUB_TOKEN¦canonical_name=GitHub】)}\nREPO: {GITHUB_REPO}\nTesting save...")
    test_ok = save_json(FILES["shop"], load_json(FILES["shop"], []))
    await update.message.reply_text(f"【entity-GitHub¦canonical_name=GitHub】 test result: {test_ok} - check Render logs for details")

def run_bot():
    b = ApplicationBuilder().token(BOT_TOKEN).build()
    b.add_handler(CommandHandler("start", start))
    b.add_handler(CommandHandler("addproduct", add_product))
    b.add_handler(CommandHandler("checkgithub", check_github))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
