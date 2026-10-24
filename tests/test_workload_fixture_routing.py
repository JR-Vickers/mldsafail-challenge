"""Real PostgreSQL fence tests only on an explicitly provisioned disposable DB."""
import os
import time
from pathlib import Path
import pytest
from sqlalchemy import create_engine,inspect
from sqlalchemy.engine import make_url
from deploy.workload_fixture_routing import ADMIN_CASES,administrative_case
from deploy.workload_routing_fixture import InertController
from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.web.models import Base
from deploy.workload_controls import SCENARIOS


class AdministrativeRuntime(InertController):
    def result(self,state):
        return sign_envelope(dict(binding=dict(workload_id=state['workload_id'],role='inert',reference=state['reference']),
            status='administrative_complete',result=dict(fixture_only=True,verified=True)),b'k'*32)


@pytest.fixture
def database():
    value=os.environ.get('MLDSAFAIL_NATIVE_TEST_DATABASE_URL')
    if not value:pytest.skip('explicit empty loopback disposable PostgreSQL required')
    url=make_url(value)
    assert url.get_backend_name()=='postgresql' and url.host=='127.0.0.1' and url.database.startswith('mldsafail_acceptance_')
    engine=create_engine(url)
    assert not inspect(engine).get_table_names()
    class Database:
        identifier='test-harness-owned-disposable-container'
        def engine(self):return engine
        def connect(self):
            import psycopg
            return psycopg.connect(host=url.host,port=url.port,user=url.username,password=url.password,dbname=url.database,
                autocommit=True,connect_timeout=1,options='-c statement_timeout=500 -c lock_timeout=500')
        def inspect(self):return {'Id':self.identifier}
    try:yield Database()
    finally:Base.metadata.drop_all(engine);engine.dispose()


@pytest.mark.parametrize('control,scenario',sorted(ADMIN_CASES))
def test_actual_administrative_routing_and_fence(database,tmp_path,control,scenario):
    receipt=administrative_case(control,scenario,tmp_path/'routing',database,AdministrativeRuntime,time.monotonic()+90)
    assert all(receipt['observations'][key]==value for key,value in SCENARIOS[control][scenario].items())
    assert receipt['raw']['outcomes']
    assert all(outcome['fence_state']['client_terminated'] for outcome in receipt['raw']['outcomes'])
    if scenario=='host_gate_before_fence':
        assert receipt['raw']['outcomes'][0]['processes']
    else:
        assert all(outcome['before']==outcome['after'] for outcome in receipt['raw']['outcomes'])
