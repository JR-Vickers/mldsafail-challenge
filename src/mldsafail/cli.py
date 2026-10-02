"""Unified offline benchmark and hosted challenge CLI."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

import keyring
import requests
from keyring.errors import KeyringError, NoKeyringError

SERVICE = "mldsafail-challenge"
DEFAULT_SERVER = None


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


def _server(args):
    server = args.server or _read_config().get("server")
    if not server:
        raise CliError("Configure the private staging server with --server URL.")
    return server


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
    server = _server(args).rstrip("/")
    profile = _request("GET", server, "/api/v1/me", token=args.token).json()
    _store_token(server, args.token, args.allow_plaintext_storage)
    config = _read_config(); config["server"] = server
    # Do not rewrite a fallback token unless it is already present.
    _write_config(config)
    print(f"Logged in to {server} as {profile['display_name']}.")
    return 0


def logout(args) -> int:
    config = _read_config(); server = _server(args)
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
    config = _read_config(); server = _server(args)
    token = _load_token(server)
    payload = {"repository_url": args.repo, "commit_sha": args.commit, "hypothesis": args.hypothesis,
               "notes": args.notes, "tags": args.tag or [], "benchmark_version": args.benchmark_version}
    if args.epoch_id:
        payload["epoch_id"] = args.epoch_id
    if args.solver_path:
        payload["solver_path"] = args.solver_path
    response = _request("POST", server, "/api/v1/submissions", token=token, json=payload,
                        headers={"Idempotency-Key": args.idempotency_key or str(uuid.uuid4())})
    item = response.json()["submission"]
    print(f"{item['id']}  {item['state']}")
    return 0


def status(args) -> int:
    config = _read_config(); server = _server(args)
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
        retrying = item["state"] == "infrastructure_failed" and (item.get("job") or {}).get("status") in {"queued", "leased"}
        if not args.follow or (item["state"] in terminal and not retrying):
            return 1 if item["state"] in {"rejected", "infrastructure_failed"} else 0
        time.sleep(args.interval)


def submission_action(args):
    server = _server(args)
    body = _request("POST" if args.command == "cancel" else "GET", server,
                    f"/api/v1/submissions/{args.submission_id}/{args.command}",
                    token=_load_token(server), **({"json": {}} if args.command == "cancel" else {})).json()
    print(json.dumps(body, indent=2))
    return 0


def clone_workspace(args) -> int:
    from pathlib import Path

    dir_path = Path(args.dir).resolve()
    if dir_path.exists() and any(dir_path.iterdir()):
        raise CliError(f"target directory already exists and is non-empty: {dir_path}")
    try:
        subprocess_run(["git", "init", "-q", str(dir_path)], check=True)
    except Exception as exc:
        raise CliError(f"git init failed: {exc}") from exc
    if args.benchmark_version == "0.5.0":
        from importlib.resources import files
        solver_dir = dir_path / "solver"
        solver_dir.mkdir(parents=True, exist_ok=True)
        starter = files("mldsafail").joinpath("data/primal_lll_solver.py")
        if starter.is_file():
            data = starter.read_bytes()
        else:
            data = (Path(__file__).resolve().parents[2] / "examples/mlwe/primal-lll/solver.py").read_bytes()
        (solver_dir / "solver.py").write_bytes(data)
        (dir_path / "README.md").write_text(
            "# MLWE benchmark 0.5.0 workspace (participant package 0.5.1)\n\n"
            "Edit only solver/*.py. Use the repository's docs/MLWE_PILOT.md public development procedure "
            "for local evaluation; mldsafail run measures historical 0.4.0.\n"
            "Publish this workspace to a public GitHub repository and commit your solver.\n"
            'mldsafail submit --server "$STAGING_SERVER" --repo https://github.com/OWNER/REPO '
            '--commit FULL_SHA --solver-path solver --hypothesis "..."\n'
            'mldsafail status ID --server "$STAGING_SERVER" --follow\n')
        subprocess_run(["git", "-C", str(dir_path), "add", "."], check=True)
        subprocess_run(["git", "-C", str(dir_path), "commit", "-q", "-m", "Scaffold MLWE 0.5.0 solver"], check=True)
        print(f"Workspace created at {dir_path}; publish a full commit to public GitHub before submitting.")
        return 0
    solver_dir = dir_path / "src" / "mldsafail" / "solver"
    math_dir = dir_path / "src" / "mldsafail" / "math"
    solver_dir.mkdir(parents=True, exist_ok=True)
    math_dir.mkdir(parents=True, exist_ok=True)
    solver_init = solver_dir / "__init__.py"
    math_init = math_dir / "__init__.py"
    solver_init.write_text(
        '"""Participant solver workspace."""\n'
        "from mldsafail.solver.lazy import solve\n"
        '\n'
        '__all__ = ["solve"]\n'
    )
    math_init.write_text('"""Participant math primitives workspace."""\n')
    try:
        subprocess_run(["git", "-C", str(dir_path), "add", "."], check=True)
        subprocess_run(
            ["git", "-C", str(dir_path), "commit", "-q", "-m", "feat: scaffold participant workspace"],
            check=True, capture_output=True,
        )
    except Exception as exc:
        raise CliError(f"git commit failed: {exc}") from exc
    head = subprocess_run(
        ["git", "-C", str(dir_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    print(f"Workspace created at {dir_path}")
    print(f"Commit {head}")
    print(f"Submit with: mldsafail submit --repo file://{dir_path} --commit {head} --hypothesis \"...\"")
    return 0


def subprocess_run(*args, **kwargs):
    import subprocess
    return subprocess.run(*args, **kwargs)


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
    submission.add_argument("--tag", action="append"); submission.add_argument("--benchmark-version", default="0.5.0", choices=["0.4.0", "0.5.0"])
    submission.add_argument("--epoch-id", help="require this immutable MLWE epoch identity")
    submission.add_argument("--solver-path", help="repository-relative MLWE solver directory containing solver.py")
    submission.add_argument("--idempotency-key"); submission.add_argument("--server"); submission.set_defaults(handler=submit)
    state = commands.add_parser("status", help="show submission state and sanitized logs")
    state.add_argument("submission_id"); state.add_argument("--follow", action="store_true")
    state.add_argument("--interval", type=float, default=2.0); state.add_argument("--server"); state.set_defaults(handler=status)
    clone = commands.add_parser("clone", help="create a participant workspace with a baseline solver")
    clone.add_argument("dir", nargs="?", default="mldsafail-workspace", help="workspace directory")
    clone.add_argument("--benchmark-version", default="0.5.0", choices=["0.4.0", "0.5.0"])
    clone.set_defaults(handler=clone_workspace)
    for name in ("logs", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("submission_id")
        command.add_argument("--server")
        command.set_defaults(handler=submission_action)
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
