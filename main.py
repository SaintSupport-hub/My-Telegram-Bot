"tg://user?id={ADMIN_ID}")],[InlineKeyboardButton("Back", callback_data="back")]]
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
                await q.message.reply_photo(photo=bio, caption=f"TOP UP Order {order_id} - ${amount}\nBTC: {BTC_WALLET}\nCashApp: {CASHAPP_TAG}")
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
        msg = f"**{p['name']}**\nPrice: ${p['price']}\nDesc: {p['desc']}\n\n--- PAYMENT ---\nOrder ID: `{order_id}`\nAmount: ${p['price']}\n\nBTC: `{BTC_WALLET}`\nCashApp: `{CASHAPP_TAG}`"
        await q.message.reply_text(msg, parse_mode="Markdown")
        admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Approve {order_id}", callback_data=f"approve_{order_id}"), InlineKeyboardButton(f"Decline {order_id}", callback_data=f"decline_{order_id}")]])
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"NEW SALE\nUser: @{username} ({uid})\nOrder: {order_id}\nProduct: {p['name']}\nPrice: ${p['price']}", reply_markup=admin_kb)
        except:
            pass
    elif d.startswith("approve_"):
        if not is_admin(uid): return
        order_id = d.replace("approve_", "")
        orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id:
                o["status"] = "approved"
                save_json(ORDERS_FILE, orders)
                # if it's a top up, add balance
                if "TOPUP" in o.get("product",""):
                    add_balance(o["user_id"], float(o["price"]))
                await q.edit_message_text(f"Approved {order_id}")
                try:
                    await context.bot.send_message(chat_id=o["user_id"], text=f"✅ Order {order_id} APPROVED!")
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
                    await context.bot.send_message(chat_id=o["user_id"], text=f"❌ Order {order_id} DECLINED. Contact @{SUPPORT_USERNAME}")
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
        await update.message.reply_text(f"Saved {name} to {FILES[cat_key]}")
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
