import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.config import Config
from app.database import init_db
from app.service import ControlError, ControlPlane


class Agent(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *args): pass
    def _send(self, payload):
        raw=json.dumps(payload).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path == '/.well-known/agent-card.json': return self._send({'name':'真实联调测试 Agent','version':'1.0','capabilities':['meeting_minutes_to_actions'],'skills':['pmo.readonly']})
        if self.path.startswith('/a2a/tasks/'): return self._send({'state':'running'})
        self.send_error(404)
    def do_POST(self):
        length=int(self.headers.get('content-length','0')); payload=json.loads(self.rfile.read(length) or '{}'); Agent.calls.append((self.path,payload))
        if self.path == '/a2a/tasks': return self._send({'run_id':'remote-real-001'})
        return self._send({'ok':True})


@pytest.fixture()
def plane():
    server=ThreadingHTTPServer(('127.0.0.1',0),Agent); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    with tempfile.TemporaryDirectory() as d:
        config=Config(db_path=Path(d)/'control.db',signing_key='test-key',worker_interval_seconds=60)
        init_db(config.db_path); yield ControlPlane(config),f'http://127.0.0.1:{server.server_port}'
    server.shutdown(); thread.join()


def ready_resource(p, endpoint):
    r=p.register({'type':'agent','name':'PMO 纪要 Agent','owner':'数字化中心','endpoint':endpoint,'execution_domain':'remote','adapter':'native_a2a'},'管理员')
    p.discover(r['id'],'管理员'); p.sandbox_validate(r['id'],'管理员')
    ticket=p.create_ticket({'level':'L1','reason':'试点资源启用'},'管理员'); p.decide_ticket(ticket['id'],'安全负责人',True); p.enable(r['id'],'管理员',ticket['id'])
    return r['id']


def test_real_http_agent_card_to_review_and_rework(plane):
    p, endpoint=plane; rid=ready_resource(p,endpoint)
    ticket=p.create_ticket({'level':'L1','reason':'建议必须审核'},'项目经理'); p.decide_ticket(ticket['id'],'审核人',True)
    c=p.create_contract({'idempotency_key':'minutes-20260807-001','subject':'经营例会行动项','resource_id':rid,'role':'经营 PMO 助理','skills':['pmo.readonly'],'tools':[{'name':'minutes_parser','tier':'T0'}],'data_scope':[{'ref':'meeting:2026-08-07','level':'L2'}],'write_policy':'suggest','approval_ticket_id':ticket['id'],'input_payload':{'minutes':'销售部本周补齐回款风险清单。'}},'项目经理')
    assert not c['idempotent']; assert p.process_outbox()[0]['ok']
    run=p.runs()[0]; assert run['external_run_id']=='remote-real-001'; assert p.contract(c['contract_id'])['state']=='Dispatched'
    assert p.receive_event(run['id'],{'event_id':'e1','sequence':1,'event_type':'started'})['state']=='Running'
    assert p.receive_event(run['id'],{'event_id':'e2','sequence':2,'event_type':'deliverable','artifact':'行动项：销售部 8 月 9 日前提交回款风险清单。','provenance':{'source':'meeting:2026-08-07'}})['state']=='Review'
    assert p.receive_event(run['id'],{'event_id':'e2','sequence':2,'event_type':'deliverable','artifact':'ignored'})['idempotent']
    assert p.review(c['contract_id'],'项目负责人',False,'请标注责任人')['state']=='Rework'
    assert p.process_outbox()[0]['ok']; assert p.contract(c['contract_id'])['state']=='Dispatched'


def test_policy_idempotency_ordering_and_degrade(plane):
    p, endpoint=plane; rid=ready_resource(p,endpoint)
    body={'idempotency_key':'same-key','subject':'风险检查','resource_id':rid,'role':'PMO','skills':[],'tools':[{'tier':'T0'}],'data_scope':[{'level':'L1'}],'write_policy':'forbid'}
    first=p.create_contract(body,'负责人'); second=p.create_contract(body,'负责人'); assert not first['idempotent'] and second['idempotent']
    with pytest.raises(ControlError,match='首期仅允许'):
        p.create_contract(dict(body,idempotency_key='l3',data_scope=[{'level':'L3'}]),'负责人')
    p.process_outbox(); run=p.runs()[0]
    p.receive_event(run['id'],{'event_id':'a','sequence':2,'event_type':'progress'})
    with pytest.raises(ControlError,match='乱序'):
        p.receive_event(run['id'],{'event_id':'old','sequence':1,'event_type':'started'})
    p.receive_event(run['id'],{'event_id':'f','sequence':3,'event_type':'failed','content':'远端离线'})
    assert p.contract(first['contract_id'])['state']=='Degraded'
    assert p.takeover(first['contract_id'],'项目负责人','人工完成行动项确认')['state']=='HumanTakeover'


def test_unbind_blocks_inflight_and_authorization_is_not_plain_scope(plane):
    p, endpoint=plane; rid=ready_resource(p,endpoint)
    c=p.create_contract({'idempotency_key':'unbind-1','subject':'行动','resource_id':rid,'role':'PMO','skills':[],'tools':[{'tier':'T0'}],'data_scope':[{'ref':'doc:1','level':'L1'}],'write_policy':'forbid'},'负责人')
    p.process_outbox()
    with pytest.raises(ControlError,match='在途任务'): p.unbind(rid,'管理员')
    assert 'doc:1' not in p.contract(c['contract_id'])['authorization']
