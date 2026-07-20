# -*- coding: utf-8 -*-
# 范丁鑫 round2 并发回归：20线程混合读写（GET /api/agents + POST 工作区消息）× 3轮
import urllib.request, urllib.error, json, threading, time, collections

BASE = 'http://127.0.0.1:8000'
TOKEN = 'e988cc9eff6347f6bef4857229d56531'
WID = 1
THREADS = 20
OPS_PER_THREAD = 10  # 5读 + 5写 交替
ROUNDS = 3

def do_get():
    r = urllib.request.Request(BASE + '/api/agents',
        headers={'Authorization': 'Bearer ' + TOKEN})
    try:
        with urllib.request.urlopen(r) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__

def do_post(i, j):
    body = {'content': '并发回归测试 t%d-op%d' % (i, j)}
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    r = urllib.request.Request(BASE + '/api/workspaces/%d/messages' % WID, data=data,
        method='POST',
        headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__

def worker(i, results):
    for j in range(OPS_PER_THREAD):
        code = do_get() if j % 2 == 0 else do_post(i, j)
        results.append(code)

for rnd in range(1, ROUNDS + 1):
    results = []
    threads = [threading.Thread(target=worker, args=(i, results)) for i in range(THREADS)]
    t0 = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    dt = time.time() - t0
    c = collections.Counter(results)
    total = len(results)
    n500 = c.get(500, 0)
    print('第%d轮: 总请求=%d 耗时=%.2fs 状态分布=%s  500数=%d (%.1f%%)' % (
        rnd, total, dt, dict(sorted(c.items(), key=lambda kv: str(kv[0]))), n500, 100.0*n500/total))
