"""R5 交付闭环：角色边界、配置校验、激励闭环与一次性授权凭证。"""
import sqlite3
import unittest

from fastapi import HTTPException

from app.database import init_db
from app.routers.agents import create_agent, update_agent
from app.routers.governance import (create_incentive, incentive_summary,
                                    review_incentive)
from app.routers.skills import create_skill
from app.security import (consume_login_code, consume_oauth_state,
                          create_login_code, create_oauth_state)
from app.seed import run_r4_seed, run_r5_seed, run_seed


class BusinessClosureTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        run_r4_seed(self.conn)
        run_r5_seed(self.conn)
        self.boss = dict(self.conn.execute(
            "SELECT * FROM people WHERE tier='boss' LIMIT 1").fetchone())
        self.coach = dict(self.conn.execute(
            "SELECT * FROM people WHERE tier='coach' LIMIT 1").fetchone())
        self.developer = dict(self.conn.execute(
            "SELECT * FROM people WHERE id=20").fetchone())
        self.staff = dict(self.conn.execute(
            "SELECT * FROM people WHERE id=40").fetchone())

    def tearDown(self):
        self.conn.close()

    def assert_http(self, status, fn, *args):
        with self.assertRaises(HTTPException) as ctx:
            fn(*args)
        self.assertEqual(status, ctx.exception.status_code)

    def test_skill_maintenance_is_manager_only_and_validated(self):
        self.assert_http(
            403, create_skill, {"name": "越权技能"}, self.conn, self.staff)
        self.assert_http(
            422, create_skill,
            {"name": "错误范围", "scope": "全宇宙"}, self.conn, self.boss)
        created = create_skill(
            {"name": "交付验收清单", "scope": "组织"}, self.conn, self.coach)
        self.assertEqual("组织", created["scope"])

    def test_developer_can_only_create_owned_agent_in_own_department(self):
        self.assert_http(
            403, create_agent,
            {"name": "跨部门数字员工", "dept_id": 1}, self.conn, self.developer)
        created = create_agent(
            {"name": "本部门验收数字员工", "dept_id": self.developer["dept_id"],
             "wave": 4},
            self.conn, self.developer,
        )
        self.assertEqual(self.developer["id"], created["owner_id"])
        self.assert_http(
            422, update_agent, created["id"], {"accuracy": 101},
            self.conn, self.developer)
        updated = update_agent(
            created["id"], {"status": "试点中"}, self.conn, self.developer)
        self.assertEqual("试点中", updated["status"])

    def test_incentive_pool_and_review_release_closed_loop(self):
        self.assert_http(
            403, create_incentive,
            {"type": "火花奖", "nominee": "其他人", "amount": 800},
            self.conn, self.staff,
        )
        item = create_incentive(
            {"type": "火花奖", "nominee": self.staff["name"],
             "reason": "一线改善", "amount": 800},
            self.conn, self.staff,
        )
        assessed = review_incentive(
            item["id"], {"action": "approve", "comment": "证据完整"},
            self.conn, self.coach,
        )
        self.assertEqual("已评定", assessed["status"])
        released = review_incentive(
            item["id"], {"action": "release"}, self.conn, self.boss)
        self.assertEqual("已发放", released["status"])
        self.assertGreater(incentive_summary(self.conn, self.boss)["remaining"], 0)
        self.assert_http(
            422, create_incentive,
            {"type": "种子基金", "nominee": "超额验证", "amount": 100000},
            self.conn, self.boss,
        )

    def test_oauth_state_and_login_code_are_one_time(self):
        state = create_oauth_state(
            self.conn, "dingtalk", "bind", self.staff["id"])
        payload = consume_oauth_state(self.conn, state, "dingtalk")
        self.assertEqual(self.staff["id"], payload["person_id"])
        self.assertIsNone(consume_oauth_state(self.conn, state, "dingtalk"))

        code = create_login_code(self.conn, self.staff["id"], "dingtalk")
        first = consume_login_code(self.conn, code)
        self.assertEqual(self.staff["id"], first["person_id"])
        self.assertIsNone(consume_login_code(self.conn, code))


if __name__ == "__main__":
    unittest.main()
