import json
from types import SimpleNamespace

import pytest

from deploy.render_operator_units import render, SERVICES
from scripts import native_operator_unit_verification as runner
from test_operator_unit_rendering import inputs


def prepared(tmp_path):
    import sys
    source, metadata, configs = inputs(tmp_path)
    units = tmp_path/'units'
    render(str(source), sys.executable, metadata, configs, 'mldsafail', 1001, str(units))
    return source, metadata, units


def test_native_unit_verification_never_installs_or_starts(monkeypatch, tmp_path):
    source, metadata, units = prepared(tmp_path)
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    calls, stopped = [], []
    def command(argv, clients, save, evidence, **kwargs):
        calls.append(argv)
        clients.append({'id': str(len(calls))})
        save()
        if argv[0] != 'systemd-analyze':
            kwargs['stdout'].write(json.dumps({'python': '3.12.10', 'modules': {entry[0]: str(source/(entry[0].replace('.', '/')+'.py')) for entry in SERVICES.values()}}).encode())
        assert 'PYTHONHOME' not in kwargs['env']
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runner.owned_client, 'run', command)
    monkeypatch.setattr(runner.owned_client, 'stop', lambda entry: stopped.append(entry))
    report = runner.verify(units, metadata, tmp_path/'evidence')
    assert report['complete'] and report['cleanup_complete']
    assert not report['installed'] and not report['activated']
    assert calls[-1][0:2] == ['systemd-analyze', 'verify']
    assert len(stopped) == 2


def test_changed_source_prevents_native_commands(monkeypatch, tmp_path):
    source, metadata, units = prepared(tmp_path)
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    (source/'deploy/helper.py').write_text('changed')
    monkeypatch.setattr(runner.owned_client, 'run', lambda *a, **kw: pytest.fail('must not execute mismatched source'))
    with pytest.raises(ValueError, match='module identity'):
        runner.verify(units, metadata, tmp_path/'evidence')
    report = json.loads((tmp_path/'evidence/verification.json').read_text())
    assert report['complete'] is False and report['cleanup_complete']
