"""Skill 资产库"""
from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/skills", tags=["skills"])
SKILL_SCOPES = ("公开", "组织", "个人")


def _check_maintainer(person):
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可维护 Skill")


@router.get("")
def list_skills(scope: str = None, conn=Depends(db_conn), person=Depends(get_current_person)):
    sql = "SELECT * FROM skills"
    args = []
    if scope:
        sql += " WHERE scope=?"
        args.append(scope)
    sql += " ORDER BY id"
    return [dict(r) for r in conn.execute(sql, args)]


@router.post("")
def create_skill(body: dict = Body(...), conn=Depends(db_conn), person=Depends(get_current_person)):
    _check_maintainer(person)
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name 必填")
    scope = body.get("scope", "公开")
    if scope not in SKILL_SCOPES:
        raise HTTPException(422, f"scope 仅允许：{'/'.join(SKILL_SCOPES)}")
    sid = conn.execute(
        "INSERT INTO skills(name,scope,category,owner_name,description) VALUES(?,?,?,?,?)",
        (name, scope, body.get("category", ""),
         body.get("owner_name", person["name"]), body.get("description", ""))).lastrowid
    conn.commit()
    audit(conn, person["name"], "新增Skill", name)
    return dict(conn.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone())


@router.patch("/{sid}")
def update_skill(sid: int, body: dict = Body(...), conn=Depends(db_conn),
                 person=Depends(get_current_person)):
    """维护 Skill：name/scope/category/owner_name/description，权限 coach/boss"""
    _check_maintainer(person)
    row = conn.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    if "scope" in body and body["scope"] not in SKILL_SCOPES:
        raise HTTPException(422, f"scope 仅允许：{'/'.join(SKILL_SCOPES)}")
    allowed = ("name", "scope", "category", "owner_name", "description")
    sets, args = [], []
    for k in allowed:
        if k in body:
            sets.append(f"{k}=?")
            args.append(body[k])
    if not sets:
        raise HTTPException(400, "没有可更新的字段")
    args.append(sid)
    conn.execute(f"UPDATE skills SET {', '.join(sets)} WHERE id=?", args)
    conn.commit()
    audit(conn, person["name"], "更新Skill", row["name"], f"更新字段：{','.join(body.keys())}")
    return dict(conn.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone())


@router.delete("/{sid}")
def delete_skill(sid: int, conn=Depends(db_conn), person=Depends(get_current_person)):
    """删除 Skill，权限 coach/boss"""
    _check_maintainer(person)
    row = conn.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    conn.execute("DELETE FROM skills WHERE id=?", (sid,))
    conn.commit()
    audit(conn, person["name"], "删除Skill", row["name"])
    return {"ok": True, "deleted": sid}
