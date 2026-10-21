"""Bounded private runtime helper transport, without reader threads.

The helper is an installed, reviewed executable, not a contestant command. Each
call receives one JSON request on stdin and returns one bounded JSON response.
A timeout is ambiguous: the caller must retain ownership and reconcile resources.
"""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time

from mldsafail.evaluator.workload import WorkloadBlocked


class RuntimeTransport:
    def __init__(self, command, *, timeout=.8, max_bytes=65536):
        if (not command or not os.path.isabs(command[0]) or
                not 0 < timeout <= .8 or not 0 < max_bytes <= 1024 * 1024):
            raise ValueError('invalid_runtime_transport')
        self.command = tuple(command)
        self.timeout, self.max_bytes = timeout, max_bytes
        self.pending = []

    def call(self, method, argument):
        if method not in {'identity', 'preflight', 'sample', 'launch', 'inspect', 'terminate', 'stopped'}:
            raise ValueError('invalid_runtime_method')
        self.pending = [process for process in self.pending if process.poll() is None]
        if self.pending:
            raise WorkloadBlocked('runtime_helper_unresolved')
        request = json.dumps({'method': method, 'argument': argument}).encode() + b'\n'
        if len(request) > self.max_bytes:
            raise WorkloadBlocked('runtime_request_limit')
        deadline = time.monotonic() + self.timeout
        process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        output, offset = bytearray(), 0
        try:
            with selectors.DefaultSelector() as selector:
                for stream in (process.stdin, process.stdout):
                    os.set_blocking(stream.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise WorkloadBlocked('runtime_helper_deadline')
                    for key, _ in selector.select(remaining):
                        if key.fileobj is process.stdin:
                            offset += os.write(process.stdin.fileno(), request[offset:])
                            if offset == len(request):
                                selector.unregister(process.stdin)
                                process.stdin.close()
                        else:
                            chunk = os.read(process.stdout.fileno(), min(4096, self.max_bytes + 1 - len(output)))
                            if not chunk:
                                selector.unregister(process.stdout)
                            output.extend(chunk)
                            if len(output) > self.max_bytes:
                                raise WorkloadBlocked('runtime_response_limit')
                try:
                    status = process.wait(timeout=max(.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired as error:
                    raise WorkloadBlocked('runtime_helper_deadline') from error
                if status != 0:
                    raise WorkloadBlocked('runtime_helper_failed')
                try:
                    response = json.loads(output)
                except (ValueError, UnicodeError) as error:
                    raise WorkloadBlocked('runtime_response_invalid') from error
                if type(response) is not dict or set(response) != {'result'}:
                    raise WorkloadBlocked('runtime_response_invalid')
                return response['result']
        finally:
            # Never wait for a potentially uninterruptible helper while holding
            # the journal mutex. Retain its process handle and prohibit new I/O.
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                self.pending.append(process)
            process.stdin.close()
            process.stdout.close()
