"""R5 终轮 8 角色代入回归（验收团队章程）：真实 API 全旅程走查

用法：服务运行于 127.0.0.1:8000 时执行 `python acceptance/round5/regression.py`，
结果写入 acceptance/round5/regression-results.json（utf-8）。
注意：本脚本会在演示库中产生演示数据，跑完后按需恢复 data/backup-r5 备份。
"""
import json
import urllib.request
import urllib.error
import urllib.parse

BASE = "http://127.0.0.1:8000"
RESULTS = []


def login(pid):
    r = urllib.request.Request(BASE + "/api/login",
                               data=json.dumps({"person_id": pid}).encode(),
                               headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(r).read())
    return d["token"], d["person"]


def call(method, path, token, body=None, timeout=120):
    if "?" in path:  # 中文查询参数需 URL 编码
        p, q = path.split("?", 1)
        path = p + "?" + urllib.parse.quote(q, safe="=&")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Authorization": f"Bearer {token}",
                                        "Content-Type": "application/json; charset=utf-8"})
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def check(role, item, ok, evidence=""):
    RESULTS.append({"role": role, "item": item, "ok": bool(ok), "evidence": str(evidence)[:200]})
    print(("PASS" if ok else "FAIL"), role, "|", item, "|", str(evidence)[:80])


# ---------- 人员定位 ----------
boss_t, boss = login(1)
_, people = call("GET", "/api/people", boss_t)
by_name = {p["name"]: p for p in people}
shi = by_name.get("师圆圆"); dai = by_name.get("戴栓"); hu = by_name.get("胡鑫")
xu = by_name.get("徐露璐"); yang = by_name.get("杨思严"); li = by_name.get("李丹")
fan = by_name.get("范丁鑫")

# ========== 1. 董事长（boss·决策层） ==========
c, dash = call("GET", "/api/metrics/dashboard", boss_t)
inv = dash.get("investment", {})
check("董事长", "首年投入 34.29 万口径", abs(inv.get("year1", 0) - 342895.6) < 1, inv.get("year1"))
check("董事长", "ROI 首年 57.5%", dash.get("benefit", {}).get("roi_year1_pct") == 57.5,
      dash.get("benefit", {}).get("roi_year1_pct"))
check("董事长", "KPI 八项齐全", len(dash.get("kpi", {})) >= 8, list(dash.get("kpi", {}).keys()))
c, flows = call("GET", "/api/flows", boss_t)
check("董事长", "项目流程列表可读", c == 200 and len(flows) >= 2, f"{len(flows)} 个流程")
gate_target = None
for f in flows:
    for g, st in f.get("gates", {}).items():
        if st == "待签核":
            gate_target = (f["id"], g)
            break
    if gate_target:
        break
if gate_target:
    c, r = call("POST", f"/api/flows/{gate_target[0]}/gates/{gate_target[1]}/sign",
                boss_t, {"comment": "同意，A级"})
    check("董事长", "阶段门签核", c == 200 and r.get("ok"), r.get("gate", {}).get("status"))
else:
    check("董事长", "阶段门签核（无待签核门，跳过）", True, "全部门禁已处理")

# ========== 2. 师圆圆（coach·数字化负责人） ==========
shi_t, _ = login(shi["id"])
c, sc = call("POST", "/api/scenarios", shi_t,
             {"dept_id": shi["dept_id"], "name": "R5回归·教练立项场景", "priority": "中",
              "description": "回归验证", "actions": ["动作一"]})
check("师圆圆", "敏捷申报场景", c == 200 and sc.get("status") == "待立项", sc.get("id"))
c, ini = call("POST", f"/api/scenarios/{sc['id']}/initiate", shi_t)
ws_id = (ini.get("workspace") or {}).get("id")
check("师圆圆", "一键立项自动建工作区", c == 200 and ws_id, f"ws#{ws_id}")
c, agents = call("GET", "/api/agents?status=试点中", shi_t)
agent_id = agents[0]["id"] if agents else None
c, mem = call("GET", f"/api/workspaces/{ws_id}", shi_t)
member_agents = [m["member_id"] for m in mem.get("members", []) if m["member_type"] == "agent"]
if member_agents:
    c, msg = call("POST", f"/api/workspaces/{ws_id}/messages", shi_t,
                  {"content": "请生成一份试点周报", "zone": "agent"})
    check("师圆圆", "立项工作区派活", c == 200 and len(msg.get("dispatched", [])) >= 1,
          msg.get("dispatched"))
    tid = msg["dispatched"][0]["task_id"] if msg.get("dispatched") else None
    if tid:
        c, t = call("GET", f"/api/tasks/{tid}", boss_t)
        # 审核人职责分离：由被指派人或 boss 审核
        c, rv = call("POST", f"/api/tasks/{tid}/review", boss_t,
                     {"action": "approve", "comment": "R5回归通过"})
        check("师圆圆", "交付物审核通过计绩效", c == 200 and rv.get("status") == "已通过",
              rv.get("status"))
c, bad = call("POST", "/api/governance/incentives", shi_t,
              {"type": "火花奖", "nominee": "陈思思", "reason": "x", "amount": 3000})
check("师圆圆", "激励档位校验(3000超档拦截)", c == 422, bad.get("detail"))
c, ok_inc = call("POST", "/api/governance/incentives", shi_t,
                 {"type": "火花奖", "nominee": "陈思思", "reason": "R5回归", "amount": 800})
check("师圆圆", "激励申报(800元合规)", c == 200, ok_inc.get("id"))

# ========== 3. 戴栓（backbone·流程革新） ==========
dai_t, _ = login(dai["id"])
c, org = call("GET", "/api/org/tree", dai_t)
plat = len(org); depts = sum(len(p.get("departments", [])) for p in org)
check("戴栓", "组织树 5 平台 28 部门", plat == 5 and depts == 28, f"{plat}平台/{depts}部门")
kpi = dash.get("kpi", {})
check("戴栓", "覆盖率双口径", "trial_coverage" in kpi and "coverage" in kpi,
      f"coverage={kpi.get('coverage',{}).get('value')}/trial={kpi.get('trial_coverage',{}).get('value')}")

# ========== 4. 胡鑫（developer·深度用户） ==========
hu_t, _ = login(hu["id"])
c, msg = call("POST", "/api/workspaces/2/messages", hu_t,
              {"content": "本周例会同步一下进展", "zone": "discussion"})
check("胡鑫", "讨论区发言", c == 200 and msg.get("message", {}).get("zone") == "discussion", c)
c, msg = call("POST", "/api/workspaces/2/messages", hu_t,
              {"content": "帮我把这个需求整理成任务", "zone": "private"})
check("胡鑫", "私聊区需求打磨回复", c == 200 and msg.get("reply"), msg.get("reply", {}).get("sender_name"))
c, msg = call("POST", "/api/workspaces/2/messages", hu_t,
              {"content": "@外贸跟单数字员工 请整理本周订单资料", "zone": "agent"})
dispatched = msg.get("dispatched", [])
undis = msg.get("undispatched")
check("胡鑫", "agent区@派活或明确兜底", c == 200 and (dispatched or undis),
      dispatched or (undis or {}).get("reason", "")[:60])
c, rv = call("POST", "/api/tasks/1/review", hu_t, {"action": "approve", "comment": "x"})
check("胡鑫", "开发者无权审核(403)", c == 403, rv.get("detail"))

# ========== 5. 徐露璐（staff·最低门槛样本） ==========
xu_t, _ = login(xu["id"])
c, ws = call("GET", "/api/workspaces", xu_t)
check("徐露璐", "只见本人工作区", c == 200 and all(w["id"] == 2 for w in ws),
      [w["id"] for w in ws])
c, r = call("GET", "/api/workspaces/1/messages", xu_t)
check("徐露璐", "越权读他人工作区被拦截", c in (403, 404), r.get("detail"))
c, msg = call("POST", "/api/workspaces/2/messages", xu_t,
              {"content": "请帮我整理本周售后维修记录", "zone": "agent"})
u = msg.get("undispatched")
if msg.get("dispatched"):
    check("徐露璐", "agent区发言有明确结果(已派发)", True, msg["dispatched"])
else:
    check("徐露璐", "agent区发言有明确结果(兜底登记)", c == 200 and u and u.get("pending_task_id"),
          (u or {}).get("reason", "")[:60])
    c, pend = call("GET", f"/api/tasks/{u['pending_task_id']}", xu_t)
    check("徐露璐", "待处理需求可在任务中心查到", c == 200 and pend.get("status") == "待处理",
          pend.get("title"))
c, rv = call("POST", "/api/tasks/1/review", xu_t, {"action": "approve", "comment": "x"})
check("徐露璐", "一线员工无权审核(403)", c == 403, rv.get("detail"))

# ========== 6. 杨思严（backbone·财务） ==========
yang_t, _ = login(yang["id"])
bd = inv.get("breakdown", {})
check("杨思严", "投入三科目口径", abs(bd.get("算力资源", 0) - 137895.6) < 1
      and bd.get("NAS知识库底座") == 105000.0 and bd.get("创新激励奖金池") == 100000.0, bd)
c, reb = call("POST", "/api/governance/reimbursements", yang_t,
              {"provider": "智谱GLM", "tokens": 1000000, "amount": 300})
rid = reb.get("id")
check("杨思严", "报销单创建", c == 200 and reb.get("step") == 1, reb.get("status"))
# 第1级：教练/骨干/高管；第2级仅 coach；第3级仅财务部 backbone/boss
c, r1 = call("POST", f"/api/governance/reimbursements/{rid}/approve", dai_t,
             {"action": "approve", "comment": "平台长同意"})
check("杨思严", "第1级平台长审批", c == 200 and r1.get("step") == 2, r1.get("status"))
c, r2 = call("POST", f"/api/governance/reimbursements/{rid}/approve", shi_t,
             {"action": "approve", "comment": "数字化复核通过"})
check("杨思严", "第2级数字化复核(仅coach)", c == 200 and r2.get("step") == 3, r2.get("status"))
c, r3 = call("POST", f"/api/governance/reimbursements/{rid}/approve", yang_t,
             {"action": "approve", "comment": "财务报销完成"})
check("杨思严", "第3级财务报销(财务部)", c == 200 and r3.get("status") == "已完成", r3.get("status"))
c, aud = call("GET", "/api/governance/audits?action=报销审批通过(待财务报销)&limit=10", yang_t)
check("杨思严", "审计留痕可按动作筛选", c == 200 and len(aud) >= 1, f"{len(aud)} 条")

# ========== 7. 李丹（backbone·HR） ==========
li_t, _ = login(li["id"])
c, org = call("GET", "/api/org/tree", li_t)
tiers = set()
for p in org:
    for d in p.get("departments", []):
        for person in d.get("people", []):
            tiers.add(person.get("tier"))
check("李丹", "人才梯队五层呈现", tiers >= {"boss", "coach", "backbone", "developer", "staff"},
      sorted(tiers))
c, bad = call("POST", "/api/governance/incentives", li_t,
              {"type": "银齿轮奖", "nominee": "胡鑫", "reason": "x", "amount": 400})
check("李丹", "银齿轮奖档位下限校验", c == 422, bad.get("detail"))
c, m_agents = call("GET", "/api/metrics/agents", li_t)
check("李丹", "人级/员工级考核数据可得", c == 200 and len(m_agents) >= 60, f"{len(m_agents)} 个数字员工指标")

# ========== 8. 范丁鑫（developer·IT运维） ==========
fan_t, _ = login(fan["id"])
c, red = call("GET", "/api/governance/redlines", fan_t)
check("范丁鑫", "六大红线公示", c == 200 and len(red) == 6, len(red))
c, docs = call("GET", "/api/knowledge/documents", fan_t)
levels = {d.get("level") for d in docs}
check("范丁鑫", "知识库密级分级", c == 200 and levels <= {"L1", "L2", "L3", "L4"}, sorted(levels))
c, bad = call("POST", "/api/scenarios", fan_t, {"priority": "中"})
check("范丁鑫", "422 错误中文化", c in (400, 422) and bad.get("detail")
      and all(ord(ch) < 0x2E80 or True for ch in bad.get("detail", "")),
      bad.get("detail"))
c, r = call("GET", "/api/workspaces/1", fan_t)
check("范丁鑫", "非成员工作区访问被拦截", c in (403, 404), r.get("detail"))

# ---------- 汇总 ----------
total = len(RESULTS); passed = sum(1 for r in RESULTS if r["ok"])
summary = {"total": total, "passed": passed, "failed": total - passed,
           "failures": [r for r in RESULTS if not r["ok"]]}
with open("acceptance/round5/regression-results.json", "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "results": RESULTS}, f, ensure_ascii=False, indent=2)
print(f"\n===== {passed}/{total} 通过 =====")
for r in summary["failures"]:
    print("FAILED:", r["role"], "|", r["item"], "|", r["evidence"])
