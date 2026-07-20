"""治理：激励、费用报销三级流转、审计、红线"""
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/governance", tags=["governance"])

# AI 应用六大红线（内置常量）
REDLINES = [
    {"id": 1, "text": "AI 不得直连生产数据库"},
    {"id": 2, "text": "AI 不得直接修改正式业务数据"},
    {"id": 3, "text": "AI 不得绕过人工自动提交审批"},
    {"id": 4, "text": "未经评审不得向公网部署"},
    {"id": 5, "text": "写回动作必须人工确认并留痕"},
    {"id": 6, "text": "敏感数据必须脱敏"},
]

# 报销三级流转：step → (当前状态, 通过后状态)
REIMB_FLOW = {1: ("待平台长审批", "待数字化复核"), 2: ("待数字化复核", "待财务报销"), 3: ("待财务报销", "已完成")}

# 激励申报金额档位（元）
INCENTIVE_AMOUNT_RANGE = {"火花奖": (500, 2000), "银齿轮奖": (5000, 10000), "金扳手奖": (30000, 50000)}

# 激励奖项类型枚举（仅允许这四种；带空格等变体与未收录奖项一律 422 拦截）
INCENTIVE_TYPES = ("火花奖", "银齿轮奖", "金扳手奖", "种子基金")


@router.get("/incentives")
def list_incentives(status: str = None, conn=Depends(db_conn), person=Depends(get_current_person)):
    sql = "SELECT * FROM incentives"
    args = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, args)]


@router.post("/incentives")
def create_incentive(body: dict = Body(...), conn=Depends(db_conn),
                     person=Depends(get_current_person)):
    nominee = (body.get("nominee") or "").strip()
    if not nominee:
        raise HTTPException(400, "nominee 必填")
    itype = body.get("type", "火花奖")
    if itype not in INCENTIVE_TYPES:
        raise HTTPException(422, "奖项类型仅允许：火花奖/银齿轮奖/金扳手奖/种子基金")
    amount = body.get("amount", 0)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise HTTPException(422, f"金额格式不正确：{amount}")
    if itype in INCENTIVE_AMOUNT_RANGE:
        lo, hi = INCENTIVE_AMOUNT_RANGE[itype]
        if not (lo <= amount <= hi):
            raise HTTPException(422, f"{itype}申报金额须在 {lo:.0f}-{hi:.0f} 元之间，当前 {amount:.0f} 元超出档位")
    elif itype == "种子基金":
        # 种子基金从降本增效提取，纳入年度激励池（10 万元）管理，须为正且不超过池上限
        if not (0 < amount <= 100000):
            raise HTTPException(422, f"种子基金申报金额须在 1-100000 元之间（年度激励池上限 10 万元），当前 {amount:.0f} 元超出范围")
    iid = conn.execute(
        "INSERT INTO incentives(type,nominee,reason,amount,status,created_at) VALUES(?,?,?,?,?,?)",
        (itype, nominee, body.get("reason", ""), amount,
         "申报中", datetime.now().isoformat(timespec="seconds"))).lastrowid
    conn.commit()
    audit(conn, person["name"], "激励申报", nominee, f"{itype} ¥{amount}")
    return dict(conn.execute("SELECT * FROM incentives WHERE id=?", (iid,)).fetchone())


@router.get("/reimbursements")
def list_reimbursements(status: str = None, conn=Depends(db_conn),
                        person=Depends(get_current_person)):
    sql = "SELECT * FROM reimbursements"
    args = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, args)]


@router.post("/reimbursements")
def create_reimbursement(body: dict = Body(...), conn=Depends(db_conn),
                         person=Depends(get_current_person)):
    amount = body.get("amount")
    if amount is None:
        raise HTTPException(400, "amount 必填")
    rid = conn.execute(
        "INSERT INTO reimbursements(applicant,provider,tokens,amount,status,step,created_at)"
        " VALUES(?,?,?,?,'待平台长审批',1,?)",
        (body.get("applicant", person["name"]), body.get("provider", ""), body.get("tokens", 0),
         amount, datetime.now().isoformat(timespec="seconds"))).lastrowid
    conn.commit()
    audit(conn, person["name"], "报销申请", f"报销#{rid}", f"{body.get('provider','')} ¥{amount}")
    return dict(conn.execute("SELECT * FROM reimbursements WHERE id=?", (rid,)).fetchone())


@router.post("/reimbursements/{rid}/approve")
def approve_reimbursement(rid: int, body: dict = Body(...), conn=Depends(db_conn),
                          person=Depends(get_current_person)):
    """三级流转：平台长→数字化复核→财务→已完成；任意级驳回即终止。

    分权规则：
    - 第 1 级（平台长审批）：tier ∈ {coach, backbone, boss}
    - 第 2 级（数字化复核）：仅 coach（数字化平台长）
    - 第 3 级（财务报销）：仅财务部 backbone 或 boss
    - 同一人不能审批同一单的连续两级（含已批准过的任一级）
    每级审批意见累加进 comment 列并写 audits。
    """
    row = conn.execute("SELECT * FROM reimbursements WHERE id=?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, "报销单不存在")
    action = body.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action 仅支持 approve/reject")
    if row["status"] in ("已完成", "已驳回"):
        raise HTTPException(400, f"该单已终结（{row['status']}）")

    step = row["step"]
    if step == 1 and person["tier"] not in ("coach", "backbone", "boss"):
        raise HTTPException(403, "第一级（平台长审批）须由教练团/骨干/高管审批")
    if step == 2 and person["tier"] != "coach":
        raise HTTPException(403, "第二级（数字化复核）仅数字化平台长（教练团）可审批")
    if step == 3:
        is_fin_backbone = person["tier"] == "backbone" and person.get("dept_name") == "财务部"
        if not (is_fin_backbone or person["tier"] == "boss"):
            raise HTTPException(403, "第三级（财务报销）仅财务部骨干或高管可审批")
    # 同一人不能审批连续两级：查 audits 中本单已有的通过记录
    approved_before = conn.execute(
        "SELECT actor FROM audits WHERE target=? AND action LIKE '报销审批通过%'",
        (f"报销#{rid}",)).fetchall()
    if any(r["actor"] == person["name"] for r in approved_before):
        raise HTTPException(403, "同一人不能审批同一报销单的连续两级（您已审批过本单前级）")

    step_name, next_status = REIMB_FLOW[step]
    comment = (body.get("comment") or "").strip()
    note = f"[第{step}级·{step_name}] {person['name']}：{comment or ('同意' if action == 'approve' else '驳回')}"
    new_comment = (row["comment"] + "\n" if row["comment"] else "") + note
    if action == "approve":
        new_step = step + 1
        conn.execute("UPDATE reimbursements SET status=?, step=?, comment=? WHERE id=?",
                     (next_status, min(new_step, 3), new_comment, rid))
        audit(conn, person["name"], f"报销审批通过({step_name})", f"报销#{rid}",
              f"流转至「{next_status}」；意见：{comment or '同意'}")
    else:
        conn.execute("UPDATE reimbursements SET status='已驳回', comment=? WHERE id=?",
                     (new_comment, rid))
        audit(conn, person["name"], f"报销驳回({step_name})", f"报销#{rid}", comment)
    conn.commit()
    return dict(conn.execute("SELECT * FROM reimbursements WHERE id=?", (rid,)).fetchone())


@router.get("/audits")
def list_audits(action: str = None, limit: int = 100, conn=Depends(db_conn),
                person=Depends(get_current_person)):
    """审计查询：action 精确筛选；limit 默认 100、上限 500"""
    limit = max(1, min(limit, 500))
    sql = "SELECT * FROM audits"
    args = []
    if action:
        sql += " WHERE action=?"
        args.append(action)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]


@router.get("/redlines")
def redlines(person=Depends(get_current_person)):
    return REDLINES
