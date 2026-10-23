import hashlib
import io
import json
from pathlib import Path

import pytest
from deploy import privileged_scheduling as collector
from deploy.production_maintenance import privileged_receipt, packet_state


@pytest.mark.parametrize('kind', ['alias', 'wants', 'mask'])
def test_link_targets(tmp_path, kind):
    target = tmp_path / 'service'
    target.write_text('[Service]')
    link = tmp_path / kind
    link.symlink_to('/dev/null' if kind == 'mask' else target.name)
    row = collector.inspect_path(link)
    assert 'error' not in row
    assert row['chain'][0]['literal_target'] == ('/dev/null' if kind == 'mask' else target.name)
    assert row['mask'] == (kind == 'mask')
    if kind != 'mask':
        assert row['sha256'] == hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.parametrize('kind', ['loop', 'dangling', 'large', 'hops'])
def test_bad_targets(tmp_path, kind):
    p = tmp_path / 'a'
    if kind == 'loop': p.symlink_to('a')
    if kind == 'dangling': p.symlink_to('missing')
    if kind == 'large': p.write_bytes(b'x' * (collector.MAX_FILE + 1))
    if kind == 'hops':
        for i in range(18): (tmp_path / str(i)).symlink_to(str(i+1))
        p.symlink_to('0')
    assert 'error' in collector.inspect_path(p)


def test_target_replaced(tmp_path, monkeypatch):
    p = tmp_path / 'file'; p.write_text('original')
    original = Path.open
    # Mutate at the read boundary without recursively using the patched writer.
    def replaced(self, *a, **kw):
        if self == p:
            self.unlink()
            with original(self, 'w') as stream: stream.write('changed')
        return original(self, *a, **kw)
    monkeypatch.setattr(Path, 'open', replaced)
    assert 'error' in collector.inspect_path(p)


def test_collection_limits_and_secret_free(tmp_path, monkeypatch):
    root = tmp_path / 'root'; root.mkdir()
    (root / 'one').write_text('secret')
    (root / 'two').write_text('secret')
    monkeypatch.setattr(collector, 'ROOTS', (str(root),))
    monkeypatch.setattr(collector, 'MAX_ENTRIES', 1)
    monkeypatch.setattr(collector, 'SECTIONS', {'root_crontab': ['ignored']})
    def run(command, stdout, stderr, timeout, **kwargs):
        stdout.write(b'SUPER_SECRET_CRON')
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(collector.subprocess, 'run', run)
    raw = io.BytesIO(); c = collector.collect('hash', raw)
    assert not c['complete']
    assert 'SUPER_SECRET_CRON' not in json.dumps(c)
    assert b'SUPER_SECRET_CRON'.hex().encode() in raw.getvalue()


def reviewed(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, 'ROOTS', ('/absent',))
    monkeypatch.setattr(collector, 'SECTIONS', {'at_queue': ['atq']})
    raw = json.dumps(dict(section='at_queue', stdout='', stderr=''), sort_keys=True).encode()+b'\n'
    raw_path = tmp_path/'raw'; raw_path.write_bytes(raw); raw_path.chmod(0o600)
    paths = [dict(path='/absent', absent=True)]
    c = dict(schema='mldsafail.scheduling-collection.v2', host='host', uid=0,
             collector_sha256='hash', provenance='owner_root_console', time=1000,
             complete=True, reviewed_paths=[], paths=paths,
             raw_sha256=hashlib.sha256(raw).hexdigest(),
             sections={'at_queue': dict(command=['atq'], error=None, returncode=0,
                truncated=False, raw_sha256=hashlib.sha256(raw).hexdigest(),
                sha256=hashlib.sha256(b'').hexdigest())})
    cp = tmp_path/'collection'; cp.write_text(json.dumps(c)); cp.chmod(0o600)
    r = dict(schema='mldsafail.privileged-scheduling.v2', collection=str(cp),
             collection_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),
             raw_evidence=str(raw_path), raw_sha256=c['raw_sha256'], at_state='installed_and_inspected',
             classifications=[dict(path='/absent', evidence_sha256=hashlib.sha256(json.dumps(paths[0],sort_keys=True).encode()).hexdigest(),
                disposition='absent', rationale='not installed', references=[], references_reviewed=True)])
    return r


def test_v2_review_binding(tmp_path, monkeypatch):
    r = reviewed(tmp_path, monkeypatch)
    assert privileged_receipt(r, 'host', 'hash', now=1100) == 'installed_and_inspected'
    r['classifications'] = []
    with pytest.raises(ValueError): privileged_receipt(r, 'host', 'hash', now=1100)


@pytest.mark.parametrize('mutation', ['raw', 'source', 'host', 'stale', 'classification'])
def test_v2_rejects(tmp_path, monkeypatch, mutation):
    r = reviewed(tmp_path, monkeypatch)
    host, source, now = 'host', 'hash', 1100
    if mutation == 'raw': Path(r['raw_evidence']).write_text('changed')
    if mutation == 'source': source = 'changed'
    if mutation == 'host': host = 'changed'
    if mutation == 'stale': now = 1400
    if mutation == 'classification': r['classifications'][0]['evidence_sha256'] = 'changed'
    with pytest.raises(ValueError): privileged_receipt(r, host, source, now=now, execution=True)


def test_v3_proposal_blocked():
    p = dict(schema='mldsafail.production-operation.v3', state='maintenance_proposal')
    packet_state(p, dict(scheduling_exclusion_verified=False))
    with pytest.raises(ValueError): packet_state(p, dict(scheduling_exclusion_verified=False), execution=True)


def test_permission_failure(tmp_path, monkeypatch):
    p = tmp_path/'denied'; p.write_text('x')
    original = Path.lstat
    def denied(self):
        if self == p: raise PermissionError('denied')
        return original(self)
    monkeypatch.setattr(Path, 'lstat', denied)
    assert collector.inspect_path(p)['error'] == 'PermissionError'


def test_missing_at_raw_record(monkeypatch):
    monkeypatch.setattr(collector, 'ROOTS', ())
    monkeypatch.setattr(collector, 'SECTIONS', {'at_queue': ['missing']})
    def missing(*args, **kwargs): raise FileNotFoundError()
    monkeypatch.setattr(collector.subprocess, 'run', missing)
    raw = io.BytesIO(); c = collector.collect('hash', raw)
    assert json.loads(raw.getvalue())['error'] == 'FileNotFoundError'
    assert c['sections']['at_queue']['error'] == 'FileNotFoundError'


def test_deadline_not_swallowed_inside_path(tmp_path, monkeypatch):
    def interrupted(self):
        raise collector.CollectionDeadline('collection_deadline')
    monkeypatch.setattr(Path, 'lstat', interrupted)
    with pytest.raises(collector.CollectionDeadline):
        collector.inspect_path(tmp_path/'file')


def test_collection_deadline_is_incomplete(monkeypatch):
    def interrupted(*args, **kwargs):
        raise collector.CollectionDeadline('collection_deadline')
    monkeypatch.setattr(collector, '_collect', interrupted)
    assert collector.collect('hash', io.BytesIO())['complete'] is False


def test_nonzero_observation_cannot_claim_complete(monkeypatch):
    monkeypatch.setattr(collector, 'ROOTS', ())
    monkeypatch.setattr(collector, 'SECTIONS', {'system_units': ['systemctl']})
    def denied(command, stdout, stderr, **kwargs):
        stderr.write(b'Access denied')
        return type('Result', (), {'returncode': 1})()
    monkeypatch.setattr(collector.subprocess, 'run', denied)
    result = collector.collect('hash', io.BytesIO())
    assert result['complete'] is False


@pytest.mark.parametrize('nested', [False, True])
def test_valid_symlink_parent_with_missing_optional_child(tmp_path, nested):
    target = tmp_path/'usr'; target.mkdir()
    (target/'bin').mkdir()
    link = tmp_path/'bin'; link.symlink_to('usr/bin')
    if nested:
        other = tmp_path/'other'; other.symlink_to('bin')
        link = other
    row = collector.inspect_path(link/'optional'/'child')
    assert row['absent'] is True
    assert 'error' not in row
    assert row['chain']


def test_dangling_parent_is_not_optional_absence(tmp_path):
    link = tmp_path/'bin'; link.symlink_to('missing')
    row = collector.inspect_path(link/'optional')
    assert row['error'] == 'dangling_target'
    assert 'absent' not in row


@pytest.mark.parametrize('failure', ['absent', 'permission', 'dangling'])
def test_failed_lookup_rechecks_traversed_identities(tmp_path, monkeypatch, failure):
    target = tmp_path/'target'; target.mkdir()
    link = tmp_path/'link'; link.symlink_to('target' if failure != 'dangling' else 'missing')
    original = Path.lstat
    mutated = False
    def raced(self):
        nonlocal mutated
        if self == tmp_path/('missing' if failure == 'dangling' else 'target/child') and not mutated:
            mutated = True
            link.unlink(); link.symlink_to('replacement')
            if failure == 'permission': raise PermissionError()
            raise FileNotFoundError()
        return original(self)
    monkeypatch.setattr(Path, 'lstat', raced)
    row = collector.inspect_path(link/'child')
    assert mutated
    assert row['error'] == 'target_changed'
    assert 'absent' not in row


def test_absence_becoming_present_is_a_race(tmp_path, monkeypatch):
    p = tmp_path/'missing'; original = Path.lstat
    def raced(self):
        if self == p and not p.exists():
            p.write_text('new')
            raise FileNotFoundError()
        return original(self)
    monkeypatch.setattr(Path, 'lstat', raced)
    assert collector.inspect_path(p)['error'] == 'target_changed'


def at_absence_fixture():
    sections = dict(at_queue=dict(error='FileNotFoundError'),
        at_service=dict(error=None, returncode=0, truncated=False, not_found=True, inactive=True),
        processes=dict(error=None, returncode=0, truncated=False, at_daemon_seen=False))
    paths = [dict(path=name, absent=True) for name in (*collector.AT_EXECUTABLES, *collector.AT_SPOOLS)]
    return sections, paths


def test_missing_atq_requires_correlated_observations():
    assert not collector.at_observation({'at_queue': dict(error='FileNotFoundError')}, [])['missing_utility_corroborated']
    sections, paths = at_absence_fixture()
    assert collector.at_observation(sections, paths)['missing_utility_corroborated']


@pytest.mark.parametrize('failure', ['unreadable', 'spool', 'executable', 'service', 'process', 'truncated', 'omitted'])
def test_at_absence_rejects_incomplete_or_conflicting_inventory(failure):
    sections, paths = at_absence_fixture()
    if failure == 'unreadable': paths[-1]['error'] = 'PermissionError'
    if failure == 'spool': paths[-1].pop('absent')
    if failure == 'executable': paths[0].pop('absent')
    if failure == 'service': sections['at_service']['inactive'] = False
    if failure == 'process': sections['processes']['at_daemon_seen'] = True
    if failure == 'truncated': sections['processes']['truncated'] = True
    if failure == 'omitted': paths.pop()
    assert not collector.at_observation(sections, paths)['missing_utility_corroborated']


def test_link_target_dotdot_follows_intermediate_link_before_parent(tmp_path):
    (tmp_path/'real').mkdir(); (tmp_path/'real'/'sub').mkdir()
    (tmp_path/'real'/'file').write_text('kernel target')
    (tmp_path/'file').write_text('wrong lexical target')
    (tmp_path/'intermediate').symlink_to('real/sub')
    link = tmp_path/'link'; link.symlink_to('intermediate/../file')
    row = collector.inspect_path(link)
    assert row['sha256'] == hashlib.sha256(link.read_bytes()).hexdigest()
    assert row['final_target'] == str(tmp_path/'real'/'file')


def test_link_can_be_traversed_again_after_resolution(tmp_path):
    (tmp_path/'target').mkdir()
    (tmp_path/'target'/'file').write_text('target')
    link = tmp_path/'link'; link.symlink_to('target')
    outer = tmp_path/'outer'; outer.symlink_to('link/../link/file')
    assert 'error' not in collector.inspect_path(outer)


def test_dotdot_cannot_cross_a_regular_file(tmp_path):
    (tmp_path/'file').write_text('data')
    link = tmp_path/'link'; link.symlink_to('file/../file')
    assert collector.inspect_path(link)['error'] == 'NotADirectoryError'


def test_successor_scheduling_commands_use_containment_and_cannot_hide_failure(monkeypatch):
    monkeypatch.setattr(collector, 'ROOTS', ())
    monkeypatch.setattr(collector, 'SECTIONS', {'test': ['systemctl', 'show']})
    calls = []
    def runner(command, **kw):
        calls.append(command)
        return dict(returncode=0, stdout=b'', stderr=b'',
                    containment=dict(verified=False, retained_evidence='/private/receipt'))
    c = collector.collect('hash', io.BytesIO(), command_runner=runner)
    assert calls == [['systemctl', 'show']]
    assert not c['complete']
    assert c['sections']['test']['error'] == 'command_containment_unverified'
    assert c['sections']['test']['containment']['retained_evidence'] == '/private/receipt'


def test_literal_input_dotdot_is_resolved_after_parent_symlink(tmp_path):
    (tmp_path/'real').mkdir(); (tmp_path/'real'/'sub').mkdir()
    (tmp_path/'real'/'file').write_text('kernel target')
    (tmp_path/'file').write_text('wrong lexical target')
    (tmp_path/'link').symlink_to('real/sub')
    literal = tmp_path/'link'/'..'/'file'
    row = collector.inspect_path(literal)
    assert row['sha256'] == hashlib.sha256(literal.read_bytes()).hexdigest()
