from dataclasses import dataclass
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    rongqi_api_url: str = os.getenv("RONGQI_API_URL", "http://127.0.0.1:8000").rstrip("/")
    rongqi_api_token: str = os.getenv("RONGQI_API_TOKEN", "")
    rongqi_person_id: int = int(os.getenv("RONGQI_PERSON_ID", "2"))
    multica_cli: str = os.getenv("MULTICA_CLI", "multica")
    multica_profile: str = os.getenv("MULTICA_PROFILE", "")
    multica_workspace_id: str = os.getenv("MULTICA_WORKSPACE_ID", "")
    multica_timeout_seconds: int = int(os.getenv("MULTICA_TIMEOUT_SECONDS", "45"))
    bridge_db_path: Path = Path(os.getenv("BRIDGE_DB_PATH", str(ROOT / "data" / "bridge.db")))
    bridge_poll_seconds: int = int(os.getenv("BRIDGE_POLL_SECONDS", "30"))
    bridge_auto_sync: bool = _bool_env("BRIDGE_AUTO_SYNC", True)
    bridge_admin_token: str = os.getenv("BRIDGE_ADMIN_TOKEN", "")


CONFIG = Config()

