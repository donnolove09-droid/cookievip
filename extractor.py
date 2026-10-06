# -*- coding: utf-8 -*-
"""extractor.py — Playwright + AUTO IP."""

import io
import json
import requests
import pyzipper
from datetime import datetime
from playwright.async_api import async_playwright

from config import (
    PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT,
    ZIP_PASSWORD, DEFAULT_PROXY
)

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

DATACENTER_KEYWORDS = [
    "amazon", "aws", "google", "gcp", "microsoft", "azure",
    "digitalocean", "render", "ovh", "hetzner", "linode",
    "vultr", "cloudflare", "fastly", "akamai", "oracle",
]


def get_my_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception:
        return "unknown"


def get_ip_info(ip):
    try:
        d = requests.get(
            f"http://ip-api.com/json/{ip}"
            f"?fields=status,country,city,isp,org,as,query",
            timeout=5
        ).json()
        if d.get("status") != "success":
            return {"ip": ip, "is_datacenter": True}
        isp = (d.get("isp") or "") + " " + (d.get("org") or "") + " " + (d.get("as") or "")
        is_dc = any(k in isp.lower() for k in DATACENTER_KEYWORDS)
        return {
            "ip": ip,
            "country": d.get("country"),
            "city": d.get("city"),
            "isp": d.get("isp"),
            "org": d.get("org"),
            "is_datacenter": is_dc,
        }
    except Exception:
        return {"ip": ip, "is_datacenter": True}


_RENDER_IP_CACHE = None


def get_render_ip_info(force=False):
    global _RENDER_IP_CACHE
    if _RENDER_IP_CACHE is None or force:
        ip = get_my_ip()
        info = get_ip_info(ip)
        info["ip"] = ip
        _RENDER_IP_CACHE = info
    return _RENDER_IP_CACHE


def decide_mode(user_mode, user_proxy):
    user_mode = (user_mode or "auto").lower()
    user_proxy = (user_proxy or "").strip()

    if user_mode == "agent":
        return {"mode": "agent", "proxy": None, "reason": "User chọn Agent Local"}
    if user_mode == "proxy":
        if not user_proxy:
            return {"mode": "error", "proxy": None, "reason": "Chọn Proxy nhưng chưa nhập"}
        return {"mode": "proxy", "proxy": user_proxy, "reason": "User proxy"}
    if user_mode == "render":
        return {"mode": "render", "proxy": None, "reason": "User chọn IP Render"}

    if user_proxy:
        return {"mode": "proxy", "proxy": user_proxy, "reason": "Auto → có user proxy"}
    if DEFAULT_PROXY:
        return {"mode": "proxy", "proxy": DEFAULT_PROXY, "reason": "Auto → env DEFAULT_PROXY"}
    return {"mode": "render", "proxy": None, "reason": "Auto → dùng IP Render"}


def parse_proxy(s):
    if not s:
        return None
    s = s.strip()
    if "://" not in s:
        s = "http://" + s
    scheme, rest = s.split("://", 1)
    scheme = scheme.lower()
    if scheme not in ("http", "https", "socks5", "socks4"):
        raise ValueError(f"Proxy scheme không hỗ trợ: {scheme}")
    proxy = {"server": f"{scheme}://{rest}"}
    if "@" in rest:
        creds, host = rest.rsplit("@", 1)
        if ":" in creds:
            u, p = creds.split(":", 1)
            proxy["username"] = u
            proxy["password"] = p
            proxy["server"] = f"{scheme}://{host}"
    return proxy


async def login_and_get_cookies(site, username, password,
                                 proxy_str=None, headless=None):
    if site not in SITES:
        return {"success": False, "error": f"Site '{site}' không hỗ trợ."}

    if headless is None:
        headless = PLAYWRIGHT_HEADLESS

    proxy_cfg = None
    if proxy_str:
        try:
            proxy_cfg = parse_proxy(proxy_str)
        except Exception as e:
            return {"success": False, "error": f"Proxy lỗi: {e}"}

    cfg = SITES[site]
    result = {"success": False, "cookies": [], "error": None,
              "screenshot": None, "exit_info": None, "risk": "unknown"}

    async with async_playwright() as p:
        launch_args = {
            "headless": headless,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        }
        if proxy_cfg:
            launch_args["proxy"] = proxy_cfg

        browser = await p.chromium.launch(**launch_args)
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 768},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        page = await ctx.new_page()

        try:
            try:
                await page.goto("https://api.ipify.org?format=json",
                                timeout=10000, wait_until="domcontentloaded")
                body = await page.inner_text("body")
                exit_ip = json.loads(body).get("ip")
                info = get_ip_info(exit_ip)
                info["ip"] = exit_ip
                result["exit_info"] = info
                result["risk"] = "high" if info.get("is_datacenter") else "low"
            except Exception:
                result["exit_info"] = {"ip": "unknown", "is_datacenter": True}
                result["risk"] = "unknown"

            await page.goto(cfg["url"], timeout=PLAYWRIGHT_TIMEOUT * 1000,
                            wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            await page.fill(cfg["user_sel"], username, timeout=15000)
            await page.wait_for_timeout(500)
            await page.fill(cfg["pass_sel"], password, timeout=15000)
            await page.wait_for_timeout(500)
            await page.click(cfg["submit_sel"], timeout=15000)
            await page.wait_for_timeout(8000)

            url = page.url
            shot = f"/tmp/shot_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=shot, full_page=False)
            result["screenshot"] = shot

            if "login" not in url.lower() and "checkpoint" not in url.lower():
                result["success"] = True
                result["cookies"] = await ctx.cookies()
            else:
                result["error"] = f"Login fail / checkpoint. URL: {url}"

        except Exception as e:
            result["error"] = f"Playwright: {e}"
        finally:
            await browser.close()

    return result


def export_cookies_zip_bytes(cookies, site, username, password=None):
    pwd = (password or ZIP_PASSWORD).encode("utf-8")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_user = "".join(c for c in username if c.isalnum() or c in "._-")[:30]
    fname = f"cheatgameos_{site}_{safe_user}_{ts}.zip"

    json_data = json.dumps({
        "meta": {
            "site": site, "username": username,
            "extracted_at": datetime.now().isoformat(),
            "total": len(cookies), "tool": "cheatgameos",
        },
        "cookies": cookies,
    }, ensure_ascii=False, indent=2).encode("utf-8")

    header_data = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies
    ).encode("utf-8")

    buf = io.BytesIO()
    with pyzipper.AESZipFile(buf, "w", compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(pwd)
        zf.writestr(f"cookie_{site}_{safe_user}.json", json_data)
        zf.writestr(f"cookie_header_{site}.txt", header_data)

    return buf.getvalue(), fname


def mask_proxy(p):
    if not p:
        return ""
    if "@" in p:
        creds, host = p.rsplit("@", 1)
        if "://" in creds:
            scheme, userinfo = creds.split("://", 1)
            if ":" in userinfo:
                u, _ = userinfo.split(":", 1)
                return f"{scheme}://{u}:***@{host}"
        return f"***@{host}"
    return p
