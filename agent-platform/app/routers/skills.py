"""Skill 资产库"""
from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/skills", tags=["skills"])


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
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name 必填")
    sid = conn.execute(
        "INSERT INTO skills(name,scope,category,owner_name,description) VALUES(?,?,?,?,?)",
        (name, body.get("scope", "公开"), body.get("category", ""),
         body.get("owner_name", person["name"]), body.get("description", ""))).lastrowid
    conn.commit()
    audit(conn, person["name"], "新增Skill", name)
    return dict(conn.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone())
