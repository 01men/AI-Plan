from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from threading import Lock
from typing import Any


class RongqiAPIError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"榕器 API {status}：{detail}")
        self.status = status
        self.detail = detail


class RongqiClient:
    def __init__(self, base_url: str, token: str = "", person_id: int = 2,
                 timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.person_id = person_id
        self.timeout = timeout
        self._login_lock = Lock()

    def _login(self) -> None:
        with self._login_lock:
            if self.token:
                return
            data = self._request("POST", "/api/login", {"person_id": self.person_id},
                                 authenticated=False)
            self.token = data["token"]

    def _request(self, method: str, path: str, body: dict | None = None,
                 authenticated: bool = True, retry_auth: bool = True) -> Any:
        if authenticated and not self.token:
            self._login()
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base_url + path, data=raw, method=method,
                                         headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
                return json.loads(text) if text else None
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(text).get("detail", text)
            except json.JSONDecodeError:
                detail = text
            if exc.code == 401 and authenticated and retry_auth:
                self.token = ""
                self._login()
                return self._request(method, path, body, authenticated=True, retry_auth=False)
            raise RongqiAPIError(exc.code, str(detail)) from exc
        except urllib.error.URLError as exc:
            raise RongqiAPIError(503, str(exc.reason)) from exc

    def get_task(self, task_id: int) -> dict:
        return self._request("GET", f"/api/tasks/{task_id}")

    def list_agents(self) -> list[dict]:
        return self._request("GET", "/api/agents")

    def post_external_event(self, task_id: int, *, event_id: str, event_type: str,
                            content: str = "", metadata: dict | None = None,
                            source: str = "multica") -> dict:
        return self._request("POST", f"/api/tasks/{task_id}/external-events", {
            "event_id": event_id,
            "event_type": event_type,
            "source": source,
            "content": content,
            "metadata": metadata or {},
        })

