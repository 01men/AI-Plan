import subprocess
import tempfile
import unittest
from pathlib import Path

from app.bridge import Bridge
from app.config import Config
from app.database import init_db
from app.multica_cli import MulticaCLI


class FakeRongqi:
    def __init__(self):
        self.tasks = {7: {
            "id": 7, "workspace_id": 2, "title": "真实执行测试", "agent_id": 11,
            "creator_id": 20, "reviewer_id": 2, "status": "待审核", "priority": "高",
            "requirement": "请运行真实 Agent", "deliverable": "本地模板", "review_comment": "",
            "deadline": "2026-07-21T18:00:00",
        }}
        self.events = []

    def get_task(self, task_id):
        return dict(self.tasks[task_id])

    def post_external_event(self, task_id, **event):
        self.events.append((task_id, event))
        task = self.tasks[task_id]
        kind = event["event_type"]
        if kind in ("started", "progress", "blocked"):
            task["status"] = "进行中"
            if kind == "started":
                task["deliverable"] = None
        elif kind == "deliverable":
            task["status"] = "待审核"
            task["deliverable"] = event["content"]
        elif kind == "cancelled":
            task["status"] = "已驳回"
        return {"ok": True, "idempotent": False, "task": dict(task)}


class FakeMultica:
    def __init__(self):
        self.created = []
        self.comments = []
        self.status_changes = []
        self.status = "in_progress"

    def create_issue(self, **kwargs):
        self.created.append(kwargs)
        return {"id": "issue-001", "identifier": "JJ-1"}

    def get_issue(self, issue_id, workspace_id):
        return {"id": issue_id, "status": self.status}

    def issue_runs(self, issue_id, workspace_id):
        return [{"id": "run-001"}]

    def run_messages(self, run_id, workspace_id):
        return {"messages": [
            {"role": "assistant", "type": "text", "content": "## 真实交付物\n已完成。"},
            {"role": "assistant", "type": "tool_call", "content": "不要暴露工具消息"},
        ]}

    def add_comment(self, issue_id, content, workspace_id):
        self.comments.append((issue_id, content, workspace_id))

    def set_status(self, issue_id, status, workspace_id):
        self.status_changes.append((issue_id, status, workspace_id))
        self.status = status


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config = Config(
            rongqi_api_url="http://127.0.0.1:8000", rongqi_api_token="",
            rongqi_person_id=2, multica_cli="multica", multica_profile="test",
            multica_workspace_id="workspace-001", multica_timeout_seconds=45,
            bridge_db_path=Path(self.tempdir.name) / "bridge.db", bridge_poll_seconds=30,
            bridge_auto_sync=False, bridge_admin_token="")
        init_db(self.config.bridge_db_path)
        self.rongqi = FakeRongqi()
        self.multica = FakeMultica()
        self.bridge = Bridge(self.config, self.rongqi, self.multica)
        self.bridge.upsert_binding(11, {"external_agent_id": "agent-001"})

    def tearDown(self):
        self.tempdir.cleanup()

    def test_dispatch_is_idempotent_and_replaces_template_with_running(self):
        first = self.bridge.dispatch(7)
        second = self.bridge.dispatch(7)
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(1, len(self.multica.created))
        self.assertEqual("进行中", self.rongqi.tasks[7]["status"])
        self.assertIsNone(self.rongqi.tasks[7]["deliverable"])

    def test_multica_done_only_enters_waiting_human_review(self):
        self.bridge.dispatch(7)
        self.multica.status = "done"
        result = self.bridge.sync(task_id=7)
        self.assertEqual("waiting_human_review", result[0]["state"])
        self.assertEqual("待审核", self.rongqi.tasks[7]["status"])
        self.assertIn("真实交付物", self.rongqi.tasks[7]["deliverable"])
        self.assertNotIn("工具消息", self.rongqi.tasks[7]["deliverable"])

    def test_human_rejection_routes_rework_to_multica(self):
        self.bridge.dispatch(7)
        self.multica.status = "done"
        self.bridge.sync(task_id=7)
        self.rongqi.tasks[7]["status"] = "已驳回"
        self.rongqi.tasks[7]["review_comment"] = "补充数据来源"
        result = self.bridge.sync(task_id=7)
        self.assertTrue(result[0]["rework"])
        self.assertIn("补充数据来源", self.multica.comments[-1][1])
        self.assertEqual("todo", self.multica.status_changes[-1][1])
        self.assertEqual("进行中", self.rongqi.tasks[7]["status"])

    def test_human_approval_is_final_authority(self):
        self.bridge.dispatch(7)
        self.multica.status = "done"
        self.bridge.sync(task_id=7)
        self.rongqi.tasks[7]["status"] = "已通过"
        self.rongqi.tasks[7]["review_comment"] = "同意生效"
        result = self.bridge.sync(task_id=7)
        self.assertEqual("approved", result[0]["state"])
        self.assertIn("同意生效", self.multica.comments[-1][1])

    def test_cli_never_interpolates_task_text_through_shell(self):
        captured = {}

        def runner(args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(args, 0, '{"id":"x"}', "")

        cli = MulticaCLI(runner=runner)
        unsafe = '任务; Remove-Item C:\\\\*'
        cli.create_issue(title=unsafe, description="$(whoami)", priority="high",
                         workspace_id="ws", assignee_id="agent")
        self.assertFalse(captured["kwargs"]["shell"])
        self.assertIn(unsafe, captured["args"])
        self.assertIn("$(whoami)", captured["args"])


if __name__ == "__main__":
    unittest.main()
