from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Callable


class MulticaError(RuntimeError):
    pass


def _json(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith(("{", "[")):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    raise MulticaError("Multica 未返回可解析的 JSON")


class MulticaCLI:
    """通过官方 CLI 对接；所有命令均为参数数组且 shell=False。"""

    def __init__(self, cli_path: str = "multica", profile: str = "", timeout: int = 45,
                 runner: Callable[..., subprocess.CompletedProcess] | None = None):
        self.cli_path = cli_path or "multica"
        self.profile = profile.strip()
        self.timeout = timeout
        self.runner = runner or subprocess.run

    def available(self) -> bool:
        return bool(shutil.which(self.cli_path) or os.path.isfile(self.cli_path))

    def run(self, *parts: str, workspace_id: str = "", output_json: bool = False):
        args = [self.cli_path, *[str(part) for part in parts]]
        if workspace_id:
            args.extend(["--workspace-id", workspace_id])
        if self.profile:
            args.extend(["--profile", self.profile])
        if output_json:
            args.extend(["--output", "json"])
        try:
            result = self.runner(args, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=self.timeout, shell=False, check=False)
        except FileNotFoundError as exc:
            raise MulticaError(f"找不到 Multica CLI：{self.cli_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MulticaError(f"Multica 命令超过 {self.timeout} 秒未完成") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout or "未知错误").strip()
            raise MulticaError(f"Multica 命令失败：{detail[:500]}")
        return _json(result.stdout) if output_json else result.stdout.strip()

    def health(self) -> dict:
        if not self.available():
            return {"available": False, "authenticated": False,
                    "detail": f"未找到 CLI：{self.cli_path}"}
        try:
            return {"available": True, "authenticated": True,
                    "version": self.run("version"),
                    "auth": self.run("auth", "status", output_json=True)}
        except MulticaError as exc:
            return {"available": True, "authenticated": False, "detail": str(exc)}

    def create_issue(self, *, title: str, description: str, priority: str,
                     workspace_id: str, assignee_id: str = "", assignee_name: str = "",
                     project_id: str = "", due_date: str = "") -> dict:
        parts = ["issue", "create", "--title", title, "--description", description,
                 "--status", "todo", "--priority", priority]
        if assignee_id:
            parts.extend(["--assignee-id", assignee_id])
        elif assignee_name:
            parts.extend(["--assignee", assignee_name])
        if project_id:
            parts.extend(["--project", project_id])
        if due_date:
            parts.extend(["--due-date", due_date[:10]])
        data = self.run(*parts, workspace_id=workspace_id, output_json=True)
        if not isinstance(data, dict):
            raise MulticaError("创建 Issue 的响应不是对象")
        return data

    def get_issue(self, issue_id: str, workspace_id: str) -> dict:
        data = self.run("issue", "get", issue_id, workspace_id=workspace_id,
                        output_json=True)
        if not isinstance(data, dict):
            raise MulticaError("Issue 详情响应不是对象")
        return data

    def issue_runs(self, issue_id: str, workspace_id: str):
        return self.run("issue", "runs", issue_id, workspace_id=workspace_id,
                        output_json=True)

    def run_messages(self, run_id: str, workspace_id: str):
        return self.run("issue", "run-messages", run_id, workspace_id=workspace_id,
                        output_json=True)

    def add_comment(self, issue_id: str, content: str, workspace_id: str):
        self.run("issue", "comment", "add", issue_id, "--content", content,
                 workspace_id=workspace_id)

    def set_status(self, issue_id: str, status: str, workspace_id: str):
        self.run("issue", "status", issue_id, status, workspace_id=workspace_id)


PRIORITY = {"高": "high", "中": "medium", "低": "low"}


def issue_identity(data: dict) -> tuple[str, str]:
    issue = data.get("issue") if isinstance(data.get("issue"), dict) else data
    issue_id = issue.get("id") or issue.get("issue_id") or issue.get("uuid")
    issue_key = issue.get("key") or issue.get("identifier") or issue.get("number") or ""
    if not issue_id:
        raise MulticaError("创建成功响应中缺少 Issue id")
    return str(issue_id), str(issue_key)


def issue_status(data: dict) -> str:
    issue = data.get("issue") if isinstance(data.get("issue"), dict) else data
    status = issue.get("status") or issue.get("state") or ""
    if isinstance(status, dict):
        status = status.get("key") or status.get("name") or ""
    return str(status).strip().lower().replace(" ", "_")


def _list(data: Any, *keys: str) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            if isinstance(data.get(key), list):
                return data[key]
        if isinstance(data.get("data"), list):
            return data["data"]
    return []


def latest_run_id(data: Any) -> str:
    rows = _list(data, "runs", "tasks", "items")
    if not rows or not isinstance(rows[-1], dict):
        return ""
    row = rows[-1]
    return str(row.get("id") or row.get("task_id") or row.get("run_id") or "")


def deliverable(data: Any, max_chars: int = 20000) -> str:
    texts = []
    for row in _list(data, "messages", "items", "events"):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or row.get("kind") or "").lower()
        role = str(row.get("role") or row.get("sender") or "").lower()
        if any(mark in kind for mark in ("tool", "thinking", "reasoning")):
            continue
        if role and role not in ("assistant", "agent", "ai"):
            continue
        value = row.get("content") or row.get("text") or row.get("message")
        if isinstance(value, dict):
            value = value.get("text") or value.get("content")
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
    return "\n\n".join(texts)[-max_chars:]
