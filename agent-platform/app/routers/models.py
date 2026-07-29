"""模型供应商配置（R4-1）：内置国内主流模型，全局默认 + 单员覆盖"""
from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/models", tags=["models"])


def _view(row, default_key):
    """供应商视图：api_key 脱敏为 已配置/未配置，标注是否全局默认"""
    d = dict(row)
    d["api_key"] = "已配置" if (row["api_key"] or "").strip() else "未配置"
    d["enabled"] = bool(row["enabled"])
    d["is_default"] = row["key"] == default_key
    return d


def _default_key(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='default_model_key'").fetchone()
    return row["value"] if row else "glm"


@router.get("")
def list_models(conn=Depends(db_conn), person=Depends(get_current_person)):
    dk = _default_key(conn)
    return [_view(r, dk) for r in conn.execute("SELECT * FROM model_providers ORDER BY id")]


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
    """配置单个供应商：可改 api_key / default_model / enabled；api_key 返回时脱敏"""
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可配置模型")
    row = conn.execute("SELECT * FROM model_providers WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"模型供应商不存在：{key}")
    sets, args = [], []
    if "api_key" in body:
        sets.append("api_key=?")
        args.append((body.get("api_key") or "").strip())
    if "default_model" in body:
        sets.append("default_model=?")
        args.append((body.get("default_model") or "").strip())
    if "enabled" in body:
        sets.append("enabled=?")
        args.append(1 if body.get("enabled") else 0)
    if not sets:
        raise HTTPException(400, "没有可更新的字段（支持 api_key/default_model/enabled）")
    args.append(key)
    conn.execute(f"UPDATE model_providers SET {', '.join(sets)} WHERE key=?", args)
    conn.commit()
    # 审计留痕只记改了哪些字段，绝不落 api_key 明文
    audit(conn, person["name"], "配置模型供应商", row["name"],
          f"更新字段：{','.join(body.keys())}")
    updated = conn.execute("SELECT * FROM model_providers WHERE key=?", (key,)).fetchone()
    return _view(updated, _default_key(conn))
