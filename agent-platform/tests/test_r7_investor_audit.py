"""R7 投资人尽调回归：报销三级分权 / 密级守卫 / 阶段门签核 / 任务防伪 /
私聊隔离 / HTML XSS 清洗 / 外部事件按任务幂等 / task_id LIKE 防前缀碰撞 /
发言校验顺序与长度上限。"""
import json
import sqlite3
import unittest

from fastapi import HTTPException

from app import engine
from app.access import can_access_document
from app.database import init_db
from app.routers.flows import sign_gate
from app.routers.governance import approve_reimbursement, create_reimbursement
from app.routers.knowledge import _clean_html
from app.routers.tasks import (_latest_deliverable_is_external, create_task,
                               external_event, review_task)
from app.routers.workspaces import list_messages, post_message
from app.seed import run_flow_seed, run_r4_seed, run_r5_seed, run_seed


class R7Base(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        run_r4_seed(self.conn)
        run_r5_seed(self.conn)
        run_flow_seed(self.conn)
        self.boss = dict(self.conn.execute(
            "SELECT * FROM people WHERE tier='boss' LIMIT 1").fetchone())
        self.coaches = [dict(r) for r in self.conn.execute(
            "SELECT * FROM people WHERE tier='coach' ORDER BY id LIMIT 2")]
        self.backbone = dict(self.conn.execute(
            "SELECT * FROM people WHERE tier='backbone' LIMIT 1").fetchone())
        self.developer = dict(self.conn.execute(
            "SELECT * FROM people WHERE id=20").fetchone())
        self.staff = dict(self.conn.execute(
            "SELECT * FROM people WHERE id=40").fetchone())  # 徐露璐

    def tearDown(self):
        self.conn.close()

    def assert_http(self, status, fn, *args):
        with self.assertRaises(HTTPException) as ctx:
            fn(*args)
        self.assertEqual(status, ctx.exception.status_code)

    def member_ws(self, pid):
        row = self.conn.execute(
            "SELECT workspace_id FROM workspace_members "
            "WHERE member_type='human' AND member_id=? LIMIT 1", (pid,)).fetchone()
        return row["workspace_id"] if row else None

    def staff_ws(self):
        return self.member_ws(self.staff["id"])


class ReimbursementSeparationTests(R7Base):
    def test_three_level_separation_of_duties(self):
        r = create_reimbursement(
            {"amount": 100, "tokens": 1000, "provider": "qwen"},
            self.conn, self.developer)
        self.assertEqual("待平台长审批", r["status"])
        rid = r["id"]
        # 第 1 级：staff 越权 403；coach 通过
        self.assert_http(403, approve_reimbursement,
                         rid, {"action": "approve"}, self.conn, self.staff)
        r = approve_reimbursement(rid, {"action": "approve"}, self.conn, self.coaches[0])
        self.assertEqual("待数字化复核", r["status"])
        # 第 2 级：同一人连审两级 403；boss 越权（仅 coach）403；另一 coach 通过
        self.assert_http(403, approve_reimbursement,
                         rid, {"action": "approve"}, self.conn, self.coaches[0])
        self.assert_http(403, approve_reimbursement,
                         rid, {"action": "approve"}, self.conn, self.boss)
        r = approve_reimbursement(rid, {"action": "approve"}, self.conn, self.coaches[1])
        self.assertEqual("待财务报销", r["status"])
        # 第 3 级：developer / 非财务 backbone 403；boss 通过至已完成
        self.assert_http(403, approve_reimbursement,
                         rid, {"action": "approve"}, self.conn, self.developer)
        self.assert_http(403, approve_reimbursement,
                         rid, {"action": "approve"}, self.conn, self.backbone)
        r = approve_reimbursement(rid, {"action": "approve"}, self.conn, self.boss)
        self.assertEqual("已完成", r["status"])
        # 终结后不可再审批
        self.assert_http(400, approve_reimbursement,
                         rid, {"action": "approve"}, self.conn, self.boss)


class KnowledgeClearanceTests(R7Base):
    def test_clearance_matrix(self):
        self.assertTrue(can_access_document(self.staff, "L1", "任何部门"))
        self.assertTrue(can_access_document(self.staff, "L2", None))
        # staff 非同部门 L3/L4 一律不可见
        self.assertFalse(can_access_document(self.staff, "L3", "财务部"))
        self.assertFalse(can_access_document(self.staff, "L4", self.staff.get("dept_name")))
        # 管理层全域可见
        self.assertTrue(can_access_document(self.boss, "L4", "财务部"))
        self.assertTrue(can_access_document(self.coaches[0], "L3", "国际销售部"))

    def test_html_upload_sanitizer_blocks_xss_vectors(self):
        for vector in (
                '<p onclick="steal()">正文</p>',
                '<a href="javascript:alert(1)">链接</a>',
                '<svg onload="alert(1)"></svg>',
                '<iframe src="https://evil.example"></iframe>',
                '<img src="x" onerror="alert(1)">',
        ):
            cleaned = _clean_html(vector).lower()
            for token in ("onclick", "javascript:", "onload", "<iframe", "onerror"):
                self.assertNotIn(token, cleaned, f"清洗后仍含 {token}: {cleaned}")
        # 正常内容保留
        self.assertIn("正文", _clean_html("<p>正文</p>"))


class GateSignTests(R7Base):
    def test_g1_sign_is_boss_only(self):
        row = self.conn.execute(
            "SELECT flow_id FROM gate_records WHERE gate='G1' "
            "AND (signed_by IS NULL OR signed_by='') LIMIT 1").fetchone()
        self.assertIsNotNone(row, "种子数据应提供一个待签核的 G1 阶段门")
        fid = row["flow_id"]
        self.assert_http(403, sign_gate, fid, "G1", {"comment": "越权"},
                         self.conn, self.coaches[0])
        self.assert_http(403, sign_gate, fid, "G1", {}, self.conn, self.staff)
        sign_gate(fid, "G1", {"comment": "同意立项"}, self.conn, self.boss)
        rec = self.conn.execute(
            "SELECT signed_by FROM gate_records WHERE flow_id=? AND gate='G1'",
            (fid,)).fetchone()
        self.assertEqual(self.boss["name"], rec["signed_by"])


class TaskForgeGuardTests(R7Base):
    def test_client_cannot_forge_status_priority_reviewer(self):
        # status 强制「待处理」，客户端传入被忽略
        t = create_task({"title": "伪造状态任务", "status": "已通过"},
                        self.conn, self.developer)
        self.assertEqual("待处理", t["status"])
        # 非法 priority 422
        self.assert_http(422, create_task,
                         {"title": "非法优先级", "priority": "超高"},
                         self.conn, self.developer)
        # 不存在的 reviewer_id 422
        self.assert_http(422, create_task,
                         {"title": "幽灵审核人", "reviewer_id": 99999},
                         self.conn, self.developer)

    def test_double_approve_rejected(self):
        t = create_task({"title": "防重审核任务"}, self.conn, self.developer)
        tid = t["id"]
        self.conn.execute("UPDATE tasks SET status='待审核' WHERE id=?", (tid,))
        self.conn.commit()
        review_task(tid, {"action": "approve"}, self.conn, self.boss)
        # 第二次审核（并发/重放）必须被拒，绩效不得重复累计；
        # 用 boss 重试以越过 reviewer 指派校验、直击状态防线
        with self.assertRaises(HTTPException) as ctx:
            review_task(tid, {"action": "approve"}, self.conn, self.boss)
        self.assertIn(ctx.exception.status_code, (400, 409))


class PrivateChatIsolationTests(R7Base):
    def test_private_zone_only_visible_to_owner(self):
        wid = self.staff_ws()
        post_message(wid, {"content": "我的私聊草稿", "zone": "private"},
                     self.conn, self.staff)
        mine = list_messages(wid, zone="private", conn=self.conn, person=self.staff)
        self.assertTrue(any("私聊草稿" in m["content"] for m in mine),
                        "本人应能看到自己的私聊")
        others = list_messages(wid, zone="private", conn=self.conn, person=self.boss)
        self.assertFalse(any("私聊草稿" in m["content"] for m in others),
                         "他人（含管理层）不应看到非本人私聊")


    def test_chat_history_recall_respects_private_owner(self):
        wid = self.staff_ws()
        post_message(wid, {"content": "召回隔离验证草稿", "zone": "private"},
                     self.conn, self.staff)
        own = engine._chat_history(self.conn, wid, None, person_id=self.staff["id"])
        self.assertTrue(any("召回隔离验证草稿" in m["content"] for m in own))
        other = engine._chat_history(self.conn, wid, None, person_id=self.boss["id"])
        self.assertFalse(any("召回隔离验证草稿" in m["content"] for m in other),
                         "他人私聊不得进入模型对话上下文")


class ExternalEventIdempotencyTests(R7Base):
    def test_idempotency_scoped_per_task(self):
        t1 = create_task({"title": "外部任务一"}, self.conn, self.developer)
        t2 = create_task({"title": "外部任务二"}, self.conn, self.developer)
        ev = {"event_type": "progress", "event_id": "ev-1", "source": "multica"}
        first = external_event(t1["id"], ev, self.conn, self.boss)
        self.assertFalse(first["idempotent"])
        # 同任务重放 → 幂等
        replay = external_event(t1["id"], ev, self.conn, self.boss)
        self.assertTrue(replay["idempotent"])
        # 同 source+event_id 用于另一任务 → 不得误吞
        other = external_event(t2["id"], ev, self.conn, self.boss)
        self.assertFalse(other["idempotent"])

    def test_task_id_like_no_prefix_collision(self):
        wid = self.member_ws(self.developer["id"])
        t = create_task({"title": "防碰撞任务", "workspace_id": wid},
                        self.conn, self.developer)
        tid = t["id"]
        # 工作区里只有 task_id 为本任务 id 十倍的外部交付物
        engine._add_message(self.conn, wid, "agent", None, "外部运行时", "agent",
                            "deliverable", "他任务交付物",
                            {"task_id": tid * 10, "runtime": "external"})
        self.conn.commit()
        task_row = dict(self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
        self.assertFalse(_latest_deliverable_is_external(self.conn, task_row),
                         f"task#{tid} 不应误匹配 task#{tid * 10} 的交付物")
        # 正向对照：本任务的外部交付物能被识别
        engine._add_message(self.conn, wid, "agent", None, "外部运行时", "agent",
                            "deliverable", "本任务交付物",
                            {"task_id": tid, "runtime": "external"})
        self.conn.commit()
        self.assertTrue(_latest_deliverable_is_external(self.conn, task_row))


class PostMessageValidationTests(R7Base):
    def test_invalid_target_agent_rejected_before_insert(self):
        wid = self.staff_ws()
        before = self.conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE workspace_id=?", (wid,)).fetchone()["c"]
        self.assert_http(422, post_message, wid,
                         {"content": "调用不存在的员工", "zone": "agent",
                          "target_agent_id": 99999},
                         self.conn, self.staff)
        after = self.conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE workspace_id=?", (wid,)).fetchone()["c"]
        self.assertEqual(before, after, "校验失败的消息不得落库")

    def test_content_length_limit(self):
        wid = self.staff_ws()
        self.assert_http(422, post_message, wid,
                         {"content": "长" * 20001, "zone": "discussion"},
                         self.conn, self.staff)


if __name__ == "__main__":
    unittest.main()
