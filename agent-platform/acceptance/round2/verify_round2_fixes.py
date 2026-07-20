# -*- coding: utf-8 -*-
"""第二轮修复验证脚本：逐项实测 5 个修复点并输出证据摘录"""
import json
import urllib.request
import urllib.error
import urllib.parse

BASE = "http://localhost:8000"


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + urllib.parse.quote(path, safe="/?=&"),
                               data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def login(pid):
    s, b = req("POST", "/api/login", body={"person_id": pid})
    assert s == 200, (pid, b)
    return b["token"], b["person"]["name"]


print("=" * 70)
print("验证1：审核人指派（胡鑫派活 → reviewer 非本人且为 coach/backbone → 可审）")
print("=" * 70)
huxin, _ = login(20)
s, b = req("POST", "/api/workspaces/2/messages", huxin,
           {"zone": "agent", "content": "@外贸跟单数字员工 请整理本周外贸订单并输出明细清单"})
print(f"POST /api/workspaces/2/messages → {s}")
tid = b["dispatched"][0]["task_id"]
print(f"  dispatched: {b['dispatched']}")
s, tasks = req("GET", f"/api/tasks?workspace_id=2", huxin)
task = [t for t in tasks if t["id"] == tid][0]
print(f"  任务#{tid}: status={task['status']} creator_id={task['creator_id']} "
      f"reviewer_id={task['reviewer_id']} reviewer_name={task['reviewer_name']}")
assert task["reviewer_id"] != 20, "reviewer 仍是创建人本人！"
s, people_ok = req("GET", "/api/people", huxin)
rev = [p for p in people_ok if p["id"] == task["reviewer_id"]]
rev_tier = rev[0]["tier"] if rev else "?"
print(f"  reviewer tier={rev_tier} name={rev[0]['name'] if rev else '?'}")
assert rev_tier in ("coach", "backbone"), "reviewer 不是 coach/backbone！"
rev_tok, rev_name = login(task["reviewer_id"])
s, b = req("POST", f"/api/tasks/{tid}/review", rev_tok,
           {"action": "approve", "comment": "第二轮验收复核：通过"})
print(f"POST /api/tasks/{tid}/review ({rev_name}) → {s} status={b.get('status')}")
assert s == 200 and b["status"] == "已通过"
print("验证1 PASS")

print()
print("=" * 70)
print("验证2：激励类型校验（钻石奖 / 带空格 均被 422 拦截；合法类型放行）")
print("=" * 70)
coach, _ = login(2)
for t in ("钻石奖", "火花奖 ", " 火花奖"):
    s, b = req("POST", "/api/governance/incentives", coach,
               {"type": t, "nominee": "测试拦截", "amount": 100})
    print(f"POST incentives type={t!r} → {s} detail={b.get('detail')}")
    assert s == 422 and b.get("detail") == "奖项类型仅允许：火花奖/银齿轮奖/金扳手奖/种子基金"
s, b = req("POST", "/api/governance/incentives", coach,
           {"type": "种子基金", "nominee": "验证用例", "amount": 0, "reason": "类型放行验证"})
print(f"POST incentives type='种子基金' → {s} id={b.get('id')} status={b.get('status')}")
assert s == 200
print("验证2 PASS")

print()
print("=" * 70)
print("验证3：登录不再写审计 + audits action/limit 筛选")
print("=" * 70)
for pid in (1, 2, 3):
    login(pid)
s, audits = req("GET", "/api/governance/audits", coach)
logins = [a for a in audits if a["action"] == "登录"]
print(f"连续登录 3 次后 GET /api/governance/audits：总条数={len(audits)} 登录记录={len(logins)}")
assert not logins
s, inc = req("GET", "/api/governance/audits?action=激励评定", coach)
print(f"GET /api/governance/audits?action=激励评定 → {s} 条数={len(inc)}")
for a in inc:
    print(f"  #{a['id']} {a['actor']} {a['action']} {a['target']} | {a['detail']}")
assert len(inc) == 3
s, lim = req("GET", "/api/governance/audits?limit=5", coach)
print(f"GET /api/governance/audits?limit=5 → {s} 条数={len(lim)}")
assert len(lim) == 5
s, cap = req("GET", "/api/governance/audits?limit=9999", coach)
print(f"GET /api/governance/audits?limit=9999 → {s} 条数={len(cap)}（上限500封顶）")
assert len(cap) <= 500
print("验证3 PASS")

print()
print("=" * 70)
print("验证4：dashboard.latest_report")
print("=" * 70)
s, dash = req("GET", "/api/metrics/dashboard", coach)
lr = dash.get("latest_report")
print(f"GET /api/metrics/dashboard → {s}")
print(f"  latest_report keys: {sorted(lr.keys()) if lr else None}")
print(f"  workspace_id={lr['workspace_id']} workspace_name={lr['workspace_name']}")
print(f"  sender={lr['sender_name']} created_at={lr['created_at']}")
print(f"  content 首行: {lr['content'].splitlines()[0]}")
assert lr and all(k in lr for k in ("workspace_id", "workspace_name", "content", "created_at"))
print("验证4 PASS")

print()
print("=" * 70)
print("验证5：私聊推荐优先在区成员 agent")
print("=" * 70)
# 工作区2 成员 agent = 外贸跟单数字员工；发一个不含关键词的需求，应推荐在区员工而非按关键词外推
s, b = req("POST", "/api/workspaces/2/messages", huxin,
           {"zone": "private", "content": "帮我把这堆客户邮件整理成一份周报"})
reply = b.get("reply") or {}
sec = [l for l in reply.get("content", "").splitlines() if "建议" in l]
print("工作区2 私聊（无关键词需求）:")
for l in sec:
    print("  " + l.strip())
assert "外贸跟单数字员工" in reply["content"], "未推荐在区成员员工"
# 工作区1 只有项目管理智能体（自身），应回退关键词匹配
boss_tok, _ = login(1)
s, b = req("POST", "/api/workspaces/1/messages", boss_tok,
           {"zone": "private", "content": "帮我整理一下外贸订单的周报表"})
reply2 = b.get("reply") or {}
sec2 = [l for l in reply2.get("content", "").splitlines() if "建议" in l]
print("工作区1 私聊（外贸关键词、区内无其他员工）:")
for l in sec2:
    print("  " + l.strip())
assert "外贸跟单数字员工" in reply2["content"]
print("验证5 PASS")

print()
print("==== 全部 5 项验证 PASS ====")
