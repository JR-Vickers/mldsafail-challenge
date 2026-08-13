from __future__ import annotations

import json

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
    monkeypatch.setattr("mldsafail.benchmark.runner.main", lambda args: seen.setdefault("args", args) or 0)
    assert cli.main(["run", "--profile", "small", "--no-record"]) == ["--profile", "small", "--no-record"]
