"""R7 生产认证与就绪探针回归。"""
import json
import os
import sqlite3
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.config import allowed_origins, public_environment
from app.database import init_db
from app.main import health_ready
from app.routers.auth import get_current_person, login
from app.routers.imbind import bind_provider, oauth_callback
from app.routers.org import login_people
from app.seed import run_r4_seed, run_r6_seed, run_seed


class ProductionAuthTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        init_db(self.conn)
        run_seed(self.conn)
        run_r4_seed(self.conn)
        run_r6_seed(self.conn)
        self.boss = dict(self.conn.execute(
            "SELECT * FROM people WHERE tier='boss' LIMIT 1"
        ).fetchone())

    def tearDown(self):
        self.conn.close()

    def test_demo_is_default_and_keeps_local_cors(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                {"mode": "demo", "demo_login_enabled": True},
                public_environment(),
            )
            self.assertEqual(
                ["http://localhost:8000", "http://127.0.0.1:8000"],
                allowed_origins(),
            )

    def test_production_disables_all_demo_identity_entry_points(self):
        with patch.dict(os.environ, {"PLATFORM_MODE": "production"}, clear=True):
            for call in (
                lambda: login(type("Body", (), {"person_id": self.boss["id"]})(), self.conn),
                lambda: login_people(self.conn),
                lambda: oauth_callback("dingtalk", demo="1", person_id=self.boss["id"],
                                       conn=self.conn),
                lambda: bind_provider("dingtalk", self.conn, self.boss),
            ):
                with self.assertRaises(HTTPException) as caught:
                    call()
                self.assertEqual(403, caught.exception.status_code)
            self.assertEqual(
                {"mode": "production", "demo_login_enabled": False},
                public_environment(),
            )

    def test_disabled_employee_existing_session_is_rejected(self):
        token = "existing-session"
        self.conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            (f"token:{token}", json.dumps({
                "person_id": self.boss["id"],
                "expires_at": "2999-01-01T00:00:00",
            })),
        )
        self.conn.execute("UPDATE people SET status='离职' WHERE id=?", (self.boss["id"],))
        self.conn.commit()
        with self.assertRaises(HTTPException) as caught:
            get_current_person(f"Bearer {token}", self.conn)
        self.assertEqual(401, caught.exception.status_code)

    def test_production_readiness_blocks_without_real_im(self):
        self.conn.execute(
            "UPDATE model_providers SET enabled=1,api_key='enc:test',"
            "base_url='https://example.invalid/v1',default_model='test' WHERE id=("
            "SELECT MIN(id) FROM model_providers)"
        )
        self.conn.commit()
        with patch.dict(os.environ, {"PLATFORM_MODE": "production"}, clear=True):
            result = health_ready(self.conn)
        self.assertIsInstance(result, JSONResponse)
        self.assertEqual(503, result.status_code)
        payload = json.loads(result.body)
        self.assertIn("im_provider", payload["blocking"])
        self.assertTrue(payload["checks"]["database"]["ok"])
        self.assertTrue(payload["checks"]["business_data"]["ok"])
        self.assertNotIn("api_key", result.body.decode("utf-8"))
        self.assertNotIn("app_secret", result.body.decode("utf-8"))

    def test_demo_readiness_allows_unconfigured_external_services(self):
        with patch.dict(os.environ, {"PLATFORM_MODE": "demo"}, clear=True):
            result = health_ready(self.conn)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["ok"])
        self.assertFalse(result["checks"]["im_provider"]["required"])


if __name__ == "__main__":
    unittest.main()
