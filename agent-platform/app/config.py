"""运行环境配置。

默认保持历史演示模式兼容；生产模式关闭所有仅凭人员 ID 的模拟认证能力。
配置函数在调用时读取环境变量，便于测试与运维切换，且不在响应中暴露敏感值。
"""
import os
from urllib.parse import urlparse


VALID_PLATFORM_MODES = ("demo", "production")
DEFAULT_DEMO_ORIGINS = ("http://localhost:8000", "http://127.0.0.1:8000")


def platform_mode() -> str:
    """返回 demo/production；非法值按 production 失败关闭演示认证。"""
    value = os.environ.get("PLATFORM_MODE", "demo").strip().lower()
    return value if value in VALID_PLATFORM_MODES else "production"


def is_demo_mode() -> bool:
    return platform_mode() == "demo"


def demo_login_enabled() -> bool:
    return is_demo_mode()


def allowed_origins() -> list[str]:
    """读取逗号分隔的 CORS 来源；生产模式不提供隐式跨源白名单。"""
    raw = os.environ.get("PLATFORM_ALLOWED_ORIGINS", "").strip()
    candidates = raw.split(",") if raw else (DEFAULT_DEMO_ORIGINS if is_demo_mode() else ())
    origins = []
    for item in candidates:
        origin = item.strip().rstrip("/")
        parsed = urlparse(origin)
        if (
            origin
            and origin != "*"
            and parsed.scheme in ("http", "https")
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        ):
            origins.append(origin)
    return list(dict.fromkeys(origins))


def public_environment() -> dict:
    """前端可安全读取的环境能力，不返回来源、凭证或内部配置。"""
    return {
        "mode": platform_mode(),
        "demo_login_enabled": demo_login_enabled(),
    }
