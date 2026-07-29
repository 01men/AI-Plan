"""OAuth 一次性状态、登录交换码与第三方错误脱敏。"""
import json
import secrets
from datetime import datetime, timedelta


def create_oauth_state(conn, provider: str, action: str, person_id: int | None = None,
                       ttl_minutes: int = 10) -> str:
    token = secrets.token_urlsafe(32)
    payload = {
        "provider": provider,
        "action": action,
        "person_id": person_id,
        "expires_at": (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds"),
    }
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?)",
                 (f"oauth-state:{token}", json.dumps(payload, ensure_ascii=False)))
    conn.commit()
    return token


def consume_oauth_state(conn, token: str, provider: str) -> dict | None:
    """原子消费 state；错误、过期、平台不匹配均返回 None，禁止重放。"""
    if not token or len(token) > 128:
        return None
    key = f"oauth-state:{token}"
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM settings WHERE key=?", (key,))
    conn.commit()
    try:
        payload = json.loads(row["value"])
        if payload.get("provider") != provider:
            return None
        if datetime.fromisoformat(payload["expires_at"]) < datetime.now():
            return None
        return payload
    except Exception:
        return None


def create_login_code(conn, person_id: int, provider: str, ttl_minutes: int = 2) -> str:
    code = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO oauth_login_codes(code,person_id,provider,expires_at) VALUES(?,?,?,?)",
        (code, person_id, provider,
         (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds")),
    )
    conn.commit()
    return code


def consume_login_code(conn, code: str):
    """一次性换取人员身份；成功后立即标记使用，禁止浏览器重放。"""
    if not code or len(code) > 128:
        return None
    row = conn.execute(
        "SELECT * FROM oauth_login_codes WHERE code=? AND used_at IS NULL", (code,)
    ).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return None
    conn.execute("UPDATE oauth_login_codes SET used_at=? WHERE code=?",
                 (datetime.now().isoformat(timespec="seconds"), code))
    conn.commit()
    return row


def public_error(exc: Exception) -> str:
    """只返回类型/HTTP 状态，不回显第三方响应体、请求 URL 或凭证。"""
    code = getattr(exc, "code", None)
    if code:
        return f"第三方服务返回 HTTP {code}"
    if isinstance(exc, TimeoutError):
        return "第三方服务响应超时"
    return f"调用失败（{type(exc).__name__}）"
