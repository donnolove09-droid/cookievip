# -*- coding: utf-8 -*-
"""config.py — Load toàn bộ env."""

import os
from dotenv import load_dotenv

load_dotenv()


def _b(k, d=False):
    v = os.getenv(k)
    return d if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _i(k, d=0):
    try:
        return int(os.getenv(k, d))
    except (TypeError, ValueError):
        return d


def _l(k):
    return [x.strip() for x in os.getenv(k, "").split(",") if x.strip()]


# ===== TELEGRAM =====
TOKEN_TELEGRAM   = os.getenv("TOKEN_TELEGRAM", "")
TEN_BOT_TELEGRAM = os.getenv("TEN_BOT_TELEGRAM", "CheatGameOS Bot")
USERNAME_BOT     = os.getenv("USERNAME_BOT_TELEGRAM", "cheatgameos_bot")
ALLOWED_IDS      = [int(x) for x in _l("ALLOWED_IDS") if x.isdigit()]

CMD_START     = os.getenv("CMD_START", "start").lstrip("/")
CMD_HELP      = os.getenv("CMD_HELP", "help").lstrip("/")
CMD_ID        = os.getenv("CMD_ID", "id").lstrip("/")
CMD_COOKIE    = os.getenv("CMD_COOKIE", "cookie").lstrip("/")
CMD_MYCOOKIES = os.getenv("CMD_MYCOOKIES", "mycookies").lstrip("/")
CMD_CANCEL    = os.getenv("CMD_CANCEL", "cancel").lstrip("/")

# ===== API =====
API_KEY    = os.getenv("API_KEY", "cheatgame")
SECRET_KEY = os.getenv("SECRET_KEY", "change_me")

# ===== WEB =====
WEB_URL = os.getenv("WEB_URL", "http://localhost:8080")
PORT    = _i("PORT", 8080)

# ===== SUPABASE =====
SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY    = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET_SELFIES       = os.getenv("SUPABASE_BUCKET_SELFIES", "selfies")
BUCKET_COOKIES       = os.getenv("SUPABASE_BUCKET_COOKIES", "cookies")
TABLE_USERS          = os.getenv("SUPABASE_TABLE_USERS", "cg_users")
TABLE_VERIFICATIONS  = os.getenv("SUPABASE_TABLE_VERIFICATIONS", "cg_verifications")
TABLE_AUDIT          = os.getenv("SUPABASE_TABLE_AUDIT", "cg_audit_log")

# ===== EXTRACTOR =====
ZIP_PASSWORD        = os.getenv("ZIP_PASSWORD", "cheatgame")
RETENTION_DAYS      = _i("DATA_RETENTION_DAYS", 7)
DOWNLOAD_TTL        = _i("DOWNLOAD_TOKEN_TTL", 300)
PLAYWRIGHT_HEADLESS = _b("PLAYWRIGHT_HEADLESS", True)
PLAYWRIGHT_TIMEOUT  = _i("PLAYWRIGHT_TIMEOUT", 60)

# ===== PROXY =====
DEFAULT_PROXY    = os.getenv("DEFAULT_PROXY", "").strip()
ALLOW_USER_PROXY = _b("ALLOW_USER_PROXY", True)

# ===== IP AUTO =====
DEFAULT_MODE    = os.getenv("DEFAULT_MODE", "auto").lower()
SHOW_RENDER_IP  = _b("SHOW_RENDER_IP", True)

# ===== SITES =====
SITES_ENABLED = {
    "facebook":  _b("ENABLE_FACEBOOK", True),
    "tiktok":    _b("ENABLE_TIKTOK", True),
    "instagram": _b("ENABLE_INSTAGRAM", True),
}

# ===== RATE LIMIT =====
RATE_LIMIT_PER_DAY = _i("RATE_LIMIT_PER_DAY", 5)


def validate():
    missing = []
    if not TOKEN_TELEGRAM:
        missing.append("TOKEN_TELEGRAM")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("SUPABASE_SERVICE_KEY")
    if missing:
        raise RuntimeError(f"❌ Thiếu env: {', '.join(missing)}")


def summary():
    def mask(s, k=6):
        if not s: return "(empty)"
        return s[:k] + "..." + s[-k:] if len(s) > k * 2 else s[:k] + "..."
    return "\n".join([
        "═══════════ CHEATGAMEOS ═══════════",
        f"🤖 Bot     : {TEN_BOT_TELEGRAM} (@{USERNAME_BOT})",
        f"🔑 Token   : {mask(TOKEN_TELEGRAM, 10)}",
        f"👥 IDs     : {ALLOWED_IDS or '(all)'}",
        f"🌐 Web     : {WEB_URL}",
        f"🗄️  Supabase: {SUPABASE_URL}",
        f"🎭 Proxy   : {mask(DEFAULT_PROXY, 8) if DEFAULT_PROXY else '(auto)'}",
        f"🔧 Mode    : {DEFAULT_MODE}",
        f"🌍 Sites   : {[k for k, v in SITES_ENABLED.items() if v]}",
        "═══════════════════════════════════",
    ])
