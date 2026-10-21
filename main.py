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
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
def load_json(path, default):
    local=None
    if os.path.exists(path):
        try:
            with open(path,"r") as f: local=json.load(f)
        except: pass
    gh=None
    if GH_TOKEN:
        try:
            url=f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
            r=requests.get(url, headers=gh_headers(), timeout=15)
            if r.status_code==200: gh=json.loads(base64.b64decode(r.json()["content"]).decode())
        except: pass
    if local is not None: return local
    if gh is not None:
        with open(path,"w") as f: json.dump(gh,f,indent=2)
        return gh
    return default
def save_json(path,data):
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
    for needed in DEFAULT_CATEGORIES:
        if needed["id"] not in ids:
            cats.append(needed)
    save_json(CATEGORIES_FILE,cats)
    return cats
def get_cat_by_id(cat_id):
    if cat_id=="shop_high":
        return {"id": "shop_high", "name": "SHOP HIGH % SNIFF [High Bal]", "file": "products_high.json"}
    if cat_id=="shop_low":
        return {"id": "shop_low", "name": "SHOP LOW % SNIFF [Med-Low Bal]", "file": "products_low.json"}
    if cat_id=="shop_tees":
        return {"id": "shop_tees", "name": "Shop Tees", "file": "products_tees.json"}
    if cat_id=="shop_food":
        return {"id": "shop_food", "name": "Shop Food", "file": "products_food.json"}
    if cat_id=="shop_accessories":
        return {"id": "shop_accessories", "name": "Shop Accessories", "file": "products_accessories.json"}
    if cat_id=="shop":
        return {"id": "shop", "name": "Shop CC", "file": "products.json"}
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
    if amount_spent < 10: return 0
    inc = int(amount_spent // 10) * 3
    users=load_json(USERS_FILE,{})
    s=str(uid)
    if s not in users: users[s]={"balance":0.0,"loyalty":0,"total_spent":0.0}
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
    if float(amt) >= 10: add_loyalty(uid, float(amt))
    return users[s]["balance"]
def deduct_balance(uid,amt):
    users=load_json(USERS_FILE,{})
    s=str(uid)
    if float(users[s].get("balance",0))<float(amt): return None
    users[s]["balance"]=float(users[s].get("balance",0))-float(amt)
    save_json(USERS_FILE,users)
    if float(amt) >= 10: add_loyalty(uid, float(amt))
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
def is_url(s):
    return s.startswith("http://") or s.startswith("https://")

app=Flask(__name__)
@app.route("/")
def home(): return "LIVE - TEES FIXED WITH BUTTONS"
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
    u=get_user(uid); bal=u.get("balance",0); loy=u.get("loyalty",0); title=get_loyalty_title(loy)
    txt=f"💰 Balance: ${bal:.2f}\n⭐ Loyalty: {loy}% [{title}]\nSpent: ${u.get('total_spent',0):.2f}\n\nNext title at {((loy//25)+1)*25}%"
    kb=[[InlineKeyboardButton("Top Up",callback_data="topup_choose")],[InlineKeyboardButton("Back",callback_data="back")]]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def show_category(q,cat_id,is_admin_view=False):
    try:
        cat=get_cat_by_id(cat_id)
        if not cat:
            await q.edit_message_text(f"❌ Category {cat_id} not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="back")]]))
            return
        products=load_json(cat["file"],[])
        if not products:
            await q.edit_message_text(f"🔴 {cat['name']} is empty\n/addproduct {cat_id} | Name | Price | Desc", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="back")]]))
            return
        kb=[]
        for i,p in enumerate(products):
            fp=safe_float(p.get("price",0))
            for o in p.get("options",[]):
                if o.get("price") is not None:
                    try:
                        fv=safe_float(o.get("price"), fp)
                        if fv < fp or fp==0: fp=fv
                    except: pass
            # FIXED: every category including shop_tees gets clickable buttons
            kb.append([InlineKeyboardButton(f"{p['name']} - ${fp:.2f}",callback_data=f"view_{cat_id}_{i}")])
        kb.append([InlineKeyboardButton("Back",callback_data="back")])
        await q.edit_message_text(f"⚫ *{cat['name']}* - {len(products)} items\nTap a product to buy:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        await q.edit_message_text(f"Error in {cat_id}: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="back")]]))

async def show_cart(q,uid):
    cart=get_cart(uid)
    if not cart:
        await q.edit_message_text("🛒 Cart is empty.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back",callback_data="back")]]))
        return
    total=sum(safe_float(it.get("total",0)) for it in cart)
    lines=[f"{idx+1}. {it['name']} {it.get('option','')} x{it['qty']} = ${safe_float(it['total']):.2f}" for idx,it in enumerate(cart)]
    txt="🛒 *Your Cart*\n\n"+"\n".join(lines)+f"\n\n*Total: ${total:.2f}*"
    kb=[[InlineKeyboardButton(f"❌ {idx+1}",callback_data=f"cartdel_{idx}") ] for idx in range(len(cart))]
    kb.append([InlineKeyboardButton("Clear",callback_data="cartclear")])
    kb.append([InlineKeyboardButton(f"${total:.2f} Pay",callback_data="cartpay_bal")])
    kb.append([InlineKeyboardButton(f"BTC",callback_data="cartpay_btc"), InlineKeyboardButton(f"Cash",callback_data="cartpay_cash")])
    kb.append([InlineKeyboardButton("Back",callback_data="back")])
    await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    try: await q.answer()
    except: pass
    d=q.data; uid=q.from_user.id; username=q.from_user.username or "no_username"
    # EXPLICIT FIX FOR ALL MAIN BUTTONS
    if d=="cat_shop_low":
        await show_category(q,"shop_low", is_admin_view=is_admin(uid)); return
    if d=="cat_shop_high":
        await show_category(q,"shop_high", is_admin_view=is_admin(uid)); return
    if d=="cat_shop_tees":
        await show_category(q,"shop_tees", is_admin_view=is_admin(uid)); return
    if d=="cat_shop_food":
        await show_category(q,"shop_food", is_admin_view=is_admin(uid)); return
    if d=="cat_shop_accessories":
        await show_category(q,"shop_accessories", is_admin_view=is_admin(uid)); return
    if d=="cat_shop":
        kb=[[InlineKeyboardButton("SHOP LOW %",callback_data="cat_shop_low")],[InlineKeyboardButton("SHOP HIGH %",callback_data="cat_shop_high")],[InlineKeyboardButton("Back",callback_data="back")]]
        try: await q.edit_message_text("💳 Shop CC - Choose Type:", reply_markup=InlineKeyboardMarkup(kb))
        except: await q.message.reply_text("💳 Shop CC - Choose Type:", reply_markup=InlineKeyboardMarkup(kb))
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
        await q.edit_message_text(header, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)); return
    if d=="balance": await show_balance(q,uid); return
    if d=="viewcart": await show_cart(q,uid); return
    if d=="support":
        kb=[[InlineKeyboardButton("Message Support",url=f"tg://user?id={ADMIN_ID}")],[InlineKeyboardButton("Back",callback_data="back")]]
        await q.edit_message_text("SUPPORT", reply_markup=InlineKeyboardMarkup(kb)); return
    if d=="topup_choose":
        kb=[[InlineKeyboardButton("$10",callback_data="topup_amount_10"),InlineKeyboardButton("$20",callback_data="topup_amount_20")],[InlineKeyboardButton("$50",callback_data="topup_amount_50"),InlineKeyboardButton("$100",callback_data="topup_amount_100")],[InlineKeyboardButton("Back",callback_data="balance")]]
        await q.edit_message_text("Choose Top Up amount:", reply_markup=InlineKeyboardMarkup(kb)); return
    if d.startswith("topup_amount_"):
        context.user_data["topup_amount"]=d.replace("topup_amount_","")
        kb=[[InlineKeyboardButton("BTC",callback_data="topup_method_btc"),InlineKeyboardButton("CashApp",callback_data="topup_method_cash")]]
        await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb)); return
    if d.startswith("topup_method_"):
        method=d.replace("topup_method_",""); amount=context.user_data.get("topup_amount","20"); order_id=gen_id()
        orders=load_json(ORDERS_FILE,[]); orders.append({"order_id":order_id,"user_id":uid,"username":username,"product":f"TOPUP ${amount}","price":amount,"method":method,"status":"pending"}); save_json(ORDERS_FILE,orders)
        if method=="btc": await q.message.reply_text(f"Order {order_id} - ${amount} BTC: {BTC_WALLET}")
        else: await q.message.reply_text(f"Order {order_id} - ${amount} CashApp: {CASHAPP_TAG} Note: {order_id}")
        return
    if d.startswith("cartdel_"):
        idx=int(d.replace("cartdel_","")); carts=load_json(CARTS_FILE,{}); s=str(uid)
        if s in carts and 0<=idx<len(carts[s]): carts[s].pop(idx); save_json(CARTS_FILE,carts)
        await show_cart(q,uid); return
    if d=="cartclear": clear_cart(uid); await show_cart(q,uid); return
    if d.startswith("cartpay_"):
        method=d.replace("cartpay_",""); cart=get_cart(uid)
        if not cart: await q.edit_message_text("Cart empty"); return
        total=sum(safe_float(it.get("total",0)) for it in cart); order_id=gen_id()
        orders=load_json(ORDERS_FILE,[]); item_list="\n".join([f"- {it['name']} {it.get('option','')} x{it['qty']} = ${safe_float(it['total']):.2f}" for it in cart])
        orders.append({"order_id":order_id,"user_id":uid,"username":username,"product":f"CART {len(cart)} items","price":total,"method":method,"status":"pending","items":cart,"total":total}); save_json(ORDERS_FILE,orders)
        if method=="bal":
            if get_user(uid).get("balance",0)<total: await q.message.reply_text(f"Need ${total:.2f}"); return
            new_bal=deduct_balance(uid,total); clear_cart(uid)
            u=get_user(uid); inc_text=f" +{int(total//10*3)}% loyalty!" if total>=10 else ""
            await q.message.reply_text(f"✅ CART PAID ${total:.2f} Order {order_id}{inc_text}\n{item_list}\nNew Bal ${new_bal:.2f}\nLoyalty: {u.get('loyalty',0)}% [{get_loyalty_title(u.get('loyalty',0))}]")
        elif method=="btc":
            clear_cart(uid); await q.message.reply_text(f"Order {order_id} ${total:.2f} BTC: {BTC_WALLET}")
        else:
            clear_cart(uid); await q.message.reply_text(f"Order {order_id} ${total:.2f} CashApp: {CASHAPP_TAG}")
        return
    if d.startswith("view_"):
        parts=d.replace("view_","").rsplit("_",1); cat_id=parts[0]; idx=int(parts[1])
        cat=get_cat_by_id(cat_id); p=load_json(cat["file"],[])[idx]
        context.user_data[f"qty_{cat_id}_{idx}"]=int(p.get("min_qty",1))
        context.user_data[f"opt_{cat_id}_{idx}"]=""; context.user_data[f"optprice_{cat_id}_{idx}"]=safe_float(p.get("price",0))
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
        context.user_data[f"
