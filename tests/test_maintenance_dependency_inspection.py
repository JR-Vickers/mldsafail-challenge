from scripts import maintenance_dependency_inspection as inspection
import pytest


def test_dependency_inspection_does_not_expand_dynamic_paths_or_import(monkeypatch, tmp_path):
    module = tmp_path/'dangerous.py'
    module.write_text("raise RuntimeError('must never import inspected code')\n")
    monkeypatch.setattr(inspection.sys, 'path', [str(tmp_path)])
    result = inspection.inspect(dict(paths=['/etc/$DYNAMIC', '/etc/*.conf'], commands=['nonexistent-maintenance-command'], imports=['dangerous']))
    assert all(r['status'] == 'dynamic_or_invalid_not_inspected' for r in result['paths'].values())
    assert result['imports']['dangerous']['static_candidates'][0]['evidence']['sha256']
    assert result['imports']['dangerous']['resolved'] is False
    assert result['commands']['nonexistent-maintenance-command']['resolved'] is None


def test_dependency_request_bounds_and_literal_commands():
    for request in (dict(paths=['/tmp']*513, commands=[], imports=[]),
                    dict(paths=[], commands=['sh; false'], imports=[]),
                    dict(paths=[], commands=[], imports=['pkg;false'])):
        with pytest.raises(ValueError): inspection.inspect(request)
