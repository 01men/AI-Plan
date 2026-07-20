# -*- coding: utf-8 -*-
import json, urllib.request, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE='http://127.0.0.1:8000'
T='c51cb228793f468192f960fb12ab45f2'

def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE+path, data=data, method=method,
        headers={'Authorization':'Bearer '+T, 'Content-Type':'application/json'})
    with urllib.request.urlopen(r) as resp:
        return json.load(resp)

sc = req('GET','/api/scenarios')
items = sc if isinstance(sc,list) else sc.get('items', sc.get('scenarios',[]))
pending = [s for s in items if s.get('status')=='待立项']
with_agent = [s for s in pending if s.get('agent_id')]
print('待立项总数:', len(pending), '| 其中关联了数字员工的:', len(with_agent))
for s in with_agent[:10]:
    print('  ', s['id'], s['name'], '-> agent_id', s['agent_id'])

# 看试点场景(已试点)的 agent_id 做对照
pilots = [s for s in items if s.get('status')=='试点中']
print('\n试点中场景 agent 关联:')
for s in pilots:
    print('  ', s['id'], s['name'], '-> agent_id', s.get('agent_id'))

# 数字员工列表：董事办/dept1 有没有可用员工
ag = req('GET','/api/agents')
agents = ag if isinstance(ag,list) else ag.get('items', ag.get('agents',[]))
print('\n数字员工总数:', len(agents))
d1 = [a for a in agents if a.get('dept_id')==1]
print('董事办(dept 1)的数字员工:', [(a['id'],a['name'],a.get('status')) for a in d1])
