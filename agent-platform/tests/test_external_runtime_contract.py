import sqlite3
import unittest

from app.database import init_db
from app.seed import run_seed
from app.routers.tasks import create_task, external_event, get_task, review_task


class ExternalRuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        self.developer = dict(self.conn.execute("SELECT * FROM people WHERE id=20").fetchone())
        self.coach = dict(self.conn.execute("SELECT * FROM people WHERE id=2").fetchone())
        self.agent_id = self.conn.execute(
            "SELECT id FROM agents ORDER BY id LIMIT 1").fetchone()["id"]

    def tearDown(self):
        self.conn.close()

    def create_agent_task(self, title="契约测试"):
        return create_task({
            "title": title,
            "agent_id": self.agent_id,
            "workspace_id": 2,
            "requirement": "请完成任务",
        }, self.conn, self.developer)

    def test_external_deliverable_is_idempotent_and_waits_for_human(self):
        task = self.create_agent_task()
        task_id = task["id"]
        self.assertEqual(task_id, get_task(task_id, self.conn, self.developer)["id"])
        started = external_event(task_id, {
            "event_id": f"dispatch:issue-{task_id}",
            "event_type": "started",
            "source": "multica",
        }, self.conn, self.coach)
        self.assertEqual("进行中", started["task"]["status"])
        self.assertIsNone(started["task"]["deliverable"])

        body = {
            "event_id": f"deliverable:issue-{task_id}:hash",
            "event_type": "deliverable",
            "source": "multica",
            "content": "## 真实交付物\n\n已完成。",
        }
        delivered = external_event(task_id, body, self.conn, self.coach)
        duplicate = external_event(task_id, body, self.conn, self.coach)
        self.assertEqual("待审核", delivered["task"]["status"])
        self.assertNotEqual("已通过", delivered["task"]["status"])
        self.assertTrue(duplicate["idempotent"])
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE workspace_id=2 AND msg_type='deliverable' "
            "AND payload LIKE '%\"runtime\": \"external\"%'").fetchone()["c"]
        self.assertEqual(1, count)

    def test_external_reject_waits_for_external_rework(self):
        task = self.create_agent_task("外部驳回")
        task_id = task["id"]
        external_event(task_id, {
            "event_id": f"deliverable:issue-{task_id}:hash",
            "event_type": "deliverable",
            "source": "multica",
            "content": "外部结果",
        }, self.conn, self.coach)
        rejected = review_task(task_id, {"action": "reject", "comment": "补充来源"},
                               self.conn, self.coach)
        self.assertEqual("已驳回", rejected["status"])

    def test_local_reject_keeps_original_auto_rework(self):
        task = self.create_agent_task("本地驳回")
        rejected = review_task(task["id"], {"action": "reject", "comment": "本地重做"},
                               self.conn, self.coach)
        self.assertEqual("待审核", rejected["status"])
        self.assertIn("第 2 版修订说明", rejected["deliverable"])


if __name__ == "__main__":
    unittest.main()
