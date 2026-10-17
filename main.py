{saintlocksupport}")],[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await q.edit_message_text("💬 SUPPORT", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "topup_choose":
        kb = [[InlineKeyboardButton("$10", callback_data="topup_amount_10"), InlineKeyboardButton("$20", callback_data="topup_amount_20")],[InlineKeyboardButton("$50", callback_data="topup_amount_50"), InlineKeyboardButton("$100", callback_data="topup_amount_100")],[InlineKeyboardButton("⬅️ Back", callback_data="balance")]]
        await q.edit_message_text("Choose amount:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_amount_"):
        context.user_data["topup_amount"] = d.replace("topup_amount_", "")
        kb = [[InlineKeyboardButton("₿ BTC", callback_data="topup_method_btc"), InlineKeyboardButton("💵 CashApp", callback_data="topup_method_cash")]]
        await q.edit_message_text(f"Top Up ${context.user_data['topup_amount']} - Choose method:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("topup_method_"):
        method = d.replace("topup_method_", ""); amount = context.user_data.get("topup_amount", "20"); order_id = gen_order_id()
        orders = load_json(ORDERS_FILE, []); orders.append({"order_id": order_id, "user_id": uid, "amount": float(amount), "method": method, "status": "pending", "username": q.from_user.username}); save_json(ORDERS_FILE, orders)
        if method == "btc":
            img = qrcode.make(BTC_WALLET); bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
            await q.message.reply_photo(photo=bio, caption=f"Order {order_id} - ${amount} BTC to:\n`{BTC_WALLET}`", parse_mode="Markdown")
        else:
            await q.message.reply_text(f"Order {order_id} - ${amount} CashApp: `{CASHAPP_TAG}` Note: {order_id}", parse_mode="Markdown")
        if uid != ADMIN_ID:
            admin_kb = [[InlineKeyboardButton(f"✅ Verify {order_id}", callback_data=f"admin_verify_{order_id}"), InlineKeyboardButton(f"❌ Decline", callback_data=f"admin_decline_{order_id}")]]
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 NEW TOP UP\nUser: @{q.from_user.username} ({uid})\nOrder: {order_id}\nAmount: ${amount}\nMethod: {method}", reply_markup=InlineKeyboardMarkup(admin_kb))
            except: pass
    elif d.startswith("admin_verify_"):
        if not is_admin(uid): return
        order_id = d.replace("admin_verify_", ""); orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["status"] == "pending":
                o["status"] = "verified"; add_balance(o["user_id"], o["amount"]); save_json(ORDERS_FILE, orders)
                await q.edit_message_text(f"✅ Verified {order_id}")
                try: await context.bot.send_message(chat_id=o["user_id"], text=f"✅ Verified {order_id} - ${o['amount']} added!")
                except: pass
    elif d.startswith("admin_decline_"):
        if not is_admin(uid): return
        order_id = d.replace("admin_decline_", ""); orders = load_json(ORDERS_FILE, [])
        for o in orders:
            if o["order_id"] == order_id and o["status"] == "pending":
                o["status"] = "declined"; save_json(ORDERS_FILE, orders); await q.edit_message_text(f"❌ Declined {order_id}")
    elif d.startswith("view_"):
        rest = d.replace("view_", "")
        if rest.startswith("shop_tees_"): cat_key="shop_tees"; idx=int(rest.replace("shop_tees_",""))
        elif rest.startswith("shop_accessories_"): cat_key="shop_accessories"; idx=int(rest.replace("shop_accessories_",""))
        else: cat_key="shop"; idx=int(rest.replace("shop_",""))
        p = load_json(FILES[cat_key], [])[idx]
        await q.message.reply_text(f"{p['name']} - ${p['price']}\n{p['desc']}")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        raw = update.message.text.split(" ", 1)[1]; parts = [x.strip() for x in raw.split("|")]
        cat_key, name, price, desc = (parts[0].lower(), parts[1], parts[2], parts[3]) if len(parts)==4 else ("shop", parts[0], parts[1], parts[2])
        if cat_key not in FILES: cat_key="shop"
        price = price.replace("$","").strip()
        prods = load_json(FILES[cat_key], []); prods.append({"name": name, "price": price, "desc": desc}); save_json(FILES[cat_key], prods)
        await update.message.reply_text(f"✅ Saved to GitHub: {name} - Check your GitHub repo, you should see {FILES[cat_key]} updated")
    except Exception as e:
        await update.message.reply_text(f"Use: /addproduct shop | Name | Price | Desc Error:{e}")

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addproduct", add_product))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
