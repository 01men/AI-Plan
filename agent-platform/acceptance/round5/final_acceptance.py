"""R5 终验：对正在运行的服务执行多角色、关键闭环与安全边界验收。"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
passed = []
failed = []


def request(method, path, token=None, body=None, raw=False):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + urllib.parse.quote(path, safe="/?=&:%"),
        data=data, method=method, headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload, dict(resp.headers)
            return resp.status, json.loads(payload.decode("utf-8")), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            result = json.loads(payload.decode("utf-8"))
        except Exception:
            result = {"raw": payload.decode("utf-8", "replace")}
        return exc.code, result, dict(exc.headers)


def check(name, condition, evidence=""):
    (passed if condition else failed).append(name)
    print(f"[{'PASS' if condition else 'FAIL'}] {name}"
          + (f" | {evidence}" if evidence else ""))


def login(person_id):
    status, data, _ = request("POST", "/api/login", body={"person_id": person_id})
    if status != 200:
        raise RuntimeError(f"登录 {person_id} 失败：{status} {data}")
    return data["token"], data["person"]


status, health, headers = request("GET", "/api/health")
check("健康探针与安全响应头", status == 200 and health.get("version") == "1.5.0"
      and headers.get("x-content-type-options") == "nosniff", str(health))

boss, boss_person = login(1)
coach, _ = login(2)
backbone, _ = login(6)
developer, _ = login(20)
staff, staff_person = login(40)
check("五层业务角色可进入", all((boss, coach, backbone, developer, staff)))

status, _, _ = request("POST", "/api/login", body={})
check("422 全中文提示", status == 422, f"status={status}")

_, boss_ws, _ = request("GET", "/api/workspaces", boss)
_, staff_ws, _ = request("GET", "/api/workspaces", staff)
staff_ids = {w["id"] for w in staff_ws}
foreign = next((w["id"] for w in boss_ws if w["id"] not in staff_ids), None)
status, _, _ = request("GET", f"/api/workspaces/{foreign}", staff)
check("普通员工工作区最小权限", len(staff_ws) < len(boss_ws) and status == 404,
      f"staff={len(staff_ws)} boss={len(boss_ws)} foreign={status}")
status, _, _ = request("GET", f"/api/workspaces/{foreign}/messages", staff)
check("跨工作区消息不可读取", status == 404, f"status={status}")

status, scenarios, _ = request("GET", "/api/scenarios", boss)
reserve = sum(1 for item in scenarios if item.get("batch") == "规划储备")
check("方案 232 场景容量承载", status == 200 and len(scenarios) >= 232 and reserve >= 151,
      f"total={len(scenarios)} reserve={reserve}")

_, agents, _ = request("GET", "/api/agents", developer)
agent = next(a for a in agents if a["status"] != "已下线")
status, task, _ = request("POST", "/api/tasks", developer, {
    "title": "R5终验·一线需求闭环",
    "agent_id": agent["id"],
    "priority": "中",
    "requirement": "请生成三条可执行的明日交付验收准备事项，使用简明中文。",
})
check("开发者派活并生成待审交付", status == 200 and task.get("status") == "待审核"
      and bool(task.get("deliverable")),
      f"task={task.get('id')} mode={task.get('execution_mode')} model={task.get('model_provider')}")
task_id = task["id"]
status, _, _ = request("POST", f"/api/tasks/{task_id}/review", staff,
                       {"action": "approve", "comment": "越权验证"})
check("普通员工不可审核", status in (403, 404), f"status={status}")
reviewer_id = task["reviewer_id"]
reviewer, reviewer_person = login(reviewer_id)
status, approved_task, _ = request(
    "POST", f"/api/tasks/{task_id}/review", reviewer,
    {"action": "approve", "comment": "终验通过"},
)
check("指派审核人完成闭环", status == 200 and approved_task.get("status") == "已通过",
      f"reviewer={reviewer_person['name']}")

status, _, _ = request("GET", "/api/metrics/people", staff)
manager_status, people_metrics, _ = request("GET", "/api/metrics/people", backbone)
check("HR 人级成效按角色开放", status == 403 and manager_status == 200
      and len(people_metrics) >= 48, f"staff={status} manager_rows={len(people_metrics)}")

status, model_views, _ = request("GET", "/api/models", staff)
admin_status, admin_models, _ = request("GET", "/api/models", boss)
check("模型配置普通员工脱敏", status == 200 and admin_status == 200
      and all("base_url" not in item for item in model_views)
      and any(item["api_key"] == "已配置" for item in admin_models))

for provider in ("kimi", "qwen"):
    item = next((x for x in admin_models if x["key"] == provider and x["api_key"] == "已配置"), None)
    if item:
        test_status, test_result, _ = request("POST", f"/api/models/{provider}/test", boss)
        check(f"{provider} 真实模型连通", test_status == 200 and test_result.get("ok"),
              json.dumps(test_result, ensure_ascii=False))

status, public_providers, _ = request("GET", "/api/auth/providers/public")
ding = next((x for x in public_providers if x["provider"] == "dingtalk"), {})
if ding.get("configured"):
    url_status, login_url, _ = request("GET", "/api/auth/oauth/dingtalk/login-url")
    qr_path = "/api/auth/oauth/qr?data=" + urllib.parse.quote(login_url.get("url", ""), safe="")
    qr_status, qr_data, qr_headers = request("GET", qr_path, raw=True)
    check("钉钉真实登录 URL 与同源二维码", url_status == 200 and qr_status == 200
          and qr_headers.get("content-type", "").startswith("image/png")
          and qr_data.startswith(b"\x89PNG"), f"url={url_status} qr={qr_status}")
else:
    check("钉钉真实登录 URL 与同源二维码", False, "钉钉配置未启用")

status, incentive, _ = request("POST", "/api/governance/incentives", staff, {
    "type": "火花奖", "nominee": staff_person["name"],
    "amount": 500, "reason": "R5普通员工闭环验收",
})
status2, assessed, _ = request(
    "POST", f"/api/governance/incentives/{incentive.get('id')}/review",
    coach, {"action": "approve", "comment": "证据完整"},
)
status3, released, _ = request(
    "POST", f"/api/governance/incentives/{incentive.get('id')}/review",
    boss, {"action": "release", "comment": "确认发放"},
)
check("激励申报评定发放闭环", status == status2 == status3 == 200
      and released.get("status") == "已发放")

status, reimb, _ = request("POST", "/api/governance/reimbursements", staff, {
    "provider": "终验模型", "tokens": 1000, "amount": 1,
})
status1, r1, _ = request("POST", f"/api/governance/reimbursements/{reimb.get('id')}/approve",
                         backbone, {"action": "approve", "comment": "平台长通过"})
status2, r2, _ = request("POST", f"/api/governance/reimbursements/{reimb.get('id')}/approve",
                         coach, {"action": "approve", "comment": "数字化复核通过"})
status3, r3, _ = request("POST", f"/api/governance/reimbursements/{reimb.get('id')}/approve",
                         boss, {"action": "approve", "comment": "财务完成"})
check("算力报销三级分权闭环", status == status1 == status2 == status3 == 200
      and r3.get("status") == "已完成", f"final={r3.get('status')}")

export_status, csv_data, export_headers = request(
    "GET", "/api/governance/audits/export", boss, raw=True)
staff_export, _, _ = request("GET", "/api/governance/audits/export", staff, raw=True)
check("审计导出与权限", export_status == 200 and staff_export == 403
      and csv_data.startswith(b"\xef\xbb\xbf"), f"rows_bytes={len(csv_data)}")

for asset in ("/static/vendor/tailwind.js", "/static/vendor/echarts.min.js",
              "/static/vendor/qrcode.min.js"):
    asset_status, payload, _ = request("GET", asset, raw=True)
    check(f"离线静态依赖 {asset.rsplit('/', 1)[-1]}", asset_status == 200 and len(payload) > 100)

temp_token, _ = login(40)
logout_status, _, _ = request("POST", "/api/logout", temp_token)
me_status, _, _ = request("GET", "/api/me", temp_token)
check("退出后会话立即撤销", logout_status == 200 and me_status == 401)

print(f"\nRESULT: {len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILED:", ", ".join(failed))
    sys.exit(1)
