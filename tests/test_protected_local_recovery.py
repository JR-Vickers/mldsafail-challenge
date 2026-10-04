import sys
import pytest
from deploy.restore_recovery import normalized_sql_dump


def test_dump_normalization_preserves_comment_shaped_private_copy_rows():
    left = b'-- generated\n\\restrict random\nCOPY users FROM stdin;\n-- actual private row\n\\restrict actual data\n\\.\n\\unrestrict random\n'
    right = left.replace(b'-- generated', b'-- another').replace(b'random', b'nonce')
    assert normalized_sql_dump(left) == normalized_sql_dump(right)
    assert b'-- actual private row' in normalized_sql_dump(left)
    assert normalized_sql_dump(left) != normalized_sql_dump(left.replace(b'private row', b'changed row'))


def test_incomplete_copy_rejected():
    with pytest.raises(ValueError, match='Incomplete COPY'):
        normalized_sql_dump(b'COPY users FROM stdin;\nrow')


def test_legacy_restore_flag_rejected_before_directory_or_command(tmp_path, monkeypatch):
    from deploy import backup_postgres
    monkeypatch.setattr(sys, 'argv', ['backup', '--env-file', '/unused', '--output', str(tmp_path / 'out'), '--verify-restore'])
    monkeypatch.setattr(backup_postgres.subprocess, 'run', lambda *a, **k: pytest.fail('command admitted'))
    with pytest.raises(SystemExit) as error: backup_postgres.main()
    assert error.value.code == 2
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('answer', ['1\n', '', 'ERROR\n'])
def test_stopped_coordinator_not_started_before_verified_idle_queue(tmp_path, monkeypatch, answer):
    from deploy.assemble_recovery import assemble
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        if 'ps' in argv: return argv[-1]
        if 'inspect' in argv: return '{"Running":false}'
        if 'psql' in argv: return answer
        return ''
    monkeypatch.setattr('deploy.assemble_recovery.subprocess.check_output', command)
    monkeypatch.setattr('deploy.recovery_journal.subprocess.run', lambda argv, **kw: calls.append(argv))
    from deploy.recovery_journal import Journal
    from types import SimpleNamespace
    from tests.test_recovery_tools import _mock_owned_run
    operation = Journal(tmp_path / 'operation.json', {})
    operation.command = lambda argv, **kwargs: SimpleNamespace(stdout=command(argv, **kwargs))
    monkeypatch.setattr('deploy.owned_client.run', _mock_owned_run)
    with pytest.raises(RuntimeError, match='unverified'):
        assemble({'env_file': '/private/env', 'compose': '/private/compose'}, tmp_path / 'set', operation=operation)
    assert ['docker', 'container', 'start', 'coordinator'] not in calls
    query = next(argv for argv in calls if 'psql' in argv)
    assert 'BEGIN READ ONLY' in query[-1]
    assert "'queued','claimed','running'" in query[-1]


def test_local_callback_preserves_failure_and_independently_cleans(tmp_path, monkeypatch):
    import hashlib
    import json
    from types import SimpleNamespace
    from scripts import native_protected_local_restoration as runner
    sealed = tmp_path / 'sealed'
    sealed.mkdir(mode=0o700)
    manifest = sealed / 'recovery.json'
    manifest.write_text('{}'); manifest.chmod(0o600)
    protocol = tmp_path / 'protocol.json'
    protocol.write_text(json.dumps(dict(schema='mldsafail.local-protected-restore-protocol.v1',
        recovery_set=str(sealed), manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        epoch_id='expected', result_count=1, coordinator_image='sha256:'+'a'*64)))
    protocol.chmod(0o600)
    cleanup = []
    class Journal:
        def __init__(self, *a): self.data = {}
        def cleanup(self): cleanup.append(True); self.data['cleanup_complete'] = True
    original = RuntimeError('actual verification failed')
    monkeypatch.setattr(runner, 'Journal', Journal)
    def fail(*a, **kw):
        assert kw['local_set'] is True
        raise original
    monkeypatch.setattr(runner, 'verify', fail)
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', '/private/owned')
    with pytest.raises(RuntimeError) as error:
        runner.callback(SimpleNamespace(path=tmp_path/'driver.json'),
            {'acceptance_protocol':str(protocol),'image':'sha256:'+'b'*64},
            {'loaded_images':['sha256:'+'a'*64,'sha256:'+'b'*64]})
    assert error.value is original and cleanup == [True]
    outcome = json.loads((tmp_path/'protected-local-restoration/result.json').read_text())
    assert outcome['passed'] is False and outcome['native_executed'] is False
    assert outcome['cleanup_complete'] is True and outcome['offhost_verified'] is False


def test_assembly_without_durable_ownership_rejected_before_mutation(tmp_path):
    from deploy.assemble_recovery import assemble
    with pytest.raises(ValueError, match='Durable operator'):
        assemble({}, tmp_path / 'set')
    assert not (tmp_path / 'set').exists()


@pytest.mark.parametrize('delimiter', [b'$$', b'$body$'])
def test_function_body_comment_shaped_content_is_not_normalized(delimiter):
    original = b'CREATE FUNCTION f() RETURNS text AS '+delimiter+b'\n-- stored body\nSELECT 1;\n'+delimiter+b' LANGUAGE sql;'
    changed = original.replace(b'-- stored body', b'-- changed body')
    assert normalized_sql_dump(original) != normalized_sql_dump(changed)
    assert b'-- stored body' in normalized_sql_dump(original)


def test_restore_callback_rejects_unbound_archive_before_output(tmp_path):
    import json
    from types import SimpleNamespace
    from scripts.native_protected_local_restoration import callback
    protocol = tmp_path / 'protocol.json'
    protocol.write_text(json.dumps(dict(schema='mldsafail.local-protected-restore-protocol.v1',
        recovery_set='/unopened',manifest_sha256='a'*64,epoch_id='expected',result_count=1,
        coordinator_image='sha256:'+'a'*64)))
    protocol.chmod(0o600)
    with pytest.raises(ValueError, match='archive provenance'):
        callback(SimpleNamespace(path=tmp_path/'driver.json'),
            {'acceptance_protocol':str(protocol),'image':'sha256:'+'b'*64},
            {'loaded_images':['sha256:'+'b'*64]})
    assert not (tmp_path/'protected-local-restoration').exists()
