from __future__ import annotations

import json
import pytest

from mldsafail import cli


class Response:
    def __init__(self, payload, status_code=200): self.payload, self.status_code = payload, status_code
    def json(self): return self.payload


def test_login_validates_without_disclosing_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    stored = {}
    monkeypatch.setattr(cli.keyring, "set_password", lambda service, server, token: stored.update(token=token))
    monkeypatch.setattr(cli.keyring, "get_password", lambda service, server: stored.get("token"))
    monkeypatch.setattr(cli.requests, "request", lambda *a, **k: Response({"display_name": "Ada"}))
    token = "mldsa_0123456789_" + "a" * 43
    assert cli.main(["login", token, "--server", "https://challenge.test"]) == 0
    output = capsys.readouterr()
    assert "Ada" in output.out and token not in output.out + output.err
    assert json.loads(cli.config_path().read_text())["server"] == "https://challenge.test"
    assert cli.config_path().stat().st_mode & 0o777 == 0o600


def test_plaintext_fallback_requires_opt_in(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(cli.keyring, "set_password", lambda *a: (_ for _ in ()).throw(cli.NoKeyringError()))
    monkeypatch.setattr(cli.keyring, "get_password", lambda *a: None)
    monkeypatch.setattr(cli.requests, "request", lambda *a, **k: Response({"display_name": "Ada"}))
    token = "mldsa_0123456789_" + "a" * 43
    assert cli.main(["login", token, "--server", "https://challenge.test"]) == 2
    assert token not in capsys.readouterr().err
    assert cli.main(["login", token, "--server", "https://challenge.test", "--allow-plaintext-storage"]) == 0
    captured = capsys.readouterr()
    assert "warning" in captured.err and token not in captured.out + captured.err
    assert json.loads(cli.config_path().read_text())["token"] == token


def test_submit_and_status_use_bearer_without_printing_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cli._write_config({"server": "https://challenge.test", "token": "secret-token"})
    monkeypatch.setattr(cli.keyring, "get_password", lambda *a: None)
    calls = []
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/logs"): return Response({"logs": [{"attempt": 1, "status": "done", "text": "verified"}]})
        return Response({"submission": {"id": "submission-1", "state": "accepted"}})
    monkeypatch.setattr(cli.requests, "request", request)
    assert cli.main(["submit", "--repo", "https://github.com/a/b", "--commit", "a" * 40, "--hypothesis", "cache"]) == 0
    assert cli.main(["status", "submission-1"]) == 0
    output = capsys.readouterr().out
    assert "submission-1" in output and "secret-token" not in output
    assert all(call[2]["headers"]["Authorization"] == "Bearer secret-token" for call in calls)


def test_run_delegates_to_offline_benchmark(monkeypatch):
    seen = {}
    monkeypatch.setattr("mldsafail.development.main", lambda args: seen.setdefault("args", args) or 0)
    assert cli.main(["run", "--profile", "small", "--no-record"]) == ["develop", "--profile", "small", "--no-record"]


def test_supported_cli_rejects_legacy_and_requires_experiment_metadata():
    with pytest.raises(SystemExit) as legacy:
        cli.main(["clone", "--benchmark-version", "0.4.0"])
    assert legacy.value.code == 2
    with pytest.raises(SystemExit) as missing:
        cli.main(["run", "--solver-dir", "solver"])
    assert missing.value.code == 2


def test_default_scaffold_uses_approved_starter(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(cli, 'subprocess_run', lambda *a, **kw: None)
    workspace = tmp_path / 'workspace'
    assert cli.main(['clone', str(workspace)]) == 0
    assert (workspace / 'solver/solver.py').read_bytes() == (Path(__file__).resolve().parents[1] / 'examples/mlwe/primal-lll/solver.py').read_bytes()
    assert cli.build_parser().parse_args(['submit', '--repo', 'url', '--commit', 'sha', '--hypothesis', 'test']).benchmark_version == '0.5.0'


def test_fresh_home_scaffolds_without_git_identity_or_signing(tmp_path, monkeypatch):
    import subprocess
    home = tmp_path/'fresh-home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(home/'config'))
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(home/'absent-gitconfig'))
    monkeypatch.setenv('GIT_AUTHOR_NAME', 'Inherited Identity')
    monkeypatch.setenv('GIT_COMMITTER_EMAIL', 'inherited@example.invalid')
    monkeypatch.setenv('GIT_CONFIG_COUNT', '2')
    monkeypatch.setenv('GIT_CONFIG_KEY_0', 'commit.gpgSign')
    monkeypatch.setenv('GIT_CONFIG_VALUE_0', 'true')
    monkeypatch.setenv('GIT_CONFIG_KEY_1', 'gpg.program')
    monkeypatch.setenv('GIT_CONFIG_VALUE_1', '/nonexistent/scaffold-signing-program')
    for version in ('0.5.0', '0.6.0'):
        workspace = tmp_path/('workspace-'+version)
        assert cli.main(['clone', '--benchmark-version', version, str(workspace)]) == 0
        identity = subprocess.check_output(['git', '-C', str(workspace), 'show', '-s', '--format=%an <%ae>|%cn <%ce>|%G?'], text=True).strip()
        assert identity == 'MLDSAFAIL Workspace <workspace@mldsafail.invalid>|MLDSAFAIL Workspace <workspace@mldsafail.invalid>|N'
        assert subprocess.check_output(['git', '-C', str(workspace), 'status', '--porcelain']) == b''
        assert 'user.name' not in (workspace/'.git/config').read_text()
    assert not (home/'.gitconfig').exists()
    assert not (home/'absent-gitconfig').exists()


def test_follow_waits_for_retry(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cli._write_config({'server': 'https://staging.test', 'token': 'private'})
    monkeypatch.setattr(cli.keyring, 'get_password', lambda *a: None)
    states = iter([{'id': 'one', 'state': 'infrastructure_failed', 'job': {'status': 'queued'}},
                   {'id': 'one', 'state': 'infrastructure_failed', 'job': {'status': 'failed'}}])
    monkeypatch.setattr(cli, '_request', lambda method, server, path, **kw: Response(
        {'logs': []} if path.endswith('/logs') else {'submission': next(states)}))
    sleeps = []
    monkeypatch.setattr(cli.time, 'sleep', lambda duration: sleeps.append(duration))
    assert cli.main(['status', 'one', '--follow']) == 1
    assert len(sleeps) == 1


def test_explicit_v060_refuses_legacy_server_before_submission(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path))
    cli._write_config({'server':'https://legacy.test','token':'private'})
    monkeypatch.setattr(cli.keyring,'get_password',lambda *a:None)
    calls=[]
    def legacy(method,url,**kwargs):
        calls.append((method,url))
        # Legacy server ignores unknown version on POST and would queue 0.5.0.
        return Response({'submission':{'id':'wrong-version','state':'queued','benchmark_version':'0.5.0'}})
    monkeypatch.setattr(cli.requests,'request',legacy)
    assert cli.main(['submit','--repo','url','--commit','a'*40,'--hypothesis','test','--benchmark-version','0.6.0'])==2
    assert calls==[('GET','https://legacy.test/api/v1/capabilities')]


def test_explicit_v060_supported_preflight_precedes_correct_version_post(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path))
    cli._write_config({'server':'https://future.test','token':'private'})
    monkeypatch.setattr(cli.keyring,'get_password',lambda *a:None)
    calls=[]
    def future(method,url,**kwargs):
        calls.append((method,url,kwargs))
        if method=='GET': return Response(dict(schema='mldsafail.api-capabilities.v1',explicit_version_selection=True,submission_versions=['0.5.0','0.6.0']))
        return Response({'submission':{'id':'correct','state':'queued','benchmark_version':'0.6.0'}})
    monkeypatch.setattr(cli.requests,'request',future)
    assert cli.main(['submit','--repo','url','--commit','a'*40,'--hypothesis','test','--benchmark-version','0.6.0','--idempotency-key','retained'])==0
    assert [row[0] for row in calls]==['GET','POST']
    assert calls[1][2]['json']['benchmark_version']=='0.6.0'
    assert calls[1][2]['headers']['Idempotency-Key']=='retained'


def test_v060_uncertain_post_retains_generated_key_before_network(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path))
    cli._write_config({'server':'https://future.test','token':'private'})
    monkeypatch.setattr(cli.keyring,'get_password',lambda *a:None)
    def request(method,url,**kwargs):
        if method=='GET':return Response(dict(schema='mldsafail.api-capabilities.v1',explicit_version_selection=True,submission_versions=['0.6.0']))
        intents=list((cli.config_path().parent/'submission-intents').glob('*.json'))
        assert len(intents)==1 and intents[0].stat().st_mode&0o777==0o600
        stored=json.loads(intents[0].read_text())
        assert stored['idempotency_key']==kwargs['headers']['Idempotency-Key']
        raise cli.CliError('lost response')
    monkeypatch.setattr(cli.requests,'request',request)
    assert cli.main(['submit','--repo','url','--commit','a'*40,'--hypothesis','test','--benchmark-version','0.6.0'])==2
    stored=json.loads(next((cli.config_path().parent/'submission-intents').glob('*.json')).read_text())
    assert stored['idempotency_key'] in capsys.readouterr().err
    assert 'private' not in json.dumps(stored)


def test_v060_scaffold_commits_without_participant_git_identity(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.setenv('HOME',str(tmp_path/'empty-home'))
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM','1')
    for variable in ('GIT_AUTHOR_NAME','GIT_AUTHOR_EMAIL','GIT_COMMITTER_NAME','GIT_COMMITTER_EMAIL'):
        monkeypatch.delenv(variable,raising=False)
    workspace=tmp_path/'candidate'
    assert cli.main(['clone',str(workspace),'--benchmark-version','0.6.0'])==0
    assert subprocess.check_output(['git','-C',str(workspace),'log','-1','--format=%an <%ae>'],text=True).strip()=='MLDSAFAIL Workspace <workspace@mldsafail.invalid>'
    assert subprocess.run(['git','-C',str(workspace),'config','--local','user.email'],capture_output=True).returncode!=0


@pytest.mark.parametrize('item',[None,[],{'id':'known','state':'queued'},{'id':'known','state':'unknown','benchmark_version':'0.6.0'}])
def test_v060_malformed_ack_preserves_generated_identity(tmp_path,monkeypatch,capsys,item):
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path))
    cli._write_config({'server':'https://future.test','token':'private'})
    monkeypatch.setattr(cli.keyring,'get_password',lambda *a:None)
    monkeypatch.setattr(cli.requests,'request',lambda method,url,**kwargs:Response(dict(schema='mldsafail.api-capabilities.v1',explicit_version_selection=True,submission_versions=['0.6.0'])) if method=='GET' else Response({'submission':item}))
    assert cli.main(['submit','--repo','url','--commit','a'*40,'--hypothesis','test','--benchmark-version','0.6.0'])==2
    stored=json.loads(next((cli.config_path().parent/'submission-intents').glob('*.json')).read_text())
    assert stored['idempotency_key'] in capsys.readouterr().err
