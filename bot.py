# -*- coding: utf-8 -*-
"""bot.py — Telegram bot."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

import config

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

SESSIONS = {}


def allowed(uid):
    return not config.ALLOWED_IDS or uid in config.ALLOWED_IDS


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not allowed(uid):
        await update.message.reply_text(
            f"⛔ Không có quyền.\nID: `{uid}`", parse_mode="Markdown")
        return
    await update.message.reply_text(
        f"🍪 *{config.TEN_BOT_TELEGRAM}*\n\n"
        f"• /{config.CMD_COOKIE} — Bắt đầu lấy cookie\n"
        f"• /{config.CMD_MYCOOKIES} — Cookie của bạn\n"
        f"• /{config.CMD_ID} — Telegram ID\n"
        f"• /{config.CMD_HELP} — Trợ giúp\n\n"
        f"⚠️ Chỉ dùng cho tài khoản CỦA CHÍNH BẠN.",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *HƯỚNG DẪN*\n\n"
        "1️⃣ /cookie → nhập API Key\n"
        "2️⃣ Chọn chế độ:\n"
        "   • AUTO — tự động chọn IP tốt nhất\n"
        "   • Agent Local — IP nhà, an toàn nhất\n"
        "   • Proxy — proxy dân cư của bạn\n"
        "   • Render — IP datacenter (nhanh, rủi ro)\n"
        "3️⃣ Điền form web (kèm selfie + SĐT)\n"
        "4️⃣ Nhận link tải ZIP qua Telegram\n"
        "5️⃣ Mật khẩu ZIP: `cheatgame`",
        parse_mode="Markdown"
    )


async def id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"🆔 `{uid}`", parse_mode="Markdown")


async def cookie_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not allowed(uid):
        await update.message.reply_text("⛔ Không có quyền.")
        return
    SESSIONS[uid] = {"step": "await_api_key"}
    await update.message.reply_text(
        "🔐 *Xác thực*\n\nNhập API Key:\n_(/cancel để hủy)_",
        parse_mode="Markdown"
    )


async def mycookies_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not allowed(uid):
        await update.message.reply_text("⛔ Không có quyền.")
        return
    url = f"{config.WEB_URL}/my-cookies?tg={uid}"
    await update.message.reply_text(
        f"📋 [Xem cookie của bạn]({url})\n\n"
        f"_(Chỉ hiện cookie do Telegram ID `{uid}` tạo)_",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def cancel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    SESSIONS.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ Đã hủy.")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sess = SESSIONS.get(uid)
    if not sess:
        return

    if sess["step"] == "await_api_key":
        if update.message.text.strip() != config.API_KEY:
            await update.message.reply_text("❌ API Key sai. Thử lại hoặc /cancel.")
            return
        SESSIONS[uid] = {"step": "authed"}
        url = f"{config.WEB_URL}/cookie?tg={uid}"
        kb = [[InlineKeyboardButton("🌐 Mở form lấy cookie", url=url)]]
        await update.message.reply_text(
            "✅ *Xác thực thành công!*\n\n"
            "Bấm nút để mở form:\n"
            "• Chọn chế độ IP (AUTO khuyến nghị)\n"
            "• Nền tảng + tài khoản + mật khẩu\n"
            "• SĐT + ảnh selfie xác minh\n\n"
            "🔑 ZIP pass: `cheatgame`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )


def main():
    if not config.TOKEN_TELEGRAM:
        raise SystemExit("❌ Thiếu TOKEN_TELEGRAM")
    app = Application.builder().token(config.TOKEN_TELEGRAM).build()

    app.add_handler(CommandHandler(config.CMD_START, start))
    app.add_handler(CommandHandler(config.CMD_HELP, help_cmd))
    app.add_handler(CommandHandler(config.CMD_ID, id_cmd))
    app.add_handler(CommandHandler(config.CMD_COOKIE, cookie_cmd))
    app.add_handler(CommandHandler(config.CMD_MYCOOKIES, mycookies_cmd))
    app.add_handler(CommandHandler(config.CMD_CANCEL, cancel_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    log.info("🤖 Bot chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
