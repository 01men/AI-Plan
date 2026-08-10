import concurrent.futures
import tempfile
from pathlib import Path

from app.config import Config
from app.database import init_db, session
from app.security import PolicyError, verify_token
from app.service import ControlPlane


def test_sqlite_concurrent_idempotency_and_signed_scope():
    """SQLite 单实例下并发重复请求只能创建一个业务契约。"""
    with tempfile.TemporaryDirectory() as d:
        config=Config(db_path=Path(d)/'db.sqlite',signing_key='nonfunctional-key')
        init_db(config.db_path); p=ControlPlane(config)
        resource=p.register({'type':'agent','name':'离线资源','owner':'测试','endpoint':'http://127.0.0.1:1','execution_domain':'remote'},'管理员')
        with session(config.db_path) as conn: conn.execute("UPDATE resources SET status='enabled' WHERE id=?",(resource['id'],)); conn.commit()
        def create(_):
            return p.create_contract({'idempotency_key':'concurrent-one','subject':'并发防重','resource_id':resource['id'],'role':'PMO','skills':[],'tools':[{'tier':'T0'}],'data_scope':[{'ref':'masked:1','level':'L1'}],'write_policy':'forbid'},'项目经理')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(create,range(8)))
        ids={r['contract']['id'] if r['idempotent'] else r['contract_id'] for r in results}
        assert len(ids)==1
        contract=p.contract(ids.pop())
        claims=verify_token(contract['authorization'],config.signing_key,config.issuer)
        assert claims['contract_id']==contract['id'] and 'masked:1' not in contract['authorization']
        try: verify_token(contract['authorization']+'x',config.signing_key,config.issuer)
        except PolicyError: pass
        else: raise AssertionError('篡改令牌必须被拒绝')


def test_outbox_failure_retries_then_dead_letters():
    with tempfile.TemporaryDirectory() as d:
        config=Config(db_path=Path(d)/'db.sqlite',signing_key='dlq-key')
        init_db(config.db_path); p=ControlPlane(config)
        resource=p.register({'type':'agent','name':'故障远端','owner':'测试','endpoint':'http://127.0.0.1:1','execution_domain':'remote'},'管理员')
        with session(config.db_path) as conn: conn.execute("UPDATE resources SET status='enabled' WHERE id=?",(resource['id'],)); conn.commit()
        c=p.create_contract({'idempotency_key':'dlq-one','subject':'故障注入','resource_id':resource['id'],'role':'PMO','skills':[],'tools':[{'tier':'T0'}],'data_scope':[{'level':'L1'}],'write_policy':'forbid'},'项目经理')
        for _ in range(3):
            p.process_outbox()
            with session(config.db_path) as conn: conn.execute("UPDATE dispatch_outbox SET available_at='2000-01-01T00:00:00+00:00' WHERE contract_id=?",(c['contract_id'],)); conn.commit()
        assert p.contract(c['contract_id'])['state']=='Degraded'
        with session(config.db_path) as conn: assert conn.execute('SELECT count(*) FROM dead_letters').fetchone()[0]==1
