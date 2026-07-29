"""模型供应商配置（R4-1）：内置国内主流模型，全局默认 + 单员覆盖

R5 变更：api_key 以 enc:v1 密文落库（app/crypto.py）；支持 base_url/temperature/timeout
配置与「测试连接」端点；密钥只在使用时内存解密，返回与审计永远脱敏。
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app import crypto
from app.routers.auth import audit, db_conn, get_current_person
from app.security import public_error

router = APIRouter(prefix="/api/models", tags=["models"])


def _view(row, default_key, admin=True):
    """供应商视图：api_key 脱敏为 已配置/未配置，标注是否全局默认"""
    d = dict(row)
    d["api_key"] = "已配置" if (row["api_key"] or "").strip() else "未配置"
    d["enabled"] = bool(row["enabled"])
    d["is_default"] = row["key"] == default_key
    if not admin:
        for field in ("base_url", "last_test_message"):
            d.pop(field, None)
    return d


def _default_key(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='default_model_key'").fetchone()
    return row["value"] if row else "glm"


@router.get("")
def list_models(conn=Depends(db_conn), person=Depends(get_current_person)):
    dk = _default_key(conn)
    admin = person["tier"] in ("boss", "coach")
    return [_view(r, dk, admin) for r in conn.execute("SELECT * FROM model_providers ORDER BY id")]


def _validated_base_url(value: str, provider_key: str) -> str:
    value = value.strip().rstrip("/")
    if provider_key == "kimi" and value in (
        "https://api.kimi.com/coding", "https://api.kimi.com/coding/v1/"
    ):
        value = "https://api.kimi.com/coding/v1"
    parsed = urllib.parse.urlparse(value)
    local = parsed.hostname in ("127.0.0.1", "localhost")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise HTTPException(422, "Base URL 必须使用 HTTPS（仅本机 localhost 可用 HTTP）")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422, "Base URL 格式不正确")
    return value


@router.put("/default")
def set_default_model(body: dict = Body(...), conn=Depends(db_conn),
                      person=Depends(get_current_person)):
    """设置全局默认模型：{"key": "kimi"}（未绑定 model_key 的数字员工跟随此默认）"""
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可配置模型")
    key = (body.get("key") or "").strip()
    row = conn.execute("SELECT * FROM model_providers WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"模型供应商不存在：{key}")
    conn.execute("INSERT INTO settings(key,value) VALUES('default_model_key',?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,))
    conn.commit()
    audit(conn, person["name"], "设置默认模型", row["name"])
    dk = _default_key(conn)
    return {"ok": True, "default_model_key": dk,
            "providers": [_view(r, dk) for r in conn.execute("SELECT * FROM model_providers ORDER BY id")]}


@router.put("/{key}")
def update_model(key: str, body: dict = Body(...), conn=Depends(db_conn),
                 person=Depends(get_current_person)):
    """配置单个供应商：可改 api_key/base_url/default_model/temperature/timeout/enabled；
    api_key 加密落库、返回时脱敏"""
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可配置模型")
    row = conn.execute("SELECT * FROM model_providers WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"模型供应商不存在：{key}")
    sets, args = [], []
    if "api_key" in body:
        plain = (body.get("api_key") or "").strip()
        sets.append("api_key=?")
        args.append(crypto.encrypt(plain) if plain else "")
    if "base_url" in body:
        sets.append("base_url=?")
        base_url = _validated_base_url((body.get("base_url") or ""), key)
        args.append(base_url)
        if key == "kimi" and "api.kimi.com/coding" in base_url and "temperature" not in body:
            sets.append("temperature=?")
            args.append(1.0)
    if "default_model" in body:
        sets.append("default_model=?")
        args.append((body.get("default_model") or "").strip())
    if "temperature" in body:
        try:
            temp = float(body.get("temperature"))
        except (TypeError, ValueError):
            raise HTTPException(422, "temperature 必须是 0-2 之间的数字")
        if not 0 <= temp <= 2:
            raise HTTPException(422, "temperature 必须在 0-2 之间")
        sets.append("temperature=?")
        args.append(temp)
    if "timeout" in body:
        try:
            timeout = int(body.get("timeout"))
        except (TypeError, ValueError):
            raise HTTPException(422, "timeout 必须是 5-120 之间的整数秒")
        if not 5 <= timeout <= 120:
            raise HTTPException(422, "timeout 必须在 5-120 秒之间")
        sets.append("timeout=?")
        args.append(timeout)
    if "enabled" in body:
        sets.append("enabled=?")
        args.append(1 if body.get("enabled") else 0)
    if not sets:
        raise HTTPException(
            400, "没有可更新的字段（支持 api_key/base_url/default_model/temperature/timeout/enabled）")
    args.append(key)
    conn.execute(f"UPDATE model_providers SET {', '.join(sets)} WHERE key=?", args)
    conn.commit()
    # 审计留痕只记改了哪些字段，绝不落 api_key 明文
    audit(conn, person["name"], "配置模型供应商", row["name"],
          f"更新字段：{','.join(body.keys())}")
    updated = conn.execute("SELECT * FROM model_providers WHERE key=?", (key,)).fetchone()
    return _view(updated, _default_key(conn))


@router.post("/{key}/test")
def test_model(key: str, conn=Depends(db_conn), person=Depends(get_current_person)):
    """测试连接：以当前配置真实请求供应商 /models，返回连通性与延迟（不脱敏密钥出参）"""
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可测试模型连接")
    row = conn.execute("SELECT * FROM model_providers WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"模型供应商不存在：{key}")
    api_key = crypto.decrypt(row["api_key"] or "")
    if not api_key.strip():
        return {"ok": False, "provider": key, "error": "未配置 API Key，请先保存密钥后再测试"}
    cols = row.keys()
    timeout = row["timeout"] if "timeout" in cols and row["timeout"] else 30
    started = time.monotonic()
    try:
        req = urllib.request.Request(
            row["base_url"].rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=min(timeout, 20)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency = int((time.monotonic() - started) * 1000)
        count = len(data.get("data", [])) if isinstance(data, dict) else 0
        conn.execute(
            "UPDATE model_providers SET last_test_status='通过',last_test_message=?,"
            "last_tested_at=? WHERE key=?",
            (f"连接正常，发现 {count} 个模型，耗时 {latency}ms",
             datetime.now().isoformat(timespec="seconds"), key),
        )
        conn.commit()
        audit(conn, person["name"], "测试模型连接", row["name"], f"通过，{latency}ms")
        return {"ok": True, "provider": key, "latency_ms": latency, "models_count": count,
                "default_model": row["default_model"]}
    except Exception as e:
        latency = int((time.monotonic() - started) * 1000)
        error = public_error(e)
        conn.execute(
            "UPDATE model_providers SET last_test_status='失败',last_test_message=?,"
            "last_tested_at=? WHERE key=?",
            (error, datetime.now().isoformat(timespec="seconds"), key),
        )
        conn.commit()
        audit(conn, person["name"], "测试模型连接", row["name"], f"失败，{latency}ms")
        return {"ok": False, "provider": key, "latency_ms": latency,
                "error": error}
