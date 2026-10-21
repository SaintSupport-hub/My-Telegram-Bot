import os, json, threading, base64, requests, random, string, io, time, re
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
BTC_WALLET = os.getenv("BTC_WALLET", "bc1q...")
CASHAPP_TAG = os.getenv("CASHAPP_TAG", "$Saintlockecon")
GH_TOKEN = os.getenv("GITHUB_"+"TOKEN")
GH_REPO = os.getenv("GITHUB_"+"REPO", "SaintSupport-hub/My-Telegram-Bot")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
SUPPORT_HANDLE = "@saintlocksupport"

CATEGORIES_FILE = "categories.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"
CARTS_FILE = "carts.json"

DEFAULT_CATEGORIES = [
    {"id": "shop", "name": "🛒Shop CC", "file": "products.json"},
    {"id": "shop_low", "name": "⬇️SHOP LOW % SNIFF [Med-Low Bal]", "file": "products_low.json"},
    {"id": "shop_high", "name": "⬆️SHOP HIGH % SNIFF [High Bal]", "file": "products_high.json"},
    {"id": "shop_tees", "name": "🥊Shop Accounts", "file": "products_tees.json"},
    {"id": "shop_food", "name": "🥙Shop Food", "file": "products_food.json"},
    {"id": "shop_accessories", "name": "🥇Shop BINs", "file": "products_accessories.json"}
]
MAIN_MENU_ORDER = ["shop", "shop_tees", "shop_food", "shop_accessories"]

def safe_float(v, default=0.0):
    try:
        s=str(v).replace("$","").strip()
        m=re.search(r"[\d\.]+", s)
        if m: return float(m.group())
        return float(s)
    except: return default

def gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.【entity-github¦canonical_name=GitHub】.v3+json"}

def load_json(path, default):
    gh=None
    if GH_TOKEN:
        try:
            url=f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
            r=requests.get(url, headers=gh_headers(), timeout=15)
            if r.status_code==200:
                gh=json.loads(base64.b64decode(r.json()["content"]).decode())
                with open(path,"w") as f: json.dump(gh,f,indent=2)
                return gh
        except Exception as e:
            print(f"GH load fail {path} {e}")
    if os.path.exists(path):
        try:
            with open(path,"r") as f: return json.load(f)
        except: pass
    return default

def save_json(path,data):
    if isinstance(data, list) and len(data)==0:
        if GH_TOKEN:
            try:
                url=f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
                r=requests.get(url, headers=gh_headers(), timeout=15)
                if r.status_code==200:
                    gh=json.loads(base64.b64decode(r.json()["content"]).decode())
                    if isinstance(gh, list) and len(gh)>0:
                        print(f"BLOCKED overwrite of {path} - GH has {len(gh)} items")
                        with open(path,"w") as f: json.dump(gh,f,indent=2)
                        return False
            except: pass
    with open(path,"w") as f: json.dump(data,f,indent=2)
    if not GH_TOKEN: return True
    try:
        url=f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
        r=requests.get(url, headers=gh_headers())
        sha=r.json().get("sha") if r.status_code==200 else None
        payload={"message":f"Update {path}","content":base64.b64encode(json.dumps(data,indent=2).encode()).decode()}
        if sha: payload["sha"]=sha
        resp=requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        return resp.status_code in [200,201]
    except: return False

def get_categories():
    cats=load_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)
    ids=[c["id"] for c in cats]
    if "shop_high" not in ids:
        cats.append({"id": "shop_high", "name": "SHOP HIGH % SNIFF [High Bal]", "file": "products_high.json"})
        save_json(CATEGORIES_FILE,cats)
    return cats

def get_cat_by_id(cat_id):
    if cat_id=="shop_high": return {"id": "shop_high", "name": "SHOP HIGH % SNIFF [High Bal]", "file": "products_high.json"}
    if cat_id=="shop_low": return {"id": "shop_low", "name": "SHOP LOW % SNIFF [Med-Low Bal]", "file": "products_low.json"}
    for c in get_categories():
        if c["id"]==cat_id: return c
    return None

def get_loyalty_title(pct):
    if pct >= 100: return "SAINTLOCK ELITE"
    if pct >= 75: return "SAINT"
    if pct >= 50: return "GOLD"
    if pct >= 25: return "LOYAL"
    return "CUSTOMER"

def get_user(uid):
    users=load_json(USERS_FILE,{})
    s=str(uid)
    if s not in users:
        users[s]={"balance":0.0,"loyalty":0,"total_spent":0.0}
        save_json(USERS_FILE,users)
    if "loyalty" not in users[s]: users[s]["loyalty"]=0
    if "total_spent" not in users[s]: users[s]["total_spent"]=0
    return users[s]

def add_loyalty(uid, amount_spent):
    try: amount_spent = float(amount_spent)
    except: return 0
    if amount_spent <= 0: return 0
    inc = int(amount_spent * 0.3)
    if inc < 1 and amount_spent >= 1: inc = 1
    if inc <= 0: return 0
    users=load_json(USERS_FILE,{})
    s=str(uid)
    if s not in users: users[s]={"balance":0.0,"loyalty":0,"total_spent":0.0}
    if "loyalty" not in users[s]: users[s]["loyalty"]=0
    if "total_spent" not in users[s]: users[s]["total_spent"]=0
    users[s]["loyalty"] = min(100, int(users[s].get("loyalty",0) + inc))
    users[s]["total_spent"] = float(users[s].get("total_spent",0)) + float(amount_spent)
    save_json(USERS_FILE,users)
    return inc

def add_balance(uid,amt):
    users=load_json(USERS_FILE,{})
    s=str(uid)
    if s not in users: users[s]={"balance":0.0,"loyalty":0,"total_spent":0.0}
    users[s]["balance"]=float(users[s].get("balance",0))+float(amt)
    save_json(USERS_FILE,users)
    if float(amt) >= 1: add_loyalty(uid, float(amt))
    return users[s]["balance"]

def deduct_balance(uid,amt):
    users=load_json(USERS_FILE,{})
    s=str(uid)
    if float(users[s].get("balance",0))<float(amt): return None
    users[s]["balance"]=float(users[s].get("balance",0))-float(amt)
    save_json(USERS_FILE,users)
    if float(amt) >= 1: add_loyalty(uid, float(amt))
    return users[s]["balance"]

def gen_id(): return "ORD-"+ "".join(random.choices(string.ascii_uppercase+string.digits,k=6))

def keep_alive_loop():
    while True:
        time.sleep(600)
        try:
            if RENDER_URL: requests.get(RENDER_URL,timeout=10)
            requests.get("http://localhost:10000/",timeout=5)
        except: pass

def get_cart(uid): return load_json(CARTS_FILE,{}).get(str(uid),[])
def get_cart_total(uid):
    cart=get_cart(uid); total=sum(safe_float(it.get("total",0)) for it in cart); return total,len(cart)
def add_to_cart(uid,item):
    carts=load_json(CARTS_FILE,{}); s=str(uid)
    if s not in carts: carts[s]=[]
    carts[s].append(item); save_json(CARTS_FILE,carts); return len(carts[s])
def clear_cart(uid):
    carts=load_json(CARTS_FILE,{}); carts[str(uid)]=[]; save_json(CARTS_FILE,carts)

def parse_options_string(opts_raw):
    if not opts_raw: return []
    result=[]
    parts=[p.strip() for p in opts_raw.split(",") if p.strip()]
    for part in parts:
        segs=[x.strip() for x in part.split(":")]
        if len(segs)==1:
            result.append({"name":segs[0],"price":None,"min_qty":None,"max_qty":None,"stock":None})
            continue
        name=segs[0]
        try: price=float(segs[1].replace("$","")) if segs[1] else None
        except: price=None
        try: min_q=int(float(segs[2])) if len(segs)>2 and segs[2] else None
        except: min_q=None
        try: max_q=int(float(segs[3])) if len(segs)>3 and segs[3] else None
        except: max_q=None
        try: stock=int(float(segs[4])) if len(segs)>4 and segs[4] else None
        except: stock=None
        result.append({"name":name,"price":price,"min_qty":min_q,"max_qty":max_q,"stock":stock})
    return result

def parse_minmax_string(s):
    s=s.strip().replace(" ","")
    if not s: return 1,999
    if ":" in s:
        a,b=s.split(":",1)
        try: return int(float(a)),int(float(b))
        except: return 1,999
    if "-" in s:
        a,b=s.split("-",1)
        try: return int(float(a)),int(float(b))
        except: return 1,999
    try: return int(float(s)),999
    except: return 1,999

def is_minmax_string(s):
    s=s.strip()
    if re.match(r"^\d+$",s): return True
    if re.match(r"^\d+\s*[:\-]\s*\d+$",s): return True
    return False

def is_url(s): return s.startswith("http://") or s.startswith("https://")

app=Flask(__name__)
@app.route("/")
def home(): return "LIVE - PUSHALL FIX"
def run_web(): app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
def is_admin(uid): return uid==ADMIN_ID
async def post_init(app): await app.bot.set_my_commands([BotCommand("start","Open Shop Menu")])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats=get_categories()
    total,count=get_cart_total(update.effective_user.id)
    u=get_user(update.effective_user.id)
    bal=u.get("balance",0)
    loyalty=u.get("loyalty",0)
    title=get_loyalty_title(loyalty)
    uname = f"@{update.effective_user.username}" if update.effective_user.username else f"ID:{update.effective_user.id}"
    caption = f"🔴⚫ *Welcome to SAINTLOCK* ⚫🔴\n{uname} | Loyalty: *{loyalty}%* [{title}]\n━━━━━━━━━━━━━━━━━━━━\n💰 `${bal:.2f}` | 🛒 `{count}` items\n━━━━━━━━━━━━━━━━━━━━\n"
    kb=[]
    cat_map={c["id"]:c for c in cats}
    for cid in MAIN_MENU_ORDER:
        if cid in cat_map:
            c=cat_map[cid]
            kb.append([InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")])
    kb.append([InlineKeyboardButton(f"🛒 {count}", callback_data="viewcart"), InlineKeyboardButton(f"💰", callback_data="balance"), InlineKeyboardButton(f"📞", callback_data="support")])
    await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def show_balance(q,uid):
    try:
        u=get_user(uid); bal=u.get("balance",0); loy=u.get("loyalty",0); title=get_loyalty_title(loy)
        txt=f"💰 Balance: ${bal:.2f}\n⭐ Loyalty: {loy}% [{title}]\nSpent: ${u.get('total_spent',0):.2f}\n\nNext title at {((loy//25)+1)*25}%"
        kb=[[InlineKeyboardButton("Top Up",callback_data="topup_choose")],[InlineKeyboardButton("Back",callback_data="back")]]
        if q.message.photo:
            await q.message.delete()
            await q.message.chat.send_message(txt, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    except: pass

async def show_category(q,cat_id,is_admin_view=False):
    try:
        cat=get_cat_by_id(cat_id)
        if not cat:
            text=f"❌ Category {cat_id} not found."
            kb=[[InlineKeyboardButton("Back",callback_data="back")]]
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message(text, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
            return
        products=load_json(cat["file"],[])
        if not products:
            text=f"🔴 {cat['name']} is empty"
            kb=[[InlineKeyboardButton("Back",callback_data="back")]]
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message(text, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
            return
        kb=[]
        for i,p in enumerate(products):
            fp=safe_float(p.get("price",0))
            for o in p.get("options",[]):
                if o.get("price") is not None:
                    fv=safe_float(o.get("price"), fp)
                    if fv < fp or fp==0: fp=fv
            kb.append([InlineKeyboardButton(f"{p['name']} - From ${fp:.2f}",callback_data=f"view_{cat_id}_{i}")])
        kb.append([InlineKeyboardButton("Back",callback_data="back")])
        text=f"⚫ *{cat['name']}* - {len(products)} items"
        if q.message.photo:
            await q.message.delete()
            await q.message.chat.send_message(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        try:
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message(f"Error in {cat_id}: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="back")]]))
            else:
                await q.edit_message_text(f"Error in {cat_id}: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="back")]]))
        except: pass

async def show_cart(q,uid):
    try:
        cart=get_cart(uid)
        if not cart:
            txt="🛒 Cart is empty."
            kb=[[InlineKeyboardButton("Back",callback_data="back")]]
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message(txt, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
            return
        total=sum(safe_float(it.get("total",0)) for it in cart)
        lines=[f"{idx+1}. {it['name']} {it.get('option','')} x{it['qty']} = ${safe_float(it['total']):.2f}" for idx,it in enumerate(cart)]
        txt="🛒 *Your Cart*\n\n"+"\n".join(lines)+f"\n\n*Total: ${total:.2f}*"
        kb=[[InlineKeyboardButton(f"❌ {idx+1}",callback_data=f"cartdel_{idx}") ] for idx in range(len(cart))]
        kb.append([InlineKeyboardButton("Clear",callback_data="cartclear")])
        kb.append([InlineKeyboardButton(f"${total:.2f} Pay",callback_data="cartpay_bal")])
        kb.append([InlineKeyboardButton(f"BTC",callback_data="cartpay_btc"), InlineKeyboardButton(f"Cash",callback_data="cartpay_cash")])
        kb.append([InlineKeyboardButton("Back",callback_data="back")])
        if q.message.photo:
            await q.message.delete()
            await q.message.chat.send_message(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except: pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    try: await q.answer()
    except: pass
    d=q.data; uid=q.from_user.id; username=q.from_user.username or "no_username"
    if d=="cat_shop_low":
        await show_category(q,"shop_low", is_admin_view=is_admin(uid)); return
    if d=="cat_shop_high":
        await show_category(q,"shop_high", is_admin_view=is_admin(uid)); return
    if d=="cat_shop":
        kb=[[InlineKeyboardButton("SHOP LOW %",callback_data="cat_shop_low")],[InlineKeyboardButton("SHOP HIGH %",callback_data="cat_shop_high")],[InlineKeyboardButton("Back",callback_data="back")]]
        try:
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message("💳 Shop CC - Choose Type:", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text("💳 Shop CC - Choose Type:", reply_markup=InlineKeyboardMarkup(kb))
        except: pass
        return
    if d.startswith("cat_"):
        await show_category(q,d.replace("cat_",""), is_admin_view=is_admin(uid)); return
    if d=="back":
        cats=get_categories(); total,count=get_cart_total(uid)
        u=get_user(uid); loy=u.get("loyalty",0); title=get_loyalty_title(loy)
        uname = f"@{q.from_user.username}" if q.from_user.username else ""
        header=f"🔴⚫ *Welcome to SAINTLOCK* ⚫🔴\n{uname} | Loyalty: {loy}% [{title}]\n"
        kb=[]
        cat_map={c["id"]:c for c in cats}
        for cid in MAIN_MENU_ORDER:
            if cid in cat_map:
                c=cat_map[cid]
                kb.append([InlineKeyboardButton(c["name"], callback_data=f"cat_{c['id']}")])
        kb.append([InlineKeyboardButton(f"🛒 {count}",callback_data="viewcart"), InlineKeyboardButton(f"💰",callback_data="balance"), InlineKeyboardButton(f"📞",callback_data="support")])
        try:
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message(header, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text(header, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        except: pass
        return
    if d=="balance": await show_balance(q,uid); return
    if d=="viewcart": await show_cart(q,uid); return
    if d=="support":
        kb=[[InlineKeyboardButton("Message Support",url=f"tg://user?id={ADMIN_ID}")],[InlineKeyboardButton("Back",callback_data="back")]]
        try:
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
        except: pass
        return
    if d=="topup_choose":
        kb=[[InlineKeyboardButton("$10",callback_data="topup_amount_10"),InlineKeyboardButton("$20",callback_data="topup_amount_20")],[InlineKeyboardButton("$50",callback_data="topup_amount_50"),InlineKeyboardButton("$100",callback_data="topup_amount_100")],[InlineKeyboardButton("Back",callback_data="balance")]]
        try:
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message("Choose Top Up amount:", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text("Choose Top Up amount:", reply_markup=InlineKeyboardMarkup(kb))
        except: pass
        return
    if d.startswith("topup_amount_"):
        context.user_data["topup_amount"]=d.replace("topup_amount_","")
        kb=[[InlineKeyboardButton("BTC",callback_data="topup_method_btc"),InlineKeyboardButton("CashApp",callback_data="topup_method_cash")]]
        try:
            if q.message.photo:
                await q.message.delete()
                await q.message.chat.send_message(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
        except: pass
        return
    if d.startswith("topup_method_"):
        method=d.replace("topup_method_",""); amount=context.user_data.get("topup_amount","20"); order_id=gen_id()
        orders=load_json(ORDERS_FILE,[]); orders.append({"order_id":order_id,"user_id":uid,"username":username,"product":f"TOPUP ${amount}","price":amount,"method":method,"status":"pending"}); save_json(ORDERS_FILE,orders)
        if method=="btc": await q.message.chat.send_message(f"Order {order_id} - ${amount} BTC: {BTC_WALLET}\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
        else: await q.message.chat.send_message(f"Order {order_id} - ${amount} CashApp: {CASHAPP_TAG} Note: {order_id}\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
        return
    if d.startswith("cartdel_"):
        idx=int(d.replace("cartdel_","")); carts=load_json(CARTS_FILE,{}); s=str(uid)
        if s in carts and 0<=idx<len(carts[s]): carts[s].pop(idx); save_json(CARTS_FILE,carts)
        await show_cart(q,uid); return
    if d=="cartclear": clear_cart(uid); await show_cart(q,uid); return
    if d.startswith("cartpay_"):
        method=d.replace("cartpay_",""); cart=get_cart(uid)
        if not cart:
            try:
                if q.message.photo: await q.message.delete()
                await q.message.chat.send_message("Cart empty")
            except: pass
            return
        total=sum(safe_float(it.get("total",0)) for it in cart); order_id=gen_id()
        orders=load_json(ORDERS_FILE,[]); item_list="\n".join([f"- {it['name']} {it.get('option','')} x{it['qty']} = ${safe_float(it['total']):.2f}" for it in cart])
        orders.append({"order_id":order_id,"user_id":uid,"username":username,"product":f"CART {len(cart)} items","price":total,"method":method,"status":"pending","items":cart,"total":total}); save_json(ORDERS_FILE,orders)
        if method=="bal":
            if get_user(uid).get("balance",0)<total:
                await q.message.chat.send_message(f"❌ You need ${total:.2f} but you have ${get_user(uid).get('balance',0):.2f}"); return
            new_bal=deduct_balance(uid,total); clear_cart(uid)
            u=get_user(uid)
            await q.message.chat.send_message(f"✅ CART PAID ${total:.2f} Order {order_id}\n{item_list}\nNew Bal ${new_bal:.2f}\nLoyalty: {u.get('loyalty',0)}% [{get_loyalty_title(u.get('loyalty',0))}]\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
        elif method=="btc":
            clear_cart(uid); await q.message.chat.send_message(f"Order {order_id} ${total:.2f} BTC: {BTC_WALLET}\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
        else:
            clear_cart(uid); await q.message.chat.send_message(f"Order {order_id} ${total:.2f} CashApp: {CASHAPP_TAG}\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
        return

    if d.startswith("view_"):
        parts=d.replace("view_","").rsplit("_",1); cat_id=parts[0]; idx=int(parts[1])
        cat=get_cat_by_id(cat_id); p=load_json(cat["file"],[])[idx]
        if p.get("options"):
            first = p["options"][0]
            context.user_data[f"opt_{cat_id}_{idx}"]=first["name"]
            if first.get("price") is not None:
                context.user_data[f"optprice_{cat_id}_{idx}"]=safe_float(first.get("price"), safe_float(p.get("price",0)))
            else:
                context.user_data[f"optprice_{cat_id}_{idx}"]=safe_float(p.get("price",0))
            context.user_data[f"qty_{cat_id}_{idx}"]=int(first.get("min_qty") if first.get("min_qty") is not None else p.get("min_qty",1))
            context.user_data[f"optmin_{cat_id}_{idx}"]=first.get("min_qty")
            context.user_data[f"optmax_{cat_id}_{idx}"]=first.get("max_qty")
            context.user_data[f"optstock_{cat_id}_{idx}"]=first.get("stock")
        else:
            context.user_data[f"qty_{cat_id}_{idx}"]=int(p.get("min_qty",1))
            context.user_data[f"opt_{cat_id}_{idx}"]=""
            context.user_data[f"optprice_{cat_id}_{idx}"]=safe_float(p.get("price",0))
            context.user_data[f"optmin_{cat_id}_{idx}"]=p.get("min_qty")
            context.user_data[f"optmax_{cat_id}_{idx}"]=p.get("max_qty")
        await send_product_view(q,cat_id,idx,context,uid); return

    if d.startswith("seloptview_"):
        rest=d.replace("seloptview_",""); cat_part,idx_part,opt_name=rest.split("|",2); cat_id=cat_part; idx=int(idx_part)
        cat=get_cat_by_id(cat_id); prod=load_json(cat["file"],[])[idx]
        opt_obj=None
        for o in prod.get("options",[]):
            if o["name"]==opt_name: opt_obj=o; break
        price=safe_float(prod.get("price",0)) if not opt_obj or opt_obj.get("price") is None else safe_float(opt_obj.get("price",0))
        min_q = opt_obj.get("min_qty") if opt_obj and opt_obj.get("min_qty") is not None else int(prod.get("min_qty",1))
        context.user_data[f"opt_{cat_id}_{idx}"]=opt_name
        context.user_data[f"optprice_{cat_id}_{idx}"]=price
        context.user_data[f"qty_{cat_id}_{idx}"]=min_q
        context.user_data[f"optmin_{cat_id}_{idx}"]=opt_obj.get("min_qty")
        context.user_data[f"optmax_{cat_id}_{idx}"]=opt_obj.get("max_qty")
        context.user_data[f"optstock_{cat_id}_{idx}"]=opt_obj.get("stock")
        await send_product_view(q,cat_id,idx,context,uid); return

    if d.startswith("qtyviewminus_") or d.startswith("qtyviewplus_"):
        is_plus=d.startswith("qtyviewplus_"); rest=d.replace("qtyviewminus_","").replace("qtyviewplus_","")
        cat_id,idx_str=rest.rsplit("|",1); idx=int(idx_str)
        cat=get_cat_by_id(cat_id); prod=load_json(cat["file"],[])[idx]
        opt_min = context.user_data.get(f"optmin_{cat_id}_{idx}")
        opt_max = context.user_data.get(f"optmax_{cat_id}_{idx}")
        opt_stock = context.user_data.get(f"optstock_{cat_id}_{idx}")
        min_q = int(opt_min) if opt_min is not None else int(prod.get("min_qty",1))
        max_q = int(opt_max) if opt_max is not None else int(prod.get("max_qty",999))
        if opt_stock is not None: max_q = min(max_q, int(opt_stock))
        key=f"qty_{cat_id}_{idx}"; qty=int(context.user_data.get(key,min_q))
        if is_plus:
            if qty<max_q: qty+=1
            else: await q.answer(f"Max is {max_q}", show_alert=True); return
        else:
            if qty>min_q: qty-=1
            else: await q.answer(f"Min is {min_q}", show_alert=True); return
        context.user_data[key]=qty; await send_product_view(q,cat_id,idx,context,uid); return

    if d.startswith("addcart_"):
        rest=d.replace("addcart_",""); cat_id,idx_str=rest.rsplit("|",1); idx=int(idx_str)
        cat=get_cat_by_id(cat_id); prod=load_json(cat["file"],[])[idx]
        qty=int(context.user_data.get(f"qty_{cat_id}_{idx}", int(prod.get("min_qty",1))))
        opt=context.user_data.get(f"opt_{cat_id}_{idx}",""); unit=safe_float(context.user_data.get(f"optprice_{cat_id}_{idx}", safe_float(prod.get("price",0)))); total=unit*qty
        item={"name":prod["name"],"category":cat_id,"product_idx":idx,"option":opt,"unit_price":unit,"qty":qty,"total":total}
        count=add_to_cart(uid,item); await q.answer(f"Added! 🛒 {count}"); await send_product_view(q,cat_id,idx,context,uid,added=True); return

    if d.startswith("buynow_"):
        try:
            rest=d.replace("buynow_",""); cat_id,idx_str=rest.rsplit("|",1); idx=int(idx_str)
            cat=get_cat_by_id(cat_id); prod=load_json(cat["file"],[])[idx]
            qty=int(context.user_data.get(f"qty_{cat_id}_{idx}", int(prod.get("min_qty",1))))
            opt=context.user_data.get(f"opt_{cat_id}_{idx}",""); unit=safe_float(context.user_data.get(f"optprice_{cat_id}_{idx}", safe_float(prod.get("price",0)))); total=unit*qty; order_id=gen_id()
            orders=load_json(ORDERS_FILE,[]); orders.append({"order_id":order_id,"user_id":uid,"username":username,"product":prod["name"],"price":unit,"quantity":qty,"total":total,"selected_option":opt,"selected_price":unit,"category":cat_id,"product_idx":idx,"method":"buynow","status":"pending"}); save_json(ORDERS_FILE,orders)
            txt=f"*{prod['name']}* {opt} x{qty} = *${total:.2f}* Order `{order_id}`\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order"
            kb=[[InlineKeyboardButton(f"${total:.2f} Pay with Balance",callback_data=f"paybalnow_{order_id}")],[InlineKeyboardButton(f"BTC",callback_data=f"paybtcnow_{order_id}"),InlineKeyboardButton(f"Cash",callback_data=f"paycashnow_{order_id}")],[InlineKeyboardButton("Back",callback_data=f"cat_{cat_id}")]]
            await q.message.chat.send_message(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            await q.message.chat.send_message(f"Buy Now error: {e}")
        return

    if d.startswith("paybalnow_"):
        order_id=d[len("paybalnow_"):]; method="bal"
    elif d.startswith("paybtcnow_"):
        order_id=d[len("paybtcnow_"):]; method="btc"
    elif d.startswith("paycashnow_"):
        order_id=d[len("paycashnow_"):]; method="cash"
    else:
        order_id=None
    if order_id:
        orders=load_json(ORDERS_FILE,[])
        for o in orders:
            if o["order_id"]==order_id:
                total=safe_float(o.get("total",0))
                if method=="bal":
                    if get_user(uid).get("balance",0)<total:
                        await q.message.chat.send_message(f"❌ You need ${total:.2f} but have ${get_user(uid).get('balance',0):.2f}"); return
                    new_bal=deduct_balance(uid,total); o["status"]="approved"; save_json(ORDERS_FILE,orders)
                    u=get_user(uid)
                    await q.message.chat.send_message(f"✅ SUCCESS {order_id} ${total:.2f} New Bal ${new_bal:.2f}\n⭐ Loyalty: {u.get('loyalty',0)}% [{get_loyalty_title(u.get('loyalty',0))}]\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
                elif method=="btc":
                    await q.message.chat.send_message(f"Order {order_id} ${total:.2f} BTC: {BTC_WALLET}\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
                else:
                    await q.message.chat.send_message(f"Order {order_id} ${total:.2f} CashApp: {CASHAPP_TAG}\n\nPlease send your order # and a ss of this order to support {SUPPORT_HANDLE} to complete this order")
                break
        return

async def send_product_view(q,cat_id,idx,context,uid,added=False):
    cat=get_cat_by_id(cat_id); prod=load_json(cat["file"],[])[idx]
    if prod.get("options") and not context.user_data.get(f"opt_{cat_id}_{idx}"):
        first = prod["options"][0]
        context.user_data[f"opt_{cat_id}_{idx}"]=first["name"]
        context.user_data[f"optprice_{cat_id}_{idx}"]=safe_float(first.get("price"), safe_float(prod.get("price",0))) if first.get("price") is not None else safe_float(prod.get("price",0))
        context.user_data[f"qty_{cat_id}_{idx}"]=int(first.get("min_qty") if first.get("min_qty") is not None else prod.get("min_qty",1))
        context.user_data[f"optmin_{cat_id}_{idx}"]=first.get("min_qty")
        context.user_data[f"optmax_{cat_id}_{idx}"]=first.get("max_qty")
        context.user_data[f"optstock_{cat_id}_{idx}"]=first.get("stock")
    min_q=int(prod.get("min_qty",1)); max_q=int(prod.get("max_qty",999))
    qty=int(context.user_data.get(f"qty_{cat_id}_{idx}",min_q))
    opt=context.user_data.get(f"opt_{cat_id}_{idx}","")
    unit=safe_float(context.user_data.get(f"optprice_{cat_id}_{idx}", safe_float(prod.get("price",0))))
    opt_min=context.user_data.get(f"optmin_{cat_id}_{idx}")
    opt_max=context.user_data.get(f"optmax_{cat_id}_{idx}")
    opt_stock=context.user_data.get(f"optstock_{cat_id}_{idx}")
    cur_min = int(opt_min) if opt_min is not None else min_q
    cur_max = int(opt_max) if opt_max is not None else max_q
    if opt_stock is not None: cur_max = min(cur_max, int(opt_stock))
    if qty < cur_min:
        qty = cur_min
        context.user_data[f"qty_{cat_id}_{idx}"]=qty
    all_prices=[safe_float(prod.get("price",0))]
    for o in prod.get("options",[]):
        if o.get("price") is not None: all_prices.append(safe_float(o.get("price"),0))
    from_price=min([p for p in all_prices if p>0] or [0])
    total=unit*qty
    options=prod.get("options",[])
    if options and not opt:
        price_line = f"From ${from_price:.2f}"
        qty_line = f"Min: {cur_min}"
    else:
        price_line = f"${unit:.2f} each"
        qty_line = f"Min {cur_min} | Qty: {qty} = ${total:.2f}"
    sel_text=f"\n🔴 Selected: {opt} - ${unit:.2f}" if opt else f"\n🔴 {price_line}"
    added_text="\n\n✅ Added to 🛒!" if added else ""
    text=f"⚫ *{prod['name']}*{sel_text}\n\n📝 {prod['desc']}\n\n{qty_line}\nTotal: *${total:.2f}*{added_text}"
    kb=[]
    if options:
        for o in options:
            price_show=f" ${safe_float(o.get('price',0)):.2f}" if o.get("price") is not None else ""
            min_show=f" Min:{o.get('min_qty')}" if o.get('min_qty') is not None else ""
            kb.append([InlineKeyboardButton(f"{o['name']}{price_show}{min_show}", callback_data=f"seloptview_{cat_id}|{idx}|{o['name']}")])
    kb.append([InlineKeyboardButton("➖",callback_data=f"qtyviewminus_{cat_id}|{idx}"), InlineKeyboardButton(f"{qty}",callback_data="noop"), InlineKeyboardButton("➕",callback_data=f"qtyviewplus_{cat_id}|{idx}")])
    kb.append([InlineKeyboardButton(f"🛒 Add {qty} = ${total:.2f}",callback_data=f"addcart_{cat_id}|{idx}")])
    kb.append([InlineKeyboardButton(f"⚡ Buy {qty} = ${total:.2f}",callback_data=f"buynow_{cat_id}|{idx}")])
    kb.append([InlineKeyboardButton(f"🛒 {get_cart_total(uid)[1]}",callback_data="viewcart"), InlineKeyboardButton("Back",callback_data=f"cat_{cat_id}")])
    img_url = prod.get("image") or prod.get("image_url")
    if img_url and is_url(img_url):
        try:
            try: await q.message.delete()
            except: pass
            await q.message.chat.send_photo(photo=img_url, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            return
        except:
            try:
                await q.message.chat.send_message(f"{text}\n\n🖼️ [Image]({img_url})", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                return
            except: pass
    try:
        if q.message.photo:
            await q.message.delete()
            await q.message.chat.send_message(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except:
        await q.message.chat.send_message(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1] if " " in update.message.text else ""
        if "|" not in raw: await context.bot.send_message(chat_id=ADMIN_ID, text="Use /addproduct cat | Name | Price | Desc | Options | Min:Max | ImageURL"); return
        parts=[x.strip() for x in raw.split("|")]
        cat_id=parts[0].lower(); name=parts[1] if len(parts)>1 else ""; price=parts[2] if len(parts)>2 else "0"; desc=parts[3] if len(parts)>3 else ""
        options_raw=""; minmax_raw=""; image_url=""
        if len(parts)==5:
            if is_url(parts[4]): image_url=parts[4]
            elif is_minmax_string(parts[4]): minmax_raw=parts[4]
            else: options_raw=parts[4]
        elif len(parts)==6:
            if is_url(parts[5]):
                if is_minmax_string(parts[4]): minmax_raw=parts[4]; image_url=parts[5]
                else: options_raw=parts[4]; image_url=parts[5]
            else:
                options_raw=parts[4]; minmax_raw=parts[5]
        elif len(parts)>=7:
            options_raw=parts[4]; minmax_raw=parts[5]; image_url=parts[6]
        options=parse_options_string(options_raw)
        min_q,max_q=parse_minmax_string(minmax_raw) if minmax_raw else (1,999)
        cat=get_cat_by_id(cat_id); prods=load_json(cat["file"],[])
        new_prod={"name":name,"price":price.replace("$",""),"desc":desc,"min_qty":min_q,"max_qty":max_q}
        if options: new_prod["options"]=options
        if image_url and is_url(image_url): new_prod["image"]=image_url
        prods.append(new_prod); save_json(cat["file"],prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Saved '{name}' From ${price} Min {min_q} Image: {'Yes' if image_url else 'No'} - File now has {len(prods)} items")
    except Exception as e: await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def del_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]
        cat_id, idx_str = [x.strip() for x in raw.split("|")]
        idx=int(idx_str)
        cat=get_cat_by_id(cat_id.lower())
        if not cat:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Category {cat_id} not found")
            return
        prods=load_json(cat["file"],[])
        if not prods:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ {cat['name']} is empty. File {cat['file']} has 0 products.")
            return
        if idx < 0 or idx >= len(prods):
            listing = "\n".join([f"{i}: {p['name']}" for i,p in enumerate(prods)])[:3000]
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Index {idx} out of range. It has {len(prods)} products (0-{len(prods)-1}):\n{listing}")
            return
        removed=prods.pop(idx)
        save_json(cat["file"],prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🗑️ Deleted #{idx}: {removed['name']} from {cat['name']}. Remaining: {len(prods)}")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}\nUse like /delproduct shop_food | 0")

async def add_image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]
        parts=[x.strip() for x in raw.split("|")]
        cat_id=parts[0].lower(); idx=int(parts[1]); url=parts[2]
        cat=get_cat_by_id(cat_id); prods=load_json(cat["file"],[])
        prods[idx]["image"]=url; save_json(cat["file"],prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Added image to {prods[idx]['name']}")
    except Exception as e: await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def set_quantity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]; cat_id,idx,minmax_raw=[x.strip() for x in raw.split("|",2)]; idx=int(idx)
        min_q,max_q=parse_minmax_string(minmax_raw); cat=get_cat_by_id(cat_id.lower()); prods=load_json(cat["file"],[]); prods[idx]["min_qty"]=min_q; prods[idx]["max_qty"]=max_q; save_json(cat["file"],prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Set qty {prods[idx]['name']}: Min {min_q} Max {max_q}")
    except Exception as e: await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def add_options_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]; cat_id,idx,opts_raw=[x.strip() for x in raw.split("|",2)]; idx=int(idx)
        options=parse_options_string(opts_raw); cat=get_cat_by_id(cat_id.lower()); prods=load_json(cat["file"],[]); prods[idx]["options"]=options; save_json(cat["file"],prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Added options")
    except Exception as e: await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]; parts=[x.strip() for x in raw.split("|")]
        cat_id=parts[0].lower(); idx=int(parts[1]); name=parts[2]; price=parts[3]; desc=parts[4]
        options_raw=parts[5] if len(parts)>5 else ""; minmax_raw=parts[6] if len(parts)>6 else ""; image_url=parts[7] if len(parts)>7 else ""
        cat=get_cat_by_id(cat_id); prods=load_json(cat["file"],[]); old=prods[idx]
        new_data={"name":name,"price":price.replace("$",""),"desc":desc,"min_qty":old.get("min_qty",1),"max_qty":old.get("max_qty",999)}
        if options_raw: new_data["options"]=parse_options_string(options_raw)
        else:
            if "options" in old: new_data["options"]=old["options"]
        if minmax_raw: min_q,max_q=parse_minmax_string(minmax_raw); new_data["min_qty"]=min_q; new_data["max_qty"]=max_q
        if image_url and is_url(image_url): new_data["image"]=image_url
        elif "image" in old: new_data["image"]=old["image"]
        prods[idx]=new_data; save_json(cat["file"],prods)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Edited #{idx}")
    except Exception as e: await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    cat_id=update.message.text.split(" ",1)[1].strip().lower() if len(update.message.text.split())>1 else "shop_low"
    cat=get_cat_by_id(cat_id)
    if not cat:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Category {cat_id} not found")
        return
    prods=load_json(cat["file"],[])
    txt="\n".join([f"{i}: {p['name']} - ${safe_float(p.get('price',0)):.2f} {'[IMG]' if p.get('image') else '[NO IMG]'}" for i,p in enumerate(prods)])
    if not txt: txt="Empty"
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"CAT: {cat['id']} -> FILE: {cat['file']}\nName: {cat['name']} {len(prods)}:\n{txt[:3500]}")

async def fixcats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    cats = [
        {"id": "shop", "name": "Shop CC", "file": "products.json"},
        {"id": "shop_low", "name": "SHOP LOW % SNIFF [Med-Low Bal]", "file": "products_low.json"},
        {"id": "shop_high", "name": "SHOP HIGH % SNIFF [High Bal]", "file": "products_high.json"},
        {"id": "shop_tees", "name": "Shop Accounts", "file": "products_tees.json"},
        {"id": "shop_food", "name": "Shop Food", "file": "products_food.json"},
        {"id": "shop_accessories", "name": "Shop Accessories", "file": "products_accessories.json"}
    ]
    save_json(CATEGORIES_FILE, cats)
    await context.bot.send_message(chat_id=ADMIN_ID, text="✅ FIXED CATEGORIES\nshop_tees (Shop Accounts) -> products_tees.json\nshop_accessories -> products_accessories.json")

async def pushall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    cats=get_categories()
    files=[CATEGORIES_FILE,ORDERS_FILE,USERS_FILE,CARTS_FILE]+[c["file"] for c in cats]
    out=[]
    for f in set(files):
        if os.path.exists(f):
            try:
                with open(f,"r") as file: data=json.load(file)
                with open(f,"w") as wf: json.dump(data,wf,indent=2)
                if GH_TOKEN:
                    url=f"https://api.github.com/repos/{GH_REPO}/contents/{f}"
                    r=requests.get(url, headers=gh_headers())
                    sha=r.json().get("sha") if r.status_code==200 else None
                    payload={"message":f"FORCE PUSH {f}","content":base64.b64encode(json.dumps(data,indent=2).encode()).decode()}
                    if sha: payload["sha"]=sha
                    resp=requests.put(url, headers=gh_headers(), json=payload, timeout=15)
                    cnt=len(data) if isinstance(data,list) else len(data)
                    out.append(f"{f}: {cnt} -> GH {resp.status_code}")
                else:
                    out.append(f"{f}: local only")
            except Exception as e:
                out.append(f"{f}: ERR {e}")
    await context.bot.send_message(chat_id=ADMIN_ID, text="PUSHED LOCAL -> GITHUB:\n"+"\n".join(out)+"\n\nNow do /start again - you should see 8")

async def add_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]; uid_str,amt=[x.strip() for x in raw.split("|")]; new_bal=add_balance(int(uid_str) if uid_str.isdigit() else uid_str,float(amt))
        u=get_user(int(uid_str) if uid_str.isdigit() else uid_str)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Added ${amt} to {uid_str} - ${new_bal:.2f} | Loyalty now {u.get('loyalty',0)}%")
    except Exception as e: await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")

async def add_loyalty_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    try:
        raw=update.message.text.split(" ",1)[1]
        uid_str, amt = [x.strip() for x in raw.split("|")]
        uid = int(uid_str) if uid_str.isdigit() else uid_str
        inc = add_loyalty(uid, float(amt))
        u=get_user(uid)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Added {inc}% loyalty for ${amt} to {uid_str} -> Now {u.get('loyalty',0)}% [{get_loyalty_title(u.get('loyalty',0))}]")
    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}\nUse /addloyalty 123456789 | 8.37")

async def saveall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try: await update.message.delete()
    except: pass
    cats=get_categories(); files=[CATEGORIES_FILE,ORDERS_FILE,USERS_FILE,CARTS_FILE]+[c["file"] for c in cats]
    out=[]
    for f in set(files):
        data=load_json(f, [])
        if isinstance(data, list):
            out.append(f"{f}: {len(data)} items - SAFE")
        else:
            out.append(f"{f}: {len(data)} keys - SAFE")
    await context.bot.send_message(chat_id=ADMIN_ID, text="SAFE SAVE - Nothing deleted:\n"+"\n".join(out))

def run_bot():
    b=ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    b.add_handler(CommandHandler("start",start))
    b.add_handler(CommandHandler("addproduct",add_product))
    b.add_handler(CommandHandler("delproduct",del_product))
    b.add_handler(CommandHandler("addimage",add_image_cmd))
    b.add_handler(CommandHandler("addoptions",add_options_cmd))
    b.add_handler(CommandHandler("setquantity",set_quantity_cmd))
    b.add_handler(CommandHandler("editproduct",edit_product))
    b.add_handler(CommandHandler("listproducts",list_products))
    b.add_handler(CommandHandler("addbalance",add_balance_cmd))
    b.add_handler(CommandHandler("addloyalty",add_loyalty_cmd))
    b.add_handler(CommandHandler("saveall",saveall_cmd))
    b.add_handler(CommandHandler("fixcats",fixcats_cmd))
    b.add_handler(CommandHandler("pushall",pushall_cmd))
    b.add_handler(CallbackQueryHandler(button_handler))
    b.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: None))
    b.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    threading.Thread(target=run_web,daemon=True).start()
    threading.Thread(target=keep_alive_loop,daemon=True).start()
    run_bot()
