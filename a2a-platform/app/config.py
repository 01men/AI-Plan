from dataclasses import dataclass
from pathlib import Path
import os
import secrets


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    db_path: Path = Path(os.getenv("A2A_DB_PATH", str(ROOT / "data" / "control.db")))
    admin_token: str = os.getenv("A2A_ADMIN_TOKEN", "")
    issuer: str = os.getenv("A2A_TOKEN_ISSUER", "rongqi-a2a")
    # Never ship a reusable signing secret. Local development gets an
    # process-scoped value; production must inject A2A_SIGNING_KEY.
    signing_key: str = os.getenv("A2A_SIGNING_KEY") or secrets.token_urlsafe(32)
    default_timeout_seconds: int = int(os.getenv("A2A_DEFAULT_TIMEOUT_SECONDS", "300"))
    worker_interval_seconds: int = int(os.getenv("A2A_WORKER_INTERVAL_SECONDS", "2"))
    single_instance: bool = _bool("A2A_SINGLE_INSTANCE", True)


CONFIG = Config()
