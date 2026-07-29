"""项目流程引擎：承载《AI数智化行动方案 V3》N01-N40 泳道节点 + G1-G4 阶段门

- FLOW_TEMPLATE：40 节点模板常量（不入库，立项实例化时生成 flow_nodes）
- instantiate()：场景立项时创建 project_flow + 40 节点 + 4 门禁记录
- tick()：项目管理智能体自动推进（🤖直接完成 / 🤝生成初稿待确认 / 👤发提醒，门禁不自动处理）
- confirm_node() / sign_gate()：人类动作（确认生效 / 阶段门签核）
- 规则：未过门禁不得进入下一阶段；阶段三无门禁，主链路全完成后自动解锁阶段四
"""
from datetime import datetime, timedelta

from app.engine import _add_message, _now

# (code, stage, 角色, exec_type, 主链路, 门禁, 标题, 产出物)
FLOW_TEMPLATE = [
    # 阶段一·项目启动
    ("N01", 1, "业务部门", "human", 1, None, "提出业务痛点·参与可行性", "需求建议书"),
    ("N02", 1, "项目经理", "agent", 1, None, "编写申请材料·明确目标·识别干系人", "申请表/干系人列表"),
    ("N03", 1, "数字化平台", "agent", 0, None, "技术可行性·工作量预估", "技术评估报告"),
    ("N04", 1, "流程革新部", "agent", 0, None, "审核数字化范围·确认覆盖率基线", "流程清单/基线数据"),
    ("N05", 1, "人力资源部", "agent", 0, None, "编制确认·人力成本评估", "人力配置计划"),
    ("N06", 1, "财务部", "hybrid", 0, None, "审核预算·ROI测算", "预算意见/ROI计算"),
    ("N07", 1, "PMO", "hybrid", 1, None, "立项发起组织·等级评审·组建团队", "立项书/章程/RACI"),
    ("N08", 1, "咨询委/决策层", "human", 1, "G1", "审批立项·确定等级", "立项批复/等级结论"),
    # 阶段二·方案与设计
    ("N09", 2, "业务部门", "hybrid", 1, None, "细化需求·评审方案·确认验收标准", "需求规格/流程清单"),
    ("N10", 2, "数字化平台", "agent", 0, None, "架构设计·技术选型·Skill/接口定义", "架构文档/接口说明"),
    ("N11", 2, "项目经理", "agent", 0, None, "WBS分解·进度表·职责确认", "WBS/甘特图"),
    ("N12", 2, "PMO", "agent", 0, None, "主计划生成·里程碑·预算确认", "计划表/预算表"),
    ("N13", 2, "财务部", "agent", 0, None, "成本核算规则·利润分享基线", "成本方案/分享办法"),
    ("N14", 2, "人力资源部", "agent", 0, None, "人员调配·培训规划", "调拨单/培训计划"),
    ("N15", 2, "流程革新部", "agent", 0, None, "指导流程梳理·优化制度", "流程优化建议"),
    ("N16", 2, "咨询委/决策层", "human", 1, "G2", "评审重大方案·批准预算调整", "评审纪要/预算变更"),
    # 阶段三·开发与测试（本阶段无阶段门）
    ("N17", 3, "业务部门", "hybrid", 1, None, "场景自研开发·功能验收·提供测试数据", "数字员工MVP/UAT反馈"),
    ("N18", 3, "数字化平台", "hybrid", 1, None, "平台支撑·带教答疑·代码审查", "Skill库/审查记录"),
    ("N19", 3, "项目经理", "agent", 0, None, "每日站会·Sprint管理·跨部门协调", "看板/会议纪要"),
    ("N20", 3, "PMO", "agent", 0, None, "进度跟踪·变更管理·风险监控", "周报/风险册/变更单"),
    ("N21", 3, "流程革新部", "agent", 0, None, "跟踪覆盖率·更新指标", "覆盖率周报"),
    ("N22", 3, "财务部", "agent", 0, None, "费用监控·Token报销处理", "费用报表/报销单"),
    ("N23", 3, "人力资源部", "agent", 0, None, "技能培训·团队绩效跟进", "培训记录/绩效跟踪"),
    ("N24", 3, "咨询委/决策层", "hybrid", 0, None, "听取阶段汇报·提供决策", "汇报PPT/决策记录"),
    # 阶段四·试点与验证
    ("N25", 4, "项目经理", "hybrid", 1, None, "试点方案·用户培训·问题迭代", "用户手册/问题台账"),
    ("N26", 4, "数字化平台", "agent", 0, None, "试点部署·缺陷修复·性能调优", "补丁更新/性能报告"),
    ("N27", 4, "PMO", "agent", 0, None, "试点协调·反馈收集·问题闭环", "试点报告/满意度"),
    ("N28", 4, "业务部门", "human", 1, "G3", "配合试点·评估业务效果", "试点评估报告"),
    ("N29", 4, "流程革新部", "agent", 0, None, "评估改进效果·输出最佳实践", "效果报告/案例汇编"),
    ("N30", 4, "财务部", "agent", 0, None, "收益核算·成本偏差审计", "财务绩效报告"),
    ("N31", 4, "人力资源部", "agent", 0, None, "满意度收集·协作评估", "问卷/评估表"),
    ("N32", 4, "咨询委/决策层", "hybrid", 0, None, "关注试点成效·推动资源", "试点简报/资源调度"),
    # 阶段五·结项与移交
    ("N33", 5, "业务部门", "human", 1, None, "确认目标达成·签署验收", "验收确认书/满意度"),
    ("N34", 5, "PMO", "agent", 0, None, "组织验收·输出物清单·移交", "验收表/移交单/结项报告"),
    ("N35", 5, "项目经理", "agent", 0, None, "结项复盘·文档归档·报告撰写", "复盘报告/知识库归档"),
    ("N36", 5, "数字化平台", "agent", 0, None, "源码移交·运维培训·能力复用", "源码/运维手册"),
    ("N37", 5, "流程革新部", "hybrid", 0, None, "纳入管理体系·推广至其他L2/L3", "制度发布/推广方案"),
    ("N38", 5, "财务部", "agent", 0, None, "最终投入产出·奖金结算", "决算表/奖金分配"),
    ("N39", 5, "人力资源部", "human", 0, None, "成果纳入人才盘点·表彰", "档案更新/颁奖记录"),
    ("N40", 5, "咨询委/决策层", "human", 1, "G4", "批准结项·表彰优秀", "结项审批/嘉奖令"),
]

GATE_STAGE = {"G1": 1, "G2": 2, "G3": 4, "G4": 5}   # 阶段三无门禁
STAGE_GATE = {v: k for k, v in GATE_STAGE.items()}
STAGE_NAMES = {1: "项目启动", 2: "方案与设计", 3: "开发与测试", 4: "试点与验证", 5: "结项与移交"}

# 签核权限：G1/G2/G4 仅 boss；G3 允许 boss/coach/backbone
GATE_SIGN_TIERS = {"G1": {"boss"}, "G2": {"boss"}, "G3": {"boss", "coach", "backbone"}, "G4": {"boss"}}
# 节点确认权限（🤝确认生效 / 👤标记完成）
CONFIRM_TIERS = {"boss", "coach", "backbone"}

MAX_TICK_ADVANCE = 2          # 每次 tick 每 flow 最多推进节点数（模拟渐进）
DELAY_DAYS = 3                # 主链路节点滞留预警阈值（天）
# 滞留统计覆盖"进行中"（👤待人工）与"待确认"（🤝待人确认）——两类都是在等人类动作
DELAY_STATUSES = ("进行中", "待确认")

ETYPE_ICON = {"agent": "🤖", "hybrid": "🤝", "human": "👤"}


# ---------------- 基础查询 ----------------

def get_flow(conn, flow_id):
    return conn.execute("SELECT * FROM project_flows WHERE id=?", (flow_id,)).fetchone()


def get_nodes(conn, flow_id):
    return conn.execute("SELECT * FROM flow_nodes WHERE flow_id=? ORDER BY code", (flow_id,)).fetchall()


def get_gates(conn, flow_id):
    return conn.execute("SELECT * FROM gate_records WHERE flow_id=? ORDER BY gate", (flow_id,)).fetchall()


def critical_chain():
    return [t[0] for t in FLOW_TEMPLATE if t[4]]


# ---------------- 实例化 ----------------

def instantiate(conn, scenario_id, workspace_id, name):
    """立项时实例化：flow + 40 节点（阶段一未开始，其余已锁定）+ 4 门禁记录（未开启）"""
    now = _now()
    fid = conn.execute(
        "INSERT INTO project_flows(scenario_id,workspace_id,name,current_stage,status,created_at)"
        " VALUES(?,?,?,1,'进行中',?)", (scenario_id, workspace_id, name, now)).lastrowid
    for code, stage, role, etype, crit, gate, title, outputs in FLOW_TEMPLATE:
        conn.execute(
            "INSERT INTO flow_nodes(flow_id,code,stage,role_name,title,outputs,exec_type,"
            "is_critical,gate_code,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (fid, code, stage, role, title, outputs, etype, crit, gate,
             "未开始" if stage == 1 else "已锁定"))
    for gate, stage in GATE_STAGE.items():
        conn.execute("INSERT INTO gate_records(flow_id,gate,stage,status) VALUES(?,?,?,'未开启')",
                     (fid, gate, stage))
    if workspace_id:
        _add_message(conn, workspace_id, "system", None, "项目管理智能体", "agent", "text",
                     f"项目流程已实例化：40 个节点（🤖agent 24 / 🤝hybrid 9 / 👤human 7）、"
                     f"阶段门 G1-G4 已就位；阶段一「{STAGE_NAMES[1]}」已解锁，主链路 12 个节点构成关键路径。")
    return fid


# ---------------- 阶段推进 ----------------

def _msg(conn, flow, content):
    if flow["workspace_id"]:
        _add_message(conn, flow["workspace_id"], "system", None, "项目管理智能体", "agent", "text", content)


def _check_stage_advance(conn, flow):
    """节点完成后检查两件事：
    1. 有门禁的阶段：除门禁节点外的主链路节点全部完成 → 门禁节点"待签核"、gate_record"待签核"；
    2. 无门禁的阶段（阶段三）：主链路节点全部完成 → 自动解锁下一阶段。
    """
    fid = flow["id"]
    nodes = get_nodes(conn, fid)
    for stage in range(1, 6):
        crit = [n for n in nodes if n["stage"] == stage and n["is_critical"]]
        gate = STAGE_GATE.get(stage)
        if gate:
            gate_node = next(n for n in crit if n["gate_code"] == gate)
            others = [n for n in crit if n["gate_code"] != gate]
            if (all(n["status"] == "已完成" for n in others)
                    and gate_node["status"] not in ("待签核", "已完成")):
                now = _now()
                conn.execute("UPDATE flow_nodes SET status='待签核', started_at=? WHERE id=?",
                             (now, gate_node["id"]))
                conn.execute("UPDATE gate_records SET status='待签核' WHERE flow_id=? AND gate=?",
                             (fid, gate))
                _msg(conn, flow,
                     f"阶段{stage}「{STAGE_NAMES[stage]}」主链路节点全部完成，阶段门 {gate}"
                     f"（{gate_node['code']} {gate_node['title']}）已开启，请咨询委/决策层签核。"
                     f"未过门禁不得进入下一阶段。")
        elif stage < 5:
            # 无门禁阶段：仅当流程正停在该阶段时自动放行下一阶段
            cur = conn.execute("SELECT current_stage FROM project_flows WHERE id=?", (fid,)).fetchone()
            if (cur and cur["current_stage"] == stage
                    and all(n["status"] == "已完成" for n in crit)):
                _unlock_stage(conn, flow, stage + 1,
                              f"阶段{stage}「{STAGE_NAMES[stage]}」主链路节点全部完成（本阶段无阶段门），"
                              f"阶段{stage + 1}「{STAGE_NAMES[stage + 1]}」已自动解锁。")


def _unlock_stage(conn, flow, stage, message):
    conn.execute("UPDATE flow_nodes SET status='未开始' WHERE flow_id=? AND stage=? AND status='已锁定'",
                 (flow["id"], stage))
    conn.execute("UPDATE project_flows SET current_stage=? WHERE id=?", (stage, flow["id"]))
    _msg(conn, flow, message)


# ---------------- 自动推进 tick ----------------

def tick(conn, flow_id):
    """自动推进一轮：按节点顺序处理"未开始"节点（跳过门禁与等待人类的节点），
    每次最多推进 MAX_TICK_ADVANCE 个。返回处理摘要。"""
    flow = get_flow(conn, flow_id)
    if not flow:
        return {"ok": False, "reason": "流程不存在"}
    if flow["status"] != "进行中":
        return {"ok": False, "reason": f"流程状态为「{flow['status']}」，不再推进", "processed": []}

    processed = []
    pending = conn.execute(
        "SELECT * FROM flow_nodes WHERE flow_id=? AND status='未开始' ORDER BY code",
        (flow_id,)).fetchall()
    for node in pending:
        if len(processed) >= MAX_TICK_ADVANCE:
            break
        if node["gate_code"]:
            continue  # 门禁节点不自动处理，须人工签核
        now = _now()
        if node["exec_type"] == "agent":
            conn.execute("UPDATE flow_nodes SET status='已完成', started_at=?, done_at=? WHERE id=?",
                         (now, now, node["id"]))
            _msg(conn, flow,
                 f"项目管理智能体已完成 {node['code']}（{node['title']}），产出：{node['outputs']}。")
        elif node["exec_type"] == "hybrid":
            conn.execute("UPDATE flow_nodes SET status='待确认', started_at=? WHERE id=?",
                         (now, node["id"]))
            _msg(conn, flow,
                 f"AI 已生成 {node['code']} 初稿（{node['outputs']}），请{node['role_name']}确认生效。")
        else:  # human
            conn.execute("UPDATE flow_nodes SET status='进行中', started_at=? WHERE id=?",
                         (now, node["id"]))
            _msg(conn, flow,
                 f"提醒：@{node['role_name']} 节点 {node['code']}（{node['title']}）需人工完成，"
                 f"产出物：{node['outputs']}；完成后请由骨干及以上确认。")
        processed.append({"code": node["code"], "exec_type": node["exec_type"]})
        _check_stage_advance(conn, flow)

    conn.commit()
    return {"ok": True, "flow_id": flow_id, "processed": processed}


# ---------------- 人类动作 ----------------

def confirm_node(conn, flow, code, person, comment=""):
    """🤝节点确认生效 / 👤节点标记完成。返回 (node, error)；调用方负责权限校验与审计。"""
    node = conn.execute("SELECT * FROM flow_nodes WHERE flow_id=? AND code=?",
                        (flow["id"], code)).fetchone()
    if not node:
        return None, (404, "节点不存在")
    if node["gate_code"]:
        return None, (400, f"{code} 是阶段门节点（{node['gate_code']}），请走签核接口")
    if node["status"] == "已完成":
        return None, (400, f"{code} 已完成，无需重复确认")
    expect = "待确认" if node["exec_type"] == "hybrid" else "进行中"
    if node["status"] != expect:
        return None, (400, f"{code} 当前状态为「{node['status']}」，"
                           f"{'需 AI 生成初稿后（待确认）' if node['exec_type'] == 'hybrid' else '需开始（进行中）后'}方可确认")
    now = _now()
    note = f"{person['name']}确认生效" + (f"：{comment}" if comment else "")
    conn.execute("UPDATE flow_nodes SET status='已完成', done_at=?, started_at=COALESCE(started_at,?), note=?"
                 " WHERE id=?", (now, now, note, node["id"]))
    _msg(conn, flow,
         f"{person['name']} 已确认 {code}（{node['title']}）生效，产出：{node['outputs']}。"
         + (f"备注：{comment}" if comment else ""))
    if node["is_critical"]:
        _check_stage_advance(conn, flow)
    conn.commit()
    return conn.execute("SELECT * FROM flow_nodes WHERE id=?", (node["id"],)).fetchone(), None


def sign_gate(conn, flow, gate, person, comment=""):
    """阶段门签核：gate_record→已通过，门禁节点→已完成，解锁下一阶段；G4 通过后结项。
    返回 (gate_record, error)；调用方负责权限校验与审计。"""
    rec = conn.execute("SELECT * FROM gate_records WHERE flow_id=? AND gate=?",
                       (flow["id"], gate)).fetchone()
    if not rec:
        return None, (404, "阶段门不存在")
    if rec["status"] == "已通过":
        return None, (400, f"{gate} 已签核通过，无需重复签核")
    if rec["status"] != "待签核":
        return None, (400, f"{gate} 尚未开启（主链路节点未全部完成），不能签核")

    now = _now()
    stage = GATE_STAGE[gate]
    gate_node = conn.execute("SELECT * FROM flow_nodes WHERE flow_id=? AND gate_code=?",
                             (flow["id"], gate)).fetchone()
    conn.execute("UPDATE gate_records SET status='已通过', signed_by=?, signed_at=?, comment=? WHERE id=?",
                 (person["name"], now, comment, rec["id"]))
    conn.execute("UPDATE flow_nodes SET status='已完成', done_at=?, note=? WHERE id=?",
                 (now, f"{person['name']}签核通过" + (f"：{comment}" if comment else ""), gate_node["id"]))

    if gate == "G4":
        conn.execute("UPDATE project_flows SET status='已结项', closed_at=? WHERE id=?",
                     (now, flow["id"]))
        conn.execute("UPDATE scenarios SET status='已验收' WHERE id=?", (flow["scenario_id"],))
        _msg(conn, flow,
             f"阶段门 G4（{gate_node['code']} {gate_node['title']}）已由 {person['name']} 签核通过"
             + (f"：{comment}" if comment else "")
             + "。项目正式结项，关联场景状态置为「已验收」。")
    else:
        _unlock_stage(conn, flow, stage + 1,
                      f"阶段门 {gate}（{gate_node['code']} {gate_node['title']}）已由 {person['name']} 签核通过"
                      + (f"：{comment}" if comment else "")
                      + f"。阶段{stage + 1}「{STAGE_NAMES[stage + 1]}」已解锁。")
    conn.commit()
    return conn.execute("SELECT * FROM gate_records WHERE id=?", (rec["id"],)).fetchone(), None


# ---------------- 延迟预警 ----------------

def delayed_critical_nodes(conn, flow_id=None):
    """主链路滞留节点：进行中/待确认超过 DELAY_DAYS 天。返回 [{flow_id, code, title, status, days}]"""
    limit = (datetime.now() - timedelta(days=DELAY_DAYS)).isoformat(timespec="seconds")
    sql = ("SELECT n.flow_id, n.code, n.title, n.status, n.started_at, f.name flow_name "
           "FROM flow_nodes n JOIN project_flows f ON f.id=n.flow_id "
           "WHERE n.is_critical=1 AND f.status='进行中' "
           "AND n.status IN ('进行中','待确认') AND n.started_at IS NOT NULL AND n.started_at<=?")
    args = [limit]
    if flow_id:
        sql += " AND n.flow_id=?"
        args.append(flow_id)
    sql += " ORDER BY n.started_at"
    now = datetime.now()
    out = []
    for r in conn.execute(sql, args):
        try:
            days = (now - datetime.fromisoformat(r["started_at"])).days
        except Exception:
            days = DELAY_DAYS
        out.append({"flow_id": r["flow_id"], "flow_name": r["flow_name"], "code": r["code"],
                    "title": r["title"], "status": r["status"], "days": days})
    return out


# ---------------- 视图组装 ----------------

def flow_summary(conn, flow):
    """列表行：flow + 当前阶段进度 + 门禁状态汇总 + 延迟主链路节点数"""
    nodes = get_nodes(conn, flow["id"])
    gates = get_gates(conn, flow["id"])
    cur = flow["current_stage"]
    stage_nodes = [n for n in nodes if n["stage"] == cur]
    stage_done = sum(1 for n in stage_nodes if n["status"] == "已完成")
    total_done = sum(1 for n in nodes if n["status"] == "已完成")
    delayed = delayed_critical_nodes(conn, flow["id"])
    return {
        "id": flow["id"], "scenario_id": flow["scenario_id"], "workspace_id": flow["workspace_id"],
        "name": flow["name"], "status": flow["status"], "current_stage": cur,
        "current_stage_name": STAGE_NAMES.get(cur, ""),
        "created_at": flow["created_at"], "closed_at": flow["closed_at"],
        "stage_progress": round(stage_done / len(stage_nodes) * 100) if stage_nodes else 0,
        "overall_progress": round(total_done / len(nodes) * 100) if nodes else 0,
        "nodes_done": total_done, "nodes_total": len(nodes),
        "gates": {g["gate"]: g["status"] for g in gates},
        "delayed_critical": len(delayed),
        "delayed_nodes": [d["code"] for d in delayed],
    }


def flow_detail(conn, flow):
    d = flow_summary(conn, flow)
    d["nodes"] = [dict(n) for n in get_nodes(conn, flow["id"])]
    d["gate_records"] = [dict(g) for g in get_gates(conn, flow["id"])]
    d["critical_chain"] = critical_chain()
    d["stage_names"] = STAGE_NAMES
    return d
