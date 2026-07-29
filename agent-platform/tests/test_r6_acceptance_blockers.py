import io
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from app import engine
from app.database import init_db
from app.routers import knowledge
from app.routers.workspaces import post_message
from app.seed import run_r4_seed, run_r6_seed, run_seed


class FakeModelResponse:
    def __init__(self, text):
        self.payload = json.dumps({
            "choices": [{"message": {"content": text}}],
        }, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class R6AcceptanceBlockersTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        run_r4_seed(self.conn)
        run_r6_seed(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_default_business_records_are_exactly_1000_and_self_healing(self):
        self.assertEqual(
            1000,
            self.conn.execute(
                "SELECT COUNT(*) c FROM business_records WHERE record_no LIKE 'DEMO-%'"
            ).fetchone()["c"],
        )
        groups = {
            row["business_type"]: row["c"]
            for row in self.conn.execute(
                "SELECT business_type,COUNT(*) c FROM business_records GROUP BY business_type"
            )
        }
        self.assertEqual(
            {
                "销售订单": 200, "生产报工": 200, "质量检验": 200,
                "库存流水": 200, "售后工单": 200,
            },
            groups,
        )
        self.assertEqual(0, run_r6_seed(self.conn), "重复启动不得重复生成")
        self.conn.execute("DELETE FROM business_records WHERE record_no='DEMO-0042'")
        self.conn.commit()
        self.assertEqual(1, run_r6_seed(self.conn), "缺失样例应在下次启动自动补回")
        self.assertEqual(
            1,
            self.conn.execute(
                "SELECT COUNT(*) c FROM business_records WHERE record_no='DEMO-0042'"
            ).fetchone()["c"],
        )

    def test_xlsx_multiple_sheets_to_sqlite_and_csv(self):
        workbook = Workbook()
        orders = workbook.active
        orders.title = "订单明细"
        orders.append(["订单号", "数量", "金额", "交期"])
        orders.append(["SO-001", 12, 399.5, datetime(2026, 7, 30, 8, 0)])
        orders.append(["SO-002", 8, 528.0, datetime(2026, 7, 31, 9, 30)])
        quality = workbook.create_sheet("质量记录")
        quality.append(["批次", "合格", "不良率"])
        quality.append(["B-01", True, 0.012])
        payload = io.BytesIO()
        workbook.save(payload)

        datasets = knowledge._excel_parse(payload.getvalue(), ".xlsx")
        self.assertEqual(["订单明细", "质量记录"], [item["sheet_name"] for item in datasets])

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(knowledge, "KNOWLEDGE_DB_DIR", Path(temp_dir)):
                db_file, metadata = knowledge._excel_to_sqlite_csv(88, datasets)
                self.assertEqual(2, len(metadata))
                self.assertTrue(db_file.exists())
                self.assertTrue(Path(metadata[0]["csv_path"]).exists())
                conn = sqlite3.connect(str(db_file))
                try:
                    table = metadata[0]["table_name"]
                    types = {
                        row[1]: row[2]
                        for row in conn.execute(f'PRAGMA table_info("{table}")')
                    }
                    self.assertEqual("INTEGER", types["数量"])
                    self.assertEqual("REAL", types["金额"])
                    self.assertEqual(2, conn.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0])
                    self.assertEqual("SO-001", conn.execute(
                        f'SELECT "订单号" FROM "{table}" ORDER BY rowid LIMIT 1'
                    ).fetchone()[0])
                finally:
                    conn.close()

    def test_agent_chat_calls_model_with_project_knowledge_and_business_context(self):
        self.conn.execute(
            "UPDATE model_providers SET api_key='test-key',enabled=1,"
            "base_url='https://model.example/v1',default_model='test-model' WHERE key='qwen'"
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('default_model_key','qwen')"
        )
        person = self.conn.execute("SELECT * FROM people WHERE name='徐露璐'").fetchone()
        membership = self.conn.execute(
            "SELECT wm.workspace_id,am.member_id agent_id FROM workspace_members wm "
            "JOIN workspace_members am ON am.workspace_id=wm.workspace_id "
            "AND am.member_type='agent' WHERE wm.member_type='human' AND wm.member_id=? "
            "ORDER BY wm.workspace_id LIMIT 1", (person["id"],)
        ).fetchone()
        document_id = self.conn.execute(
            "SELECT id FROM documents WHERE level IN ('L1','L2') ORDER BY id LIMIT 1"
        ).fetchone()["id"]
        self.conn.execute(
            "INSERT INTO doc_chunks(document_id,seq,heading,content) VALUES(?,?,?,?)",
            (document_id, 1, "订单风险规则", "德国客户订单交期不足 7 天时需要升级人工复核。"),
        )
        self.conn.commit()

        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeModelResponse("我是外贸跟单数字员工。建议先核对交期，再按风险等级推进项目。")

        with patch.object(engine.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = post_message(
                membership["workspace_id"],
                {
                    "content": "请结合订单和知识库规则，继续深化德国客户交付风险方案",
                    "zone": "agent",
                    "interaction_mode": "chat",
                    "target_agent_id": membership["agent_id"],
                },
                conn=self.conn,
                person=person,
            )

        self.assertEqual(1, len(result["replies"]))
        self.assertTrue(result["replies"][0]["model_info"]["ok"])
        system_prompt = captured["body"]["messages"][0]["content"]
        self.assertIn("【项目上下文】", system_prompt)
        self.assertIn("德国客户订单交期不足", system_prompt)
        self.assertIn("默认业务数据分布", system_prompt)
        reply = self.conn.execute(
            "SELECT * FROM messages WHERE id=?", (result["replies"][0]["message_id"],)
        ).fetchone()
        self.assertEqual("agent", reply["sender_type"])
        self.assertIn("建议先核对交期", reply["content"])
        call = self.conn.execute(
            "SELECT * FROM llm_calls WHERE task_id IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual("ok", call["status"])
        self.assertEqual("qwen", call["provider"])


if __name__ == "__main__":
    unittest.main()
