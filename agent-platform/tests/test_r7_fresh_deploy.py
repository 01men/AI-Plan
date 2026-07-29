import os
import sqlite3
import unittest
from unittest.mock import patch

from app import engine
from app.database import init_db
from app.seed import run_r4_seed, run_r6_seed, run_seed


class R7FreshDeployDemoChatTest(unittest.TestCase):
    """全新部署开箱缺口：未配置模型 Key 时，demo 模式降级为标注明确的演示回复，
    production 模式保持原硬错误文案。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        run_r4_seed(self.conn)
        run_r6_seed(self.conn)
        row = self.conn.execute(
            "SELECT wm.workspace_id, wm.member_id person_id, am.member_id agent_id "
            "FROM workspace_members wm JOIN workspace_members am "
            "ON am.workspace_id=wm.workspace_id AND am.member_type='agent' "
            "WHERE wm.member_type='human' ORDER BY wm.workspace_id LIMIT 1"
        ).fetchone()
        self.workspace_id = row["workspace_id"]
        self.agent_id = row["agent_id"]
        self.person = self.conn.execute(
            "SELECT * FROM people WHERE id=?", (row["person_id"],)
        ).fetchone()
        self.agent = self.conn.execute(
            "SELECT * FROM agents WHERE id=?", (self.agent_id,)
        ).fetchone()

    def tearDown(self):
        self.conn.close()

    def _reply_row(self, message_id):
        return self.conn.execute(
            "SELECT * FROM messages WHERE id=?", (message_id,)
        ).fetchone()

    def test_demo_mode_no_key_returns_demo_reply_with_persona(self):
        with patch.dict(os.environ, {"PLATFORM_MODE": "demo"}):
            result = engine.chat_with_agent(
                self.conn, self.workspace_id, self.agent_id, self.person,
                "请分析订单交付风险",
            )
        info = result["model_info"]
        self.assertIsNone(info["provider"])
        self.assertIsNone(info["model"])
        self.assertFalse(info["ok"])
        self.assertEqual("演示回复（未配置模型）", info["reason"])
        self.assertTrue(info["demo_reply"])

        reply = self._reply_row(result["message_id"])
        self.assertIn("【演示回复·未配置模型算力】", reply["content"])
        self.assertIn(self.agent["name"], reply["content"])
        self.assertIn(self.agent["code"], reply["content"])
        self.assertIn(self.agent["category"], reply["content"])
        # 结合提问关键词与业务数据召回，有实质内容而非空壳占位
        self.assertIn("订单", reply["content"])
        self.assertIn("默认业务数据分布", reply["content"])

        call = self.conn.execute(
            "SELECT * FROM llm_calls WHERE provider='demo_reply' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(call)
        self.assertEqual("demo_reply", call["status"])
        self.assertEqual(self.agent_id, call["agent_id"])

    def test_production_mode_keeps_hard_unavailable_message(self):
        with patch.dict(os.environ, {"PLATFORM_MODE": "production"}):
            result = engine.chat_with_agent(
                self.conn, self.workspace_id, self.agent_id, self.person,
                "请分析订单交付风险",
            )
        info = result["model_info"]
        self.assertFalse(info["ok"])
        self.assertEqual("未配置可用模型", info["reason"])
        self.assertNotIn("demo_reply", info)

        reply = self._reply_row(result["message_id"])
        self.assertIn("没有配置可用的模型算力", reply["content"])
        self.assertNotIn("【演示回复", reply["content"])
        self.assertIsNone(
            self.conn.execute(
                "SELECT * FROM llm_calls WHERE provider='demo_reply'"
            ).fetchone()
        )


if __name__ == "__main__":
    unittest.main()
