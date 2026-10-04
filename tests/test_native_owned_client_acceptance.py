import json
from pathlib import Path
import pytest
from deploy import native_owned_client_acceptance as native


def test_native_fixture_refuses_other_platform_before_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(native.sys, 'platform', 'darwin')
    with pytest.raises(RuntimeError, match='Native Linux'):
        native.execute(tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_native_cleanup_independently_attempts_both_journals(tmp_path, monkeypatch):
    root = tmp_path / 'before-release'; root.mkdir()
    for filename, identifier in [('fixture-owner.json', 'controller'), ('ownership.json', 'client')]:
        (root / filename).write_text(json.dumps({'clients': [{'id': identifier}]}))
        (root / filename).chmod(0o600)
    seen = []
    def stop(entry):
        seen.append(entry['id'])
        if entry['id'] == 'controller': raise RuntimeError('injected')
    monkeypatch.setattr(native.owned_client, 'stop', stop)
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        native.cleanup(tmp_path)
    assert seen == ['controller', 'client']
    receipt = json.loads(list(tmp_path.glob('cleanup-*.json'))[0].read_text())
    assert not receipt['cleanup_complete']
    assert receipt['errors'][0]['client'] == 'controller'
    monkeypatch.setattr(native.owned_client, 'stop', lambda entry: None)
    assert native.cleanup(tmp_path)['cleanup_complete']
    assert len(list(tmp_path.glob('cleanup-*.json'))) == 2


def test_nested_fixture_program_compiles(tmp_path, monkeypatch):
    seen = []
    def inspect(argv, *args, **kwargs):
        compile(argv[2], '<native-leader>', 'exec')
        # Parse literal nested code without executing any fixture.
        import ast
        tree = ast.parse(argv[2])
        nested = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'Popen')
        code = nested.args[0].elts[2].value
        compile(code, '<native-grandchild>', 'exec')
        seen.append(True)
    monkeypatch.setattr(native.owned_client, 'run', inspect)
    native.owner(tmp_path, False)
    assert seen == [True]
