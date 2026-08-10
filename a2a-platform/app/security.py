import base64
import hashlib
import hmac
import json
import time


class PolicyError(ValueError):
    pass


def require_policy(contract: dict):
    data_levels = {str(x.get('level', 'L1')) for x in contract.get('data_scope', []) if isinstance(x, dict)}
    tool_levels = {str(x.get('tier', 'T0')) for x in contract.get('tools', []) if isinstance(x, dict)}
    write = contract.get('write_policy', 'forbid')
    if not data_levels.issubset({'L1', 'L2'}) or not tool_levels.issubset({'T0', 'T1'}):
        raise PolicyError('首期仅允许 L1/L2 数据和 T0/T1 工具')
    if write not in {'forbid', 'suggest'}:
        raise PolicyError('首期禁止自动写入；仅允许 forbid 或 suggest')
    if write == 'suggest' and not contract.get('approval_ticket_id'):
        raise PolicyError('生成建议也必须关联人工审核票据')


def issue_token(payload: dict, key: str, issuer: str, ttl_seconds: int = 600) -> str:
    body = dict(payload, iss=issuer, exp=int(time.time()) + ttl_seconds)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    sig = hmac.new(key.encode(), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=') + '.' + base64.urlsafe_b64encode(sig).decode().rstrip('=')


def verify_token(token: str, key: str, issuer: str) -> dict:
    try:
        raw_part, sig_part = token.split('.', 1)
        raw = base64.urlsafe_b64decode(raw_part + '=' * (-len(raw_part) % 4))
        sig = base64.urlsafe_b64decode(sig_part + '=' * (-len(sig_part) % 4))
        expected = hmac.new(key.encode(), raw, hashlib.sha256).digest()
        body = json.loads(raw)
    except Exception as exc:
        raise PolicyError('任务授权令牌格式无效') from exc
    if not hmac.compare_digest(sig, expected) or body.get('iss') != issuer or body.get('exp', 0) < time.time():
        raise PolicyError('任务授权令牌无效或已过期')
    return body
