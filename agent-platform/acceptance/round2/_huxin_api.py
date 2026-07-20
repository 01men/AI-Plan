import urllib.request, json, sys, time

BASE = 'http://127.0.0.1:8000'
TOKEN = 'dd9be2621b2e43d3a1184ce7a1508545'
ERR500 = 0

def api(method, path, body=None):
    global ERR500
    data = None
    headers = {'Authorization': 'Bearer ' + TOKEN}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req) as r:
            dt = time.time() - t0
            return r.status, json.loads(r.read().decode('utf-8')), dt
    except urllib.error.HTTPError as e:
        dt = time.time() - t0
        if e.code >= 500:
            ERR500 += 1
        try:
            return e.code, json.loads(e.read().decode('utf-8')), dt
        except Exception:
            return e.code, None, dt

if __name__ == '__main__':
    method, path = sys.argv[1], sys.argv[2]
    body = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    st, r, dt = api(method, path, body)
    print(st, f'{dt:.2f}s')
    print(json.dumps(r, ensure_ascii=False, indent=1)[:3000])
