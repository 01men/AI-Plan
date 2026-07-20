# -*- coding: utf-8 -*-
"""第一轮验收修复回归脚本：逐项验证 15 个修复点（除并发项单独跑 repro_concurrent.py）"""
import json
import urllib.request
import urllib.error
import urllib.parse

BASE = "http://localhost:8000"
PASS, FAIL = [], []


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + urllib.parse.quote(path, safe="/?=&"), data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def check(name, cond, evidence=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}  {evidence}")


def login(pid):
    s, b = req("POST", "/api/login", body={"person_id": pid})
    assert s == 200, (pid, b)
    return b["token"]


boss = login(1)       # 董事长 boss
coach = login(2)      # 李乐平 coach
coach3 = login(3)     # 师圆圆 coach
backbone6 = login(6)  # 戴栓 backbone 流程革新部
finbb = login(9)      # 杨思严 backbone 财务部
dev20 = login(20)     # 胡鑫 developer
staff = login(40)     # 徐露璐 staff

# ---------- A2 待立项场景已绑定数字员工 + initiate 后工作区含员工 ----------
s, scs = req("GET", "/api/scenarios?status=待立项", boss)
check("A2 待立项场景全部绑定 agent_id", all(x["agent_id"] for x in scs),
      f"待立项 {len(scs)} 个，未绑定 {sum(1 for x in scs if not x['agent_id'])} 个")
ok_members = []
for sc in scs[:3]:
    s, r = req("POST", f"/api/scenarios/{sc['id']}/initiate", coach3)
    wid = r["workspace"]["id"]
    s, ws = req("GET", f"/api/workspaces/{wid}", coach3)
    agents_in = [m for m in ws["members"] if m["member_type"] == "agent"]
    ok_members.append(bool(agents_in))
    print(f"    场景#{sc['id']}「{sc['name']}」→ 工作区#{wid} 数字员工成员: {[m['name'] for m in agents_in]}")
check("A2 任选3个待立项场景 initiate 后工作区均含数字员工", all(ok_members))

# ---------- A3 任务中心直建 ----------
s, t1 = req("POST", "/api/tasks", boss, {"title": "直建无员工任务", "requirement": "测试hint"})
check("A3 无 agent_id 创建成功且带 hint", s == 200 and "hint" in t1,
      f"status={s} hint={t1.get('hint','')[:40]}")
s, agents = req("GET", "/api/agents?status=试点中", boss)
aid = agents[0]["id"]
s, t2 = req("POST", "/api/tasks", boss,
            {"title": "直建派给员工任务", "agent_id": aid, "requirement": "整理本周订单并输出明细"})
check("A3 带 agent_id 创建后立即转待审核且有交付物",
      s == 200 and t2["status"] == "待审核" and t2["deliverable"],
      f"status={t2.get('status')} deliverable_len={len(t2.get('deliverable') or '')}")

# ---------- B4 审核权限 ----------
tid = t2["id"]  # creator = 董事长
s, b = req("POST", f"/api/tasks/{tid}/review", staff, {"action": "approve"})
check("B4 staff 审核返回 403", s == 403, f"status={s} {b.get('detail','')}")
s, b = req("POST", f"/api/tasks/{tid}/review", boss, {"action": "approve"})
check("B4 审核自己发起的任务返回 403", s == 403 and "不能审核自己发起的任务" in str(b.get("detail", "")),
      f"status={s} {b.get('detail','')}")
s, b = req("POST", f"/api/tasks/{tid}/review", coach, {"action": "approve", "comment": "符合要求"})
check("B4 coach 审他人任务 200", s == 200 and b["status"] == "已通过", f"status={s} 任务状态={b.get('status')}")

# ---------- B7 驳回重做注入意见+version ----------
s, t3 = req("POST", "/api/tasks", boss, {"title": "驳回重做验证任务", "agent_id": aid,
                                         "workspace_id": 2, "requirement": "生成单证草稿"})
s, b = req("POST", f"/api/tasks/{t3['id']}/review", coach,
           {"action": "reject", "comment": "数据有误，请重做"})
s, t3r = req("GET", f"/api/tasks?workspace_id=2", coach)
t3cur = [x for x in t3r if x["id"] == t3["id"]][0]
has_note = "第 2 版修订说明" in (t3cur["deliverable"] or "") and "数据有误，请重做" in t3cur["deliverable"]
s, msgs = req("GET", "/api/workspaces/2/messages?zone=agent", coach)
dv = [m for m in msgs if m.get("payload") and m["payload"].get("task_id") == t3["id"] and m["msg_type"] == "deliverable"]
ver_ok = dv and dv[-1]["payload"].get("version") == 2
check("B7 重做交付物含驳回意见与版本标识", has_note and ver_ok and t3cur["status"] == "待审核",
      f"修订说明={has_note} version={dv[-1]['payload'].get('version') if dv else None} 状态={t3cur['status']}")

# ---------- B5 报销三级分权 ----------
# 单1：验证各级权限与 comment/audits 留痕（三个不同审批人）
s, rb = req("POST", "/api/governance/reimbursements", dev20,
            {"provider": "智谱GLM", "tokens": 500000, "amount": 150.0})
rid = rb["id"]
s, b = req("POST", f"/api/governance/reimbursements/{rid}/approve", staff, {"action": "approve"})
check("B5 staff 审批第1级返回 403", s == 403, f"status={s}")
s, b = req("POST", f"/api/governance/reimbursements/{rid}/approve", backbone6,
           {"action": "approve", "comment": "平台长同意"})
check("B5 backbone 审批第1级 200", s == 200 and b["status"] == "待数字化复核", f"status={s} → {b.get('status')}")
s, b = req("POST", f"/api/governance/reimbursements/{rid}/approve", backbone6, {"action": "approve"})
check("B5 非coach审批第2级返回 403", s == 403, f"status={s} {b.get('detail','')}")
s, b = req("POST", f"/api/governance/reimbursements/{rid}/approve", coach,
           {"action": "approve", "comment": "数字化复核通过"})
check("B5 coach 审批第2级 200", s == 200 and b["status"] == "待财务报销", f"status={s} → {b.get('status')}")
s, b = req("POST", f"/api/governance/reimbursements/{rid}/approve", backbone6, {"action": "approve"})
check("B5 非财务部backbone审批第3级返回 403", s == 403, f"status={s} {b.get('detail','')}")
s, b = req("POST", f"/api/governance/reimbursements/{rid}/approve", finbb,
           {"action": "approve", "comment": "财务已打款"})
check("B5 财务部backbone审批第3级 200 且 comment 留痕",
      s == 200 and b["status"] == "已完成" and "第1级" in (b.get("comment") or "") and "财务已打款" in b["comment"],
      f"status={s} 状态={b.get('status')} comment行数={len((b.get('comment') or '').splitlines())}")
s, audits = req("GET", "/api/governance/audits", boss)
check("B5 审批均写 audits", sum(1 for a in audits if a["target"] == f"报销#{rid}" and "报销审批通过" in a["action"]) == 3,
      f"该单通过类审计 {sum(1 for a in audits if a['target'] == f'报销#{rid}' and '通过' in a['action'])} 条")
# 单2：同一人不能审批连续两级
s, rb2 = req("POST", "/api/governance/reimbursements", dev20,
             {"provider": "百度文心", "tokens": 300000, "amount": 90.0})
rid2 = rb2["id"]
s, b = req("POST", f"/api/governance/reimbursements/{rid2}/approve", coach, {"action": "approve"})
check("B5 coach 审批单2第1级 200", s == 200, f"status={s}")
s, b = req("POST", f"/api/governance/reimbursements/{rid2}/approve", coach, {"action": "approve"})
check("B5 同一人连批两级返回 403", s == 403 and "同一人不能审批" in str(b.get("detail", "")),
      f"status={s} {b.get('detail','')}")

# ---------- B6 agents PATCH 枚举+权限 ----------
s, b = req("PATCH", f"/api/agents/{aid}", coach, {"status": "飞"})
check("B6 PATCH status=飞 返回 422 中文", s == 422 and "status 仅允许" in str(b.get("detail", "")),
      f"status={s} {b.get('detail','')}")
s, b = req("PATCH", f"/api/agents/{aid}", staff, {"status": "试运行"})
check("B6 staff PATCH 返回 403", s == 403, f"status={s}")
s, agent22 = req("GET", "/api/agents", dev20)  # 胡鑫名下第一个：外贸销售数字员工
own = [a for a in agent22 if a.get("owner_name") == "胡鑫"]
s, b = req("PATCH", f"/api/agents/{own[0]['id']}", dev20, {"description": "owner本人更新"})
check("B6 owner 本人 PATCH 200", s == 200 and b["description"] == "owner本人更新", f"status={s}")
s, b = req("PATCH", f"/api/agents/{aid}", coach, {"status": "试运行"})
check("B6 coach PATCH 合法状态 200", s == 200 and b["status"] == "试运行", f"status={s} → {b.get('status')}")
req("PATCH", f"/api/agents/{aid}", coach, {"status": "已下线"})  # 恢复避免影响后续（试点中不在允许枚举内，改已下线不影响指标）

# ---------- B8/B9 dashboard ----------
s, dash = req("GET", "/api/metrics/dashboard", boss)
bd = dash["investment"]["breakdown"]
check("B8 投入构成三科目金额",
      bd.get("算力资源") == 137895.6 and bd.get("NAS知识库底座") == 105000.0 and bd.get("创新激励奖金池") == 100000.0
      and dash["investment"]["year1"] == 342895.6,
      f"breakdown={bd} year1={dash['investment']['year1']}")
check("B8 明细与 ROI 字段",
      dash["investment"]["breakdown_detail"]["算力资源"]["智谱团队套餐"] == 84045.6
      and dash["benefit"]["roi_year1_pct"] == 57.5 and dash["benefit"]["roi_year2_pct"] == 117.8,
      f"roi={dash['benefit'].get('roi_year1_pct')}/{dash['benefit'].get('roi_year2_pct')}")
kpi = dash["kpi"]
notes_ok = all(isinstance(v, dict) and "note" in v and "value" in v for v in kpi.values())
check("B9 coverage 方案口径=0 且 trial_coverage 保留 6.2",
      kpi["coverage"]["value"] == 0 and kpi["trial_coverage"]["value"] == 6.2,
      f"coverage={kpi['coverage']} trial={kpi['trial_coverage']}")
check("B9 每个 kpi 项均带 note", notes_ok, f"keys={list(kpi.keys())}")

# ---------- C11 私聊区回复 ----------
s, b = req("POST", "/api/workspaces/1/messages", boss,
           {"zone": "private", "content": "帮我整理一下外贸订单的周报表"})
reply = b.get("reply") or {}
check("C11 私聊区收到项目管理智能体打磨回复",
      s == 200 and reply.get("sender_type") == "agent" and reply.get("msg_type") == "text"
      and "需求打磨草稿" in reply.get("content", "") and "外贸跟单数字员工" in reply.get("content", ""),
      f"sender={reply.get('sender_name')} 长度={len(reply.get('content',''))}")

# ---------- C12 心跳去重 ----------
s, h1 = req("POST", "/api/heartbeat/run", boss)
s, h2 = req("POST", "/api/heartbeat/run", boss)
check("C12 连续两次心跳第二次 skipped",
      h1.get("ok") and not h1.get("skipped") and h2.get("skipped") is True,
      f"第一次 skipped={h1.get('skipped')} 第二次 skipped={h2.get('skipped')}")

# ---------- C13 激励金额档位 ----------
s, b = req("POST", "/api/governance/incentives", coach3,
           {"type": "火花奖", "nominee": "测试人", "amount": 3000, "reason": "超额测试"})
check("C13 火花奖 3000 超档返回 422 中文", s == 422 and "500-2000" in str(b.get("detail", "")),
      f"status={s} {b.get('detail','')}")
s, b = req("POST", "/api/governance/incentives", coach3,
           {"type": "火花奖", "nominee": "测试人", "amount": 1000, "reason": "合规测试"})
check("C13 火花奖 1000 申报 200", s == 200 and b["status"] == "申报中", f"status={s}")
s, audits = req("GET", "/api/governance/audits", boss)
check("C13 申报写 audits", any(a["action"] == "激励申报" and a["target"] == "测试人" for a in audits))

# ---------- C14 知识空间命名 + L4 ----------
s, spaces = req("GET", "/api/knowledge/spaces", boss)
names = [x["name"] for x in spaces]
check("C14 空间命名为平台名格式",
      "产品营销平台空间" in names and "营销客户空间" not in names and "研发平台空间" in names,
      f"spaces={names}")
s, docs = req("GET", "/api/knowledge/documents?level=L4", boss)
check("C14 存在 L4 示例文档", len(docs) >= 2, f"L4 文档 {[d['title'] for d in docs]}")

# ---------- C15 种子激励评定留痕 ----------
s, audits = req("GET", "/api/governance/audits", boss)
seed_inc = [a for a in audits if a["action"] == "激励评定"]
check("C15 种子激励已补 audits", len(seed_inc) >= 3,
      f"{[(a['actor'], a['target']) for a in seed_inc]}")

print("\n==== 汇总 ====")
print(f"PASS {len(PASS)} / FAIL {len(FAIL)}")
if FAIL:
    print("失败项:", FAIL)
