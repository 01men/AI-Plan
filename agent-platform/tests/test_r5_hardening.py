"""R5 终极优化回归：工作区鉴权 / 派活兜底 / 凭证加密 / 模型回落留痕"""
import json
import sqlite3
import unittest

from fastapi import HTTPException

from app import crypto, engine
from app.database import init_db
from app.seed import run_r4_seed, run_r5_seed, run_seed
from app.routers.tasks import get_task, list_tasks
from app.routers.workspaces import (get_workspace, list_messages, list_workspaces,
                                    post_message, workspace_chain)


class R5Base(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        run_r4_seed(self.conn)
        run_r5_seed(self.conn)
        self.boss = dict(self.conn.execute("SELECT * FROM people WHERE tier='boss' LIMIT 1").fetchone())
        self.staff = dict(self.conn.execute("SELECT * FROM people WHERE id=40").fetchone())  # 徐露璐

    def tearDown(self):
        self.conn.close()

    def member_ws(self, pid):
        return [r["workspace_id"] for r in self.conn.execute(
            "SELECT workspace_id FROM workspace_members WHERE member_type='human' AND member_id=?",
            (pid,))]

    def foreign_ws(self, pid):
        row = self.conn.execute(
            "SELECT id FROM workspaces WHERE id NOT IN ("
            "SELECT workspace_id FROM workspace_members WHERE member_type='human' AND member_id=?) "
            "LIMIT 1", (pid,)).fetchone()
        return row["id"] if row else None


class WorkspaceAuthTests(R5Base):
    def test_list_workspaces_filtered_for_staff(self):
        mine = list_workspaces(None, self.conn, self.staff)
        all_ws = list_workspaces(None, self.conn, self.boss)
        self.assertLess(len(mine), len(all_ws))
        self.assertEqual(sorted(w["id"] for w in mine), sorted(self.member_ws(40)))

    def test_non_member_get_workspace_404(self):
        wid = self.foreign_ws(40)
        with self.assertRaises(HTTPException) as ctx:
            get_workspace(wid, self.conn, self.staff)
        self.assertEqual(404, ctx.exception.status_code)

    def test_non_member_messages_and_chain_404(self):
        wid = self.foreign_ws(40)
        with self.assertRaises(HTTPException) as ctx:
            list_messages(wid, conn=self.conn, person=self.staff)
        self.assertEqual(404, ctx.exception.status_code)
        with self.assertRaises(HTTPException) as ctx:
            workspace_chain(wid, self.conn, self.staff)
        self.assertEqual(404, ctx.exception.status_code)
        # 管理层不受影响
        self.assertEqual(wid, get_workspace(wid, self.conn, self.boss)["id"])

    def test_non_member_cannot_post(self):
        wid = self.foreign_ws(40)
        with self.assertRaises(HTTPException) as ctx:
            post_message(wid, {"content": "越权发言", "zone": "discussion"}, self.conn, self.staff)
        self.assertEqual(404, ctx.exception.status_code)

    def test_task_visibility(self):
        mine = list_tasks(None, None, None, None, self.conn, self.staff)
        all_t = list_tasks(None, None, None, None, self.conn, self.boss)
        self.assertLessEqual(len(mine), len(all_t))
        visible_ids = {t["id"] for t in mine}
        foreign = [t["id"] for t in all_t if t["id"] not in visible_ids]
        if foreign:
            with self.assertRaises(HTTPException) as ctx:
                get_task(foreign[0], self.conn, self.staff)
            self.assertEqual(404, ctx.exception.status_code)


class ScenarioInventoryTests(R5Base):
    def test_prd_department_quotas_total_232(self):
        rows = self.conn.execute(
            "SELECT d.name,COUNT(s.id) c FROM departments d "
            "LEFT JOIN scenarios s ON s.dept_id=d.id GROUP BY d.id"
        ).fetchall()
        self.assertEqual(232, sum(row["c"] for row in rows))
        self.assertEqual(
            151,
            self.conn.execute(
                "SELECT COUNT(*) c FROM scenarios WHERE batch='规划储备'"
            ).fetchone()["c"],
        )
        self.assertFalse(run_r5_seed(self.conn), "R5 场景容量播种必须幂等")


class UndispatchedFallbackTests(R5Base):
    def test_offline_agent_workspace_returns_guidance(self):
        # 显式建立“工作区内所有数字员工均离线”的验收前置条件。
        self.conn.execute(
            "UPDATE agents SET status='已下线' WHERE id IN ("
            "SELECT member_id FROM workspace_members "
            "WHERE workspace_id=2 AND member_type='agent')"
        )
        self.conn.commit()
        resp = post_message(2, {"content": "请帮我整理本周售后记录", "zone": "agent"},
                            self.conn, self.staff)
        self.assertEqual([], resp["dispatched"])
        u = resp.get("undispatched")
        self.assertIsNotNone(u, "未派发时必须返回 undispatched 兜底信息")
        self.assertTrue(u["reason"])
        self.assertTrue(u["suggestions"], "必须给出可执行的推荐员工")
        # 待处理需求任务已登记且可查
        task = self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                 (u["pending_task_id"],)).fetchone()
        self.assertEqual("待处理", task["status"])
        # 工作区内有项目管理智能体的引导消息
        guide = self.conn.execute(
            "SELECT content FROM messages WHERE workspace_id=2 AND sender_name='项目管理智能体' "
            "AND content LIKE '%派活引导%' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(guide)


class CredentialCryptoTests(R5Base):
    def test_roundtrip_and_plaintext_compat(self):
        secret = "sk-test-密钥-123"
        enc = crypto.encrypt(secret)
        self.assertTrue(enc.startswith("enc:v1:"))
        self.assertNotIn(secret, enc)
        self.assertEqual(secret, crypto.decrypt(enc))
        self.assertEqual("明文兼容", crypto.decrypt("明文兼容"))
        self.assertEqual("", crypto.decrypt(""))

    def test_migrate_credentials_idempotent(self):
        self.conn.execute("UPDATE model_providers SET api_key='plain-key-1' WHERE key='glm'")
        self.conn.execute("UPDATE auth_providers SET app_secret='plain-secret-1' WHERE provider='dingtalk'")
        self.conn.commit()
        n1 = crypto.migrate_credentials(self.conn)
        self.assertEqual(2, n1)
        row = self.conn.execute("SELECT api_key FROM model_providers WHERE key='glm'").fetchone()
        self.assertTrue(row["api_key"].startswith("enc:v1:"))
        self.assertEqual("plain-key-1", crypto.decrypt(row["api_key"]))
        row2 = self.conn.execute("SELECT app_secret FROM auth_providers WHERE provider='dingtalk'").fetchone()
        self.assertEqual("plain-secret-1", crypto.decrypt(row2["app_secret"]))
        self.assertEqual(0, crypto.migrate_credentials(self.conn))  # 幂等


class LlmFallbackTraceTests(R5Base):
    def test_failed_call_falls_back_and_is_logged(self):
        # 指向不可达地址，模拟供应商 4xx/超时
        self.conn.execute(
            "UPDATE model_providers SET api_key=?, base_url='http://127.0.0.1:9', timeout=5 "
            "WHERE key='glm'", (crypto.encrypt("fake-key"),))
        self.conn.execute(
            "INSERT INTO settings(key,value) VALUES('default_model_key','glm') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        self.conn.commit()
        agent = dict(self.conn.execute("SELECT * FROM agents ORDER BY id LIMIT 1").fetchone())
        text, info = engine.generate_deliverable(self.conn, agent, "测试需求", task_id=999)
        self.assertTrue(info["fallback"], "调用失败必须标记 fallback")
        self.assertEqual("glm", info["provider"])
        self.assertTrue(info["reason"], "必须记录失败原因")
        self.assertTrue(text.startswith("## 交付物"), "回落后应为模板交付物")
        rows = self.conn.execute(
            "SELECT status, provider, error, fallback_reason FROM llm_calls WHERE task_id=999 "
            "ORDER BY id").fetchall()
        self.assertEqual("error", rows[0]["status"])
        self.assertIn("glm", rows[0]["provider"])
        self.assertNotIn("fake-key", (rows[0]["error"] or "") + (rows[0]["fallback_reason"] or ""),
                         "留痕中绝不允许出现密钥")

    def test_no_config_uses_template_with_reason(self):
        self.conn.execute("UPDATE model_providers SET api_key='' ")
        self.conn.commit()
        agent = dict(self.conn.execute("SELECT * FROM agents ORDER BY id LIMIT 1").fetchone())
        text, info = engine.generate_deliverable(self.conn, agent, "测试需求", task_id=998)
        self.assertTrue(info["fallback"])
        self.assertIsNone(info["provider"])
        self.assertTrue(text.startswith("## 交付物"))


if __name__ == "__main__":
    unittest.main()
