# -*- coding: utf-8 -*-
"""supabase_client.py — Wrapper Supabase."""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

from config import (
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    BUCKET_SELFIES, BUCKET_COOKIES,
    TABLE_USERS, TABLE_VERIFICATIONS, TABLE_AUDIT,
    DOWNLOAD_TTL
)

_client: Client = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("Thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_KEY")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def upsert_user(telegram_id, username=None, full_name=None, phone=None):
    sb = get_client()
    res = sb.table(TABLE_USERS).upsert({
        "telegram_id": telegram_id,
        "telegram_username": username,
        "full_name": full_name,
        "phone": phone,
    }, on_conflict="telegram_id").execute()
    return res.data[0] if res.data else {}


def upload_selfie(telegram_id, file_bytes, filename):
    sb = get_client()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(filename)[1] or ".jpg"
    path = f"{telegram_id}/{ts}_{secrets.token_hex(4)}{ext}"
    sha = hashlib.sha256(file_bytes).hexdigest()
    sb.storage.from_(BUCKET_SELFIES).upload(
        path=path, file=file_bytes,
        file_options={"content-type": "image/jpeg", "upsert": "false"}
    )
    return path, sha


def upload_cookie_zip(telegram_id, zip_bytes, filename):
    sb = get_client()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = f"{telegram_id}/{ts}_{filename}"
    sb.storage.from_(BUCKET_COOKIES).upload(
        path=path, file=zip_bytes,
        file_options={"content-type": "application/zip", "upsert": "false"}
    )
    return path


def create_signed_url(bucket, path, expires_sec=60):
    sb = get_client()
    res = sb.storage.from_(bucket).create_signed_url(path, expires_sec)
    return res.get("signedURL") or res.get("signed_url")


def create_verification(telegram_id, user_id, site, account, phone,
                        selfie_path, selfie_hash, ip, ua,
                        user_ip=None, proxy_used=None, mode="auto"):
    sb = get_client()
    data = {
        "telegram_id": telegram_id,
        "user_id": user_id,
        "site": site,
        "account": mask_account(account),
        "phone": phone,
        "selfie_path": selfie_path,
        "selfie_hash": selfie_hash,
        "status": "pending",
        "ip_address": ip,
        "user_ip": user_ip,
        "proxy_used": proxy_used,
        "mode": mode,
        "user_agent": ua[:500] if ua else None,
    }
    res = sb.table(TABLE_VERIFICATIONS).insert(data).execute()
    return res.data[0]


def complete_verification(verif_id, cookie_path, cookie_count, exit_info=None):
    sb = get_client()
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=DOWNLOAD_TTL)
    update = {
        "status": "success",
        "cookie_path": cookie_path,
        "cookie_count": cookie_count,
        "download_token": token,
        "token_expires_at": expires.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if exit_info:
        update.update({
            "exit_ip": exit_info.get("ip"),
            "exit_ip_country": exit_info.get("country"),
            "exit_ip_isp": exit_info.get("isp"),
            "exit_ip_is_dc": exit_info.get("is_datacenter", False),
        })
    sb.table(TABLE_VERIFICATIONS).update(update).eq("id", verif_id).execute()
    return token, expires.isoformat()


def fail_verification(verif_id, error):
    sb = get_client()
    sb.table(TABLE_VERIFICATIONS).update({
        "status": "failed",
        "error_msg": error[:1000],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", verif_id).execute()


def get_verification_by_token(token):
    sb = get_client()
    res = sb.table(TABLE_VERIFICATIONS).select("*").eq(
        "download_token", token
    ).limit(1).execute()
    return res.data[0] if res.data else None


def get_verification_by_id(verif_id):
    sb = get_client()
    res = sb.table(TABLE_VERIFICATIONS).select("*").eq(
        "id", verif_id
    ).limit(1).execute()
    return res.data[0] if res.data else None


def list_user_cookies(telegram_id, limit=20):
    sb = get_client()
    res = sb.table(TABLE_VERIFICATIONS).select(
        "id,site,account,status,cookie_count,created_at,"
        "completed_at,mode,exit_ip,exit_ip_country,exit_ip_isp"
    ).eq("telegram_id", telegram_id).eq(
        "status", "success"
    ).order("created_at", desc=True).limit(limit).execute()
    return res.data or []


def count_today(telegram_id):
    sb = get_client()
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    res = sb.table(TABLE_VERIFICATIONS).select("id", count="exact").eq(
        "telegram_id", telegram_id
    ).gte("created_at", today).execute()
    return res.count or 0


def audit(telegram_id, action, detail=None, ip=None):
    sb = get_client()
    try:
        sb.table(TABLE_AUDIT).insert({
            "telegram_id": telegram_id,
            "action": action,
            "detail": detail or {},
            "ip": ip,
        }).execute()
    except Exception:
        pass


def mask_account(account):
    if "@" in account:
        n, d = account.split("@", 1)
        return (n[:2] + "*" * max(0, len(n) - 4) + n[-2:] + "@" + d
                if len(n) > 4 else "*" * len(n) + "@" + d)
    if len(account) <= 4:
        return account[0] + "*" * (len(account) - 1)
    return account[:2] + "*" * (len(account) - 4) + account[-2:]
