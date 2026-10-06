# -*- coding: utf-8 -*-
"""web.py — Flask + Supabase + AUTO IP."""

import asyncio
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, request, render_template_string, jsonify,
    session, redirect, url_for, abort, Response
)

import config
from extractor import (
    login_and_get_cookies, export_cookies_zip_bytes,
    SITES, decide_mode, get_render_ip_info, mask_proxy
)
from supabase_client import (
    upsert_user, create_verification, complete_verification,
    fail_verification, upload_selfie, upload_cookie_zip,
    create_signed_url, get_verification_by_token,
    get_verification_by_id, audit, list_user_cookies,
    count_today, get_client, mask_account
)

config.validate()
print(config.summary())

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

RENDER_INFO = get_render_ip_info()
print(f"🌐 Render IP: {RENDER_INFO['ip']} ({RENDER_INFO.get('isp')}) "
      f"DC={RENDER_INFO.get('is_datacenter')}")


def get_client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")


def require_api_key(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("authed"):
            return redirect(url_for("index"))
        return f(*a, **k)
    return w


def require_telegram(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("tg_id"):
            return render_template_string(
                RESULT_HTML, success=False,
                message="⛔ Vui lòng mở form từ bot Telegram (/cookie).",
                download_url=""
            ), 403
        return f(*a, **k)
    return w


BASE_CSS = """
body{background:#0d1117;color:#c9d1d9;font-family:system-ui;padding:40px;margin:0}
.box{max-width:640px;margin:auto;background:#161b22;padding:40px;
border-radius:12px;border:1px solid #30363d;box-shadow:0 8px 32px rgba(0,0,0,.6)}
h1{color:#58a6ff;font-size:24px;margin:0 0 8px}
p{color:#8b949e;font-size:13px;margin:0 0 20px}
label{display:block;font-size:13px;color:#8b949e;margin:14px 0 6px}
input,select{width:100%;padding:12px;background:#0d1117;border:1px solid #30363d;
border-radius:6px;color:#c9d1d9;box-sizing:border-box}
button{width:100%;padding:12px;background:#238636;color:#fff;border:0;
border-radius:6px;cursor:pointer;font-weight:600;font-size:15px;margin-top:20px}
button:hover{background:#2ea043}
.note{background:#1f2937;border-left:3px solid #f59e0b;padding:12px;
font-size:12px;color:#fbbf24;border-radius:4px;margin-bottom:16px}
.warn{background:#2d1618;border-left:3px solid #f85149;padding:12px;
font-size:12px;color:#f85149;border-radius:4px;margin-bottom:16px}
.ok{background:#0f2a1a;border-left:3px solid #3fb950;padding:12px;
font-size:12px;color:#3fb950;border-radius:4px;margin-bottom:16px}
.ip{background:#0d1117;padding:12px;border-radius:6px;font-family:monospace;
font-size:12px;margin-bottom:16px;border:1px solid #30363d;line-height:1.7}
.err{color:#f85149;font-size:13px;margin-bottom:12px}
.radio{display:flex;gap:10px;align-items:flex-start;padding:12px;
background:#0d1117;border:1px solid #30363d;border-radius:8px;margin-bottom:8px;cursor:pointer}
.radio input{width:auto;margin:3px 0 0}
.radio b{color:#c9d1d9}
.radio small{color:#8b949e;font-size:11px;display:block;margin-top:3px}
code{background:#21262d;padding:2px 6px;border-radius:4px;font-family:monospace;
font-size:12px;color:#f59e0b}
.btn{display:inline-block;padding:12px 24px;background:#238636;color:#fff;
text-decoration:none;border-radius:6px;font-weight:600;margin-top:16px}
"""

LOGIN_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>{{ bot_name }} - Xác thực</title><style>""" + BASE_CSS + """
.box{width:400px}</style></head><body><div class="box">
<h1>🔐 {{ bot_name }}</h1><p>Nhập API Key để tiếp tục</p>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
<form method="POST">
<input type="password" name="api_key" placeholder="API Key" required autofocus>
<button type="submit">Xác nhận</button></form>
</div></body></html>"""

FORM_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Lấy Cookie</title><style>""" + BASE_CSS + """</style></head><body>
<div class="box">
<h1>🍪 Lấy Cookie Tài Khoản</h1>
<p>Chỉ dùng cho tài khoản CỦA CHÍNH BẠN</p>

<div class="ip">
🌐 <b>IP Render hiện tại:</b> {{ render_ip }}<br>
🏢 ISP: {{ render_isp }}<br>
📍 {{ render_city }}, {{ render_country }}<br>
⚠️ Datacenter: {{ 'CÓ (dễ checkpoint)' if render_dc else 'Không' }}
</div>

<div class="{{ 'warn' if render_dc else 'ok' }}">
{{ '⚠️ Render đang dùng IP datacenter. Facebook/TikTok dễ checkpoint. Khuyến nghị chọn Agent Local hoặc nhập Proxy.'
   if render_dc else '✅ IP Render là dân cư — an toàn để login.' }}
</div>

{% if error %}<div class="err">{{ error }}</div>{% endif %}

<form method="POST" enctype="multipart/form-data">

<label>🔧 Chế độ lấy cookie</label>

<label class="radio"><input type="radio" name="mode" value="auto" checked>
<div><b>AUTO (khuyến nghị)</b>
<small>Tự động chọn IP tốt nhất: proxy env → user proxy → Render</small></div></label>

<label class="radio"><input type="radio" name="mode" value="agent">
<div><b>Agent Local</b>
<small>Chạy trên máy bạn — IP nhà, KHÔNG checkpoint</small></div></label>

<label class="radio"><input type="radio" name="mode" value="proxy">
<div><b>Proxy dân cư</b>
<small>Bạn có proxy riêng — nhập bên dưới</small></div></label>

<label class="radio"><input type="radio" name="mode" value="render">
<div><b>IP Render</b>
<small>Nhanh, không cần cài gì — tỷ lệ thấp</small></div></label>

<label>Nền tảng</label>
<select name="site" required>
<option value="facebook">Facebook</option>
<option value="tiktok">TikTok</option>
<option value="instagram">Instagram</option>
</select>

<label>Tài khoản (email / SĐT / username)</label>
<input type="text" name="username" required>

<label>Mật khẩu</label>
<input type="password" name="password" required>

<label>Số điện thoại liên hệ</label>
<input type="tel" name="phone" required pattern="[0-9+\\s-]{9,15}">

<label>Proxy (nếu có — để trống nếu không dùng)</label>
<input type="text" name="proxy" placeholder="http://user:pass@host:port">

<label>Ảnh selfie xác minh</label>
<input type="file" name="selfie" accept="image/*" required capture="user">

<button type="submit">🚀 Bắt đầu</button>
</form></div></body></html>"""

RESULT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Kết quả</title><style>""" + BASE_CSS + """
h1.ok-h{color:#3fb950}
.info{background:#0d1117;padding:16px;border-radius:6px;margin:16px 0;
font-size:13px;line-height:1.8;white-space:pre-wrap;font-family:monospace}
.pw{color:#f59e0b;font-weight:700}
</style></head><body><div class="box">
<h1 style="color:{{ '#3fb950' if success else '#f85149' }}">
{{ '✅ Thành công!' if success else '❌ Thất bại' }}</h1>
<div class="info">{{ message }}</div>
{% if success %}
<p>🔑 Mật khẩu ZIP: <span class="pw">cheatgame</span></p>
<p>⏱️ Link có hiệu lực <b>5 phút</b>, chỉ mở 1 lần.</p>
<a class="btn" href="{{ download_url }}">⬇️ Tải cookie ZIP</a>
{% endif %}
</div></body></html>"""

AGENT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Tải Agent Local</title><style>""" + BASE_CSS + """</style></head><body>
<div class="box">
<h1 style="color:#3fb950">✅ Tải Agent Local</h1>
<div class="ok">🏠 Agent chạy trên MÁY BẠN — dùng IP nhà — KHÔNG checkpoint.</div>

<div class="ip"><b>Bước 1:</b> Tải agent.py<br>
<a class="btn" href="{{ download_url }}">⬇️ Tải agent.py</a></div>

<div class="ip"><b>Bước 2:</b> Cài đặt<br>
<code>pip install playwright requests pyzipper</code><br>
<code>playwright install chromium</code></div>

<div class="ip"><b>Bước 3:</b> Chạy<br>
<code>python agent.py</code></div>

<div class="ip"><b>Thông tin đã điền sẵn:</b><br>
🌐 Site: <b>{{ site }}</b><br>
👤 Tài khoản: <b>{{ username }}</b><br>
📞 SĐT: <b>{{ phone }}</b><br>
🆔 Verif ID: <code>{{ verif_id }}</code></div>

<p style="color:#8b949e;font-size:12px">
🔒 Agent chạy 100% local. Không gửi mật khẩu đi đâu.
</p>
</div></body></html>"""


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if request.form.get("api_key") == config.API_KEY:
            session["authed"] = True
            tg = request.args.get("tg")
            if tg and tg.isdigit():
                session["tg_id"] = int(tg)
            return redirect(url_for("cookie_form"))
        return render_template_string(LOGIN_HTML, error="API Key sai!",
                                      bot_name=config.TEN_BOT_TELEGRAM)

    if session.get("authed"):
        return redirect(url_for("cookie_form"))

    tg = request.args.get("tg")
    if tg and tg.isdigit():
        session["tg_id"] = int(tg)
    return render_template_string(LOGIN_HTML, error=None,
                                  bot_name=config.TEN_BOT_TELEGRAM)


def _form_error(msg, tg_id):
    return render_template_string(
        FORM_HTML, error=msg, tg_id=tg_id,
        render_ip=RENDER_INFO["ip"],
        render_isp=RENDER_INFO.get("isp", "N/A"),
        render_city=RENDER_INFO.get("city", "N/A"),
        render_country=RENDER_INFO.get("country", "N/A"),
        render_dc=RENDER_INFO.get("is_datacenter", True),
    )


@app.route("/cookie", methods=["GET", "POST"])
@require_api_key
@require_telegram
def cookie_form():
    tg_id = session["tg_id"]

    if request.method == "GET":
        return render_template_string(
            FORM_HTML, error=None, tg_id=tg_id,
            render_ip=RENDER_INFO["ip"],
            render_isp=RENDER_INFO.get("isp", "N/A"),
            render_city=RENDER_INFO.get("city", "N/A"),
            render_country=RENDER_INFO.get("country", "N/A"),
            render_dc=RENDER_INFO.get("is_datacenter", True),
        )

    user_mode = request.form.get("mode", "auto").strip()
    site = request.form.get("site", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    phone = request.form.get("phone", "").strip()
    user_proxy = request.form.get("proxy", "").strip()
    selfie = request.files.get("selfie")

    if site not in SITES or not config.SITES_ENABLED.get(site):
        return _form_error("Nền tảng không hợp lệ hoặc bị tắt.", tg_id)
    if not username or not password or not phone:
        return _form_error("Thiếu thông tin.", tg_id)
    if not selfie or not selfie.filename:
        return _form_error("Thiếu ảnh selfie.", tg_id)

    if count_today(tg_id) >= config.RATE_LIMIT_PER_DAY:
        return render_template_string(
            RESULT_HTML, success=False,
            message=f"⛔ Đã dùng {config.RATE_LIMIT_PER_DAY} lần hôm nay.",
            download_url=""
        )

    decision = decide_mode(user_mode, user_proxy)
    if decision["mode"] == "error":
        return _form_error(decision["reason"], tg_id)

    actual_mode = decision["mode"]
    proxy_to_use = decision["proxy"]

    user = upsert_user(tg_id, phone=phone)
    selfie_bytes = selfie.read()
    selfie_path, selfie_hash = upload_selfie(tg_id, selfie_bytes, selfie.filename)

    verif = create_verification(
        telegram_id=tg_id, user_id=user["id"], site=site,
        account=username, phone=phone,
        selfie_path=selfie_path, selfie_hash=selfie_hash,
        ip=get_client_ip(),
        ua=request.headers.get("User-Agent", ""),
        user_ip=get_client_ip() if actual_mode == "render" else "(agent/proxy)",
        proxy_used=mask_proxy(proxy_to_use) if proxy_to_use else None,
        mode=actual_mode,
    )

    audit(tg_id, "cookie_request", {
        "verif_id": verif["id"], "site": site,
        "mode": actual_mode, "reason": decision["reason"],
    }, ip=get_client_ip())

    if actual_mode == "agent":
        return render_template_string(
            AGENT_HTML,
            site=site, username=username, phone=phone,
            verif_id=verif["id"],
            download_url=f"{config.WEB_URL}/download-agent?verif={verif['id']}"
        )

    try:
        result = asyncio.run(login_and_get_cookies(
            site, username, password,
            proxy_str=proxy_to_use,
            headless=config.PLAYWRIGHT_HEADLESS
        ))
    except Exception as e:
        fail_verification(verif["id"], f"Playwright: {e}")
        return render_template_string(
            RESULT_HTML, success=False,
            message=f"Lỗi hệ thống: {e}", download_url=""
        )

    if not result["success"]:
        fail_verification(verif["id"], result["error"])
        exit_info = result.get("exit_info", {})
        tip = ""
        if exit_info.get("is_datacenter"):
            tip = ("\n💡 IP Render là datacenter → Facebook dễ checkpoint.\n"
                   "Thử chế độ Agent Local hoặc nhập Proxy dân cư.")
        return render_template_string(
            RESULT_HTML, success=False,
            message=(
                f"Lý do: {result['error']}\n"
                f"IP thoát: {exit_info.get('ip', '?')}\n"
                f"ISP: {exit_info.get('isp', '?')}\n"
                f"{tip}"
            ),
            download_url=""
        )

    zip_bytes, zip_fname = export_cookies_zip_bytes(
        result["cookies"], site, username
    )
    cookie_path = upload_cookie_zip(tg_id, zip_bytes, zip_fname)

    token, expires = complete_verification(
        verif["id"], cookie_path, len(result["cookies"]),
        exit_info=result.get("exit_info")
    )

    audit(tg_id, "cookie_success", {
        "verif_id": verif["id"], "site": site,
        "mode": actual_mode,
        "exit_ip": result["exit_info"].get("ip"),
        "count": len(result["cookies"]),
    })

    download_url = url_for("download_by_token", token=token, _external=True)

    try:
        send_telegram_link(
            tg_id, download_url, site, len(result["cookies"]),
            expires, actual_mode, result["exit_info"]
        )
    except Exception:
        pass

    return render_template_string(
        RESULT_HTML, success=True,
        message=(
            f"Nền tảng:     {site}\n"
            f"Tài khoản:    {mask_account(username)}\n"
            f"Chế độ:       {actual_mode} ({decision['reason']})\n"
            f"IP thoát:     {result['exit_info'].get('ip')}\n"
            f"ISP:          {result['exit_info'].get('isp')}\n"
            f"Datacenter:   {result['exit_info'].get('is_datacenter')}\n"
            f"Số cookie:    {len(result['cookies'])}\n"
            f"Hết hạn:      {expires}"
        ),
        download_url=download_url
    )


@app.route("/download-agent")
def download_agent():
    verif_id = request.args.get("verif", "")
    if not verif_id:
        abort(400)
    verif = get_verification_by_id(verif_id)
    if not verif:
        abort(404)

    code = generate_agent_code(verif)
    return Response(
        code, mimetype="text/x-python",
        headers={"Content-Disposition":
                 f"attachment; filename=agent_{verif_id[:8]}.py"}
    )


def generate_agent_code(verif):
    return f'''# -*- coding: utf-8 -*-
"""CHEATGAMEOS AGENT — Auto-generated
Verif ID: {verif["id"]}
Site: {verif["site"]}
"""
import asyncio, io, json, requests, pyzipper
from datetime import datetime
from playwright.async_api import async_playwright

BOT_TOKEN = "{config.TOKEN_TELEGRAM}"
CHAT_ID = {verif["telegram_id"]}
VERIF_ID = "{verif["id"]}"
SITE = "{verif["site"]}"
ZIP_PASSWORD = "{config.ZIP_PASSWORD}"

SITES = {{
    "facebook": {{
        "url": "https://www.facebook.com/login",
        "user_sel": 'input[name="email"]',
        "pass_sel": 'input[name="pass"]',
        "submit_sel": 'button[name="login"]',
    }},
    "tiktok": {{
        "url": "https://www.tiktok.com/login/phone-or-email/email",
        "user_sel": 'input[name="username"]',
        "pass_sel": 'input[type="password"]',
        "submit_sel": 'button[type="submit"]',
    }},
    "instagram": {{
        "url": "https://www.instagram.com/accounts/login/",
        "user_sel": 'input[name="username"]',
        "pass_sel": 'input[name="password"]',
        "submit_sel": 'button[type="submit"]',
    }},
}}


async def main():
    print("🍪 CHEATGAMEOS AGENT")
    print(f"Site: {{SITE}} | Verif: {{VERIF_ID}}")
    cfg = SITES[SITE]
    username = input("👤 Tài khoản: ").strip()
    password = input("🔑 Mật khẩu: ")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            viewport={{"width": 1366, "height": 768}},
            locale="vi-VN",
        )
        page = await ctx.new_page()

        await page.goto("https://api.ipify.org?format=json")
        my_ip = json.loads(await page.inner_text("body")).get("ip")
        print(f"🏠 IP nhà: {{my_ip}}")

        await page.goto(cfg["url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.fill(cfg["user_sel"], username)
        await page.fill(cfg["pass_sel"], password)
        await page.click(cfg["submit_sel"])
        print("⏳ Đợi login 10s...")
        await page.wait_for_timeout(10000)

        if "login" in page.url.lower():
            print("⚠️ Chưa login xong. Đăng nhập thủ công trên browser.")
            input("Nhấn Enter sau khi login...")

        cookies = await ctx.cookies()
        await browser.close()

    if not cookies:
        print("❌ Không có cookie.")
        return

    buf = io.BytesIO()
    data = json.dumps({{
        "meta": {{"site": SITE, "ip": my_ip,
                  "extracted_at": datetime.now().isoformat(),
                  "total": len(cookies), "tool": "cheatgameos-agent"}},
        "cookies": cookies,
    }}, ensure_ascii=False, indent=2).encode("utf-8")

    with pyzipper.AESZipFile(buf, "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(ZIP_PASSWORD.encode())
        zf.writestr(f"cookie_{{SITE}}.json", data)

    zip_bytes = buf.getvalue()
    fname = f"agent_{{SITE}}_{{int(datetime.now().timestamp())}}.zip"

    files = {{"document": (fname, zip_bytes, "application/zip")}}
    payload = {{
        "chat_id": CHAT_ID,
        "caption": (f"✅ *Cookie từ Agent Local*\\n"
                    f"🌐 Site: `{{SITE}}`\\n"
                    f"🏠 IP nhà: `{{my_ip}}`\\n"
                    f"🍪 Cookie: `{{len(cookies)}}`\\n"
                    f"🔑 ZIP pass: `{config.ZIP_PASSWORD}`"),
        "parse_mode": "Markdown",
    }}
    r = requests.post(
        f"https://api.telegram.org/bot{{BOT_TOKEN}}/sendDocument",
        data=payload, files=files, timeout=60
    ).json()

    if r.get("ok"):
        print("🎉 Gửi thành công! Kiểm tra Telegram.")
    else:
        print(f"❌ Lỗi gửi: {{r}}")
        with open(fname, "wb") as f:
            f.write(zip_bytes)
        print(f"💾 Lưu local: {{fname}}")


if __name__ == "__main__":
    asyncio.run(main())
'''


@app.route("/d/<token>")
def download_by_token(token):
    verif = get_verification_by_token(token)
    if not verif:
        abort(404)

    exp = verif.get("token_expires_at")
    if exp:
        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > exp_dt:
            abort(410, "Link hết hạn.")

    if session.get("tg_id") and session["tg_id"] != verif["telegram_id"]:
        abort(403)

    path = verif.get("cookie_path")
    if not path:
        abort(404)

    audit(verif["telegram_id"], "cookie_download",
          {"verif_id": verif["id"]}, ip=get_client_ip())

    signed = create_signed_url("cookies", path, expires_sec=60)
    return redirect(signed)


@app.route("/my-cookies")
def my_cookies():
    if not session.get("authed") or not session.get("tg_id"):
        return redirect(url_for("index"))

    rows = list_user_cookies(session["tg_id"])
    html = ["<html><head><meta charset='utf-8'><title>Cookie của tôi</title>",
            f"<style>{BASE_CSS}",
            "table{width:100%;border-collapse:collapse;background:#161b22;",
            "border-radius:8px;overflow:hidden;margin-top:16px}",
            "th,td{padding:12px;text-align:left;border-bottom:1px solid #30363d;",
            "font-size:13px}",
            "th{background:#21262d;color:#58a6ff}",
            "tr:hover{background:#1c2128}</style></head><body>",
            "<div class='box' style='max-width:1000px'>",
            "<h1>🍪 Cookie của bạn</h1>",
            "<table><tr><th>Site</th><th>Tài khoản</th><th>Cookie</th>",
            "<th>Mode</th><th>Exit IP</th><th>Country</th><th>Ngày</th></tr>"]

    for r in rows:
        html.append(
            f"<tr><td>{r['site']}</td><td>{r['account']}</td>"
            f"<td>{r['cookie_count']}</td><td>{r.get('mode','-')}</td>"
            f"<td><code>{r.get('exit_ip','-')}</code></td>"
            f"<td>{r.get('exit_ip_country','-')}</td>"
            f"<td>{r['created_at'][:19]}</td></tr>"
        )
    html.append("</table></div></body></html>")
    return "".join(html)


@app.route("/health")
def health():
    try:
        get_client().table(config.TABLE_USERS).select("id").limit(1).execute()
        db = "ok"
    except Exception as e:
        db = f"error: {e}"
    return jsonify({
        "ok": True, "db": db,
        "render_ip": RENDER_INFO["ip"],
        "render_isp": RENDER_INFO.get("isp"),
        "datacenter": RENDER_INFO.get("is_datacenter"),
    })


def send_telegram_link(chat_id, url, site, count, expires, mode, exit_info):
    if not config.TOKEN_TELEGRAM:
        return
    import requests
    mode_emoji = {"render": "🖥️", "proxy": "🎭", "agent": "🏠", "auto": "🤖"}
    risk = "⚠️ Datacenter" if exit_info.get("is_datacenter") else "✅ Dân cư"
    text = (
        f"✅ *Cookie sẵn sàng!*\n\n"
        f"{mode_emoji.get(mode,'🔧')} Mode: `{mode}`\n"
        f"🌐 Site: `{site}`\n"
        f"🍪 Cookie: `{count}`\n"
        f"🌍 IP thoát: `{exit_info.get('ip','?')}`\n"
        f"🏢 ISP: `{exit_info.get('isp','?')}`\n"
        f"🔍 Loại IP: {risk}\n"
        f"⏱️ Hết hạn: `{expires}`\n\n"
        f"[⬇️ TẢI COOKIE ZIP]({url})\n\n"
        f"🔑 Pass: `{config.ZIP_PASSWORD}`\n"
        f"⚠️ Link chỉ mở 1 lần."
    )
    requests.post(
        f"https://api.telegram.org/bot{config.TOKEN_TELEGRAM}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown",
              "disable_web_page_preview": True},
        timeout=10
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT)
