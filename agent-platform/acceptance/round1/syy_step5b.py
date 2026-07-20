# -*- coding: utf-8 -*-
import json, urllib.request, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE='http://127.0.0.1:8000'
T='c51cb228793f468192f960fb12ab45f2'
LOCK_COUNT=0

def req(method, path, body=None, retry=1):
    global LOCK_COUNT
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE+path, data=data, method=method,
        headers={'Authorization':'Bearer '+T, 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')
        if e.code==500 and 'locked' in txt and retry>0:
            LOCK_COUNT+=1
            print(f'  [database is locked 重试 #{LOCK_COUNT}] {method} {path}')
            time.sleep(0.5)
            return req(method, path, body, retry-1)
        print(f'  HTTP {e.code}: {txt[:400]}')
        return e.code, txt

print('=== 步骤5重试: 申报火花奖(nominee字段) ===')
code, r = req('POST','/api/governance/incentives', {
    'type':'火花奖',
    'nominee':'师圆圆',
    'reason':'经营数据日报自动生成场景敏捷立项并完成首单派活-审核闭环，验证扩围场景可复制路径，申报火花奖',
    'amount': 800
})
print('申报返回:', code)
print(json.dumps(r, ensure_ascii=False, indent=1)[:1200])

_, inc2 = req('GET','/api/governance/incentives')
items = inc2 if isinstance(inc2,list) else inc2.get('items',[])
mine = [it for it in items if it.get('nominee')=='师圆圆']
print('\n我的申报记录数:', len(mine))
for it in mine:
    print(' ', json.dumps(it, ensure_ascii=False)[:300])
print('\nLOCK_COUNT =', LOCK_COUNT)
