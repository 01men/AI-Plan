"""远端执行适配器。控制面只调用 HTTP；永不执行本机 CLI。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol


class AdapterError(RuntimeError):
    pass


class Adapter(Protocol):
    def capabilities(self, resource: dict) -> dict: ...
    def send(self, resource: dict, contract: dict, authorization: str) -> dict: ...
    def fetch_result(self, resource: dict, run: dict) -> dict: ...
    def cancel(self, resource: dict, run: dict) -> dict: ...
    def resume_or_provide_input(self, resource: dict, run: dict, value: dict) -> dict: ...
    def reconcile(self, resource: dict, run: dict) -> dict: ...
    def validate_artifact(self, result: dict) -> dict: ...


def _http(method: str, url: str, body: dict | None = None, timeout: int = 10) -> dict:
    raw = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=raw, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode() or '{}')
            if not isinstance(result, dict):
                raise AdapterError('远端响应必须为 JSON 对象')
            return result
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise AdapterError(f'远端服务调用失败：{exc}') from exc


class NativeA2AAdapter:
    def capabilities(self, resource):
        endpoint = resource['endpoint'].rstrip('/')
        return _http('GET', endpoint + '/.well-known/agent-card.json')

    def send(self, resource, contract, authorization):
        endpoint = resource['endpoint'].rstrip('/')
        return _http('POST', endpoint + '/a2a/tasks', {'contract': contract, 'authorization': authorization})

    def fetch_result(self, resource, run):
        return _http('GET', resource['endpoint'].rstrip('/') + '/a2a/tasks/' + run['external_run_id'])

    def cancel(self, resource, run):
        return _http('POST', resource['endpoint'].rstrip('/') + '/a2a/tasks/' + run['external_run_id'] + '/cancel')

    def resume_or_provide_input(self, resource, run, value):
        return _http('POST', resource['endpoint'].rstrip('/') + '/a2a/tasks/' + run['external_run_id'] + '/input', value)

    def reconcile(self, resource, run):
        return self.fetch_result(resource, run)

    def validate_artifact(self, result):
        content = result.get('artifact') or result.get('content')
        if not isinstance(content, str) or not content.strip():
            raise AdapterError('远端结果没有可审核产物')
        return {'content': content[:200000], 'provenance': result.get('provenance', {})}


class MockA2AAdapter(NativeA2AAdapter):
    """仅用于契约与无副作用验收，协议与原生 A2A 形状保持一致。"""


ADAPTERS = {'native_a2a': NativeA2AAdapter(), 'mock_a2a': MockA2AAdapter()}


def for_resource(resource: dict) -> Adapter:
    manifest = json.loads(resource.get('capability_manifest') or '{}')
    kind = manifest.get('adapter', 'native_a2a')
    if kind not in ADAPTERS:
        raise AdapterError(f'不支持的适配器：{kind}')
    return ADAPTERS[kind]
