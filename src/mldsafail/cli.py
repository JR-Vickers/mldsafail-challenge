"""Unified offline benchmark and hosted challenge CLI."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
import uuid
from pathlib import Path

import keyring
import requests
from keyring.errors import KeyringError, NoKeyringError

SERVICE = "mldsafail-challenge"
DEFAULT_SERVER = "https://mldsa.fail"


class CliError(RuntimeError):
    pass


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "mldsafail" / "config.json"


def _read_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_config(values: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, (json.dumps(values, indent=2) + "\n").encode())
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _store_token(server: str, token: str, allow_file: bool) -> None:
    try:
        keyring.set_password(SERVICE, server, token)
        if keyring.get_password(SERVICE, server) != token:
            raise NoKeyringError("credential store did not retain the token")
        return
    except (KeyringError, NoKeyringError, RuntimeError):
        if not allow_file:
            raise CliError(
                "No operating-system credential store is available. Re-run with "
                "--allow-plaintext-storage to use a permission-restricted fallback file."
            ) from None
    config = _read_config()
    config["token"] = token
    _write_config(config)
    print("warning: token stored in a local 0600 configuration file", file=sys.stderr)


def _load_token(server: str) -> str:
    try:
        token = keyring.get_password(SERVICE, server)
    except (KeyringError, NoKeyringError, RuntimeError):
        token = None
    token = token or _read_config().get("token")
    if not token:
        raise CliError("Not logged in. Run `mldsafail login TOKEN --server URL` first.")
    return token


def _request(method: str, server: str, path: str, *, token: str, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, f"{server.rstrip('/')}{path}", headers=headers, timeout=20, **kwargs)
    except requests.RequestException as exception:
        raise CliError(f"Server request failed: {exception}") from None
    if response.status_code >= 400:
        try:
            problem = response.json()["error"]
            raise CliError(f"{problem['code']}: {problem['message']}")
        except (ValueError, KeyError, TypeError):
            raise CliError(f"Server returned HTTP {response.status_code}.") from None
    return response


def login(args) -> int:
    server = args.server.rstrip("/")
    profile = _request("GET", server, "/api/v1/me", token=args.token).json()
    _store_token(server, args.token, args.allow_plaintext_storage)
    config = _read_config(); config["server"] = server
    # Do not rewrite a fallback token unless it is already present.
    _write_config(config)
    print(f"Logged in to {server} as {profile['display_name']}.")
    return 0


def logout(args) -> int:
    config = _read_config(); server = args.server or config.get("server", DEFAULT_SERVER)
    try:
        keyring.delete_password(SERVICE, server)
    except (KeyringError, NoKeyringError, RuntimeError):
        pass
    config.pop("token", None)
    if config:
        _write_config(config)
    elif config_path().exists():
        config_path().unlink()
    print(f"Logged out from {server}.")
    return 0


def submit(args) -> int:
    config = _read_config(); server = args.server or config.get("server", DEFAULT_SERVER)
    token = _load_token(server)
    payload = {"repository_url": args.repo, "commit_sha": args.commit, "hypothesis": args.hypothesis,
               "notes": args.notes, "tags": args.tag or [], "benchmark_version": args.benchmark_version}
    response = _request("POST", server, "/api/v1/submissions", token=token, json=payload,
                        headers={"Idempotency-Key": args.idempotency_key or str(uuid.uuid4())})
    item = response.json()["submission"]
    print(f"{item['id']}  {item['state']}")
    return 0


def status(args) -> int:
    config = _read_config(); server = args.server or config.get("server", DEFAULT_SERVER)
    token = _load_token(server)
    terminal = {"accepted", "rejected", "infrastructure_failed", "cancelled"}
    last = None
    while True:
        item = _request("GET", server, f"/api/v1/submissions/{args.submission_id}", token=token).json()["submission"]
        logs = _request("GET", server, f"/api/v1/submissions/{args.submission_id}/logs", token=token).json()["logs"]
        rendered = "\n".join(entry["text"] for entry in logs)
        snapshot = (item["state"], rendered)
        if snapshot != last:
            print(f"{item['id']}  {item['state']}")
            if rendered:
                print(rendered)
            last = snapshot
        if not args.follow or item["state"] in terminal:
            return 0 if item["state"] != "rejected" else 1
        time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mldsafail", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the benchmark locally without authentication")
    run.add_argument("benchmark_args", nargs=argparse.REMAINDER)
    log_in = commands.add_parser("login", help="validate and store an API token")
    log_in.add_argument("token"); log_in.add_argument("--server", default=DEFAULT_SERVER)
    log_in.add_argument("--allow-plaintext-storage", action="store_true")
    log_in.set_defaults(handler=login)
    log_out = commands.add_parser("logout", help="remove stored credentials")
    log_out.add_argument("--server"); log_out.set_defaults(handler=logout)
    submission = commands.add_parser("submit", help="submit an immutable public GitHub commit")
    submission.add_argument("--repo", required=True); submission.add_argument("--commit", required=True)
    submission.add_argument("--hypothesis", required=True); submission.add_argument("--notes", default="")
    submission.add_argument("--tag", action="append"); submission.add_argument("--benchmark-version", default="0.2.0")
    submission.add_argument("--idempotency-key"); submission.add_argument("--server"); submission.set_defaults(handler=submit)
    state = commands.add_parser("status", help="show submission state and sanitized logs")
    state.add_argument("submission_id"); state.add_argument("--follow", action="store_true")
    state.add_argument("--interval", type=float, default=2.0); state.add_argument("--server"); state.set_defaults(handler=status)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Benchmark options intentionally remain owned by the established runner.
    if raw and raw[0] == "run":
        from mldsafail.benchmark.runner import main as benchmark_main
        return benchmark_main(raw[1:])
    args = build_parser().parse_args(raw)
    try:
        return args.handler(args)
    except CliError as exception:
        print(f"error: {exception}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
