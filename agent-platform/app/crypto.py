"""凭证应用层加密（R5）：AES-256-GCM

- 主密钥优先取环境变量 PLATFORM_MASTER_KEY（任意长度，SHA-256 归一为 32 字节）；
- 未设置时启动自动生成随机 256 位密钥，Base64 存于 data/master.key（仅本机可读，不入库）；
- 密文格式：enc:v1:<base64(nonce+密文)>；未带前缀的值按明文兼容读取（便于老库平滑迁移）。
"""
import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "enc:v1:"
_KEY_FILE = Path(__file__).resolve().parent.parent / "data" / "master.key"
_master_key = None


def _load_master_key() -> bytes:
    global _master_key
    if _master_key:
        return _master_key
    env = os.environ.get("PLATFORM_MASTER_KEY", "").strip()
    if env:
        _master_key = hashlib.sha256(env.encode("utf-8")).digest()
        return _master_key
    if _KEY_FILE.exists():
        _master_key = base64.urlsafe_b64decode(_KEY_FILE.read_bytes().strip())
        return _master_key
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _master_key = AESGCM.generate_key(bit_length=256)
    _KEY_FILE.write_bytes(base64.urlsafe_b64encode(_master_key))
    try:
        os.chmod(_KEY_FILE, 0o600)
    except OSError:
        pass  # Windows 上 chmod 语义有限，尽力而为
    return _master_key


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(plain: str) -> str:
    """明文 → enc:v1 密文；空串原样返回（空表示未配置，不加密）"""
    if not plain:
        return plain
    nonce = os.urandom(12)
    ct = AESGCM(_load_master_key()).encrypt(nonce, plain.encode("utf-8"), None)
    return PREFIX + base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt(value: str) -> str:
    """enc:v1 密文 → 明文；非密文（老库明文/空串）原样返回"""
    if not is_encrypted(value):
        return value
    raw = base64.urlsafe_b64decode(value[len(PREFIX):].encode("ascii"))
    return AESGCM(_load_master_key()).decrypt(raw[:12], raw[12:], None).decode("utf-8")


def migrate_credentials(conn) -> int:
    """启动迁移：把 model_providers.api_key / auth_providers.app_secret 中的明文改写为密文。

    幂等：已带 enc:v1 前缀的行跳过。返回本次加密的字段数。
    """
    n = 0
    for table, col in (("model_providers", "api_key"), ("auth_providers", "app_secret")):
        for row in conn.execute(f"SELECT id, {col} v FROM {table}").fetchall():
            v = (row["v"] or "").strip()
            if v and not is_encrypted(v):
                conn.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (encrypt(v), row["id"]))
                n += 1
    if n:
        conn.commit()
    return n
