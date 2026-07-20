# -*- coding: utf-8 -*-
"""并发复现/回归脚本：N 线程混合读写，统计状态码"""
import json
import threading
import urllib.request
from collections import Counter

BASE = "http://localhost:8000"


def req(method, path, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json",
                                        "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return -1, str(e)


def main():
    _, body = req("POST", "/api/login", "", {"person_id": 1})
    token = json.loads(body)["token"]

    results = []
    lock = threading.Lock()

    def worker(i):
        for round_ in range(3):
            s, _ = req("GET", "/api/agents", token)
            with lock:
                results.append(("GET", s))
            s, _ = req("POST", "/api/workspaces/1/messages", token,
                       {"content": f"并发测试消息 t{i} r{round_}", "zone": "discussion"})
            with lock:
                results.append(("POST", s))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    codes = Counter(s for _, s in results)
    errors = [(m, s) for m, s in results if s >= 500 or s == -1]
    print("总请求:", len(results))
    print("状态码分布:", dict(codes))
    print("5xx/异常数:", len(errors))
    print("错误率: %.1f%%" % (len(errors) / len(results) * 100))


if __name__ == "__main__":
    main()
