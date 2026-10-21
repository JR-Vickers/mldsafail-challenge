"""Durable private supervisor client. Retries preserve exact mutation identity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import threading
import uuid

from mldsafail.evaluator.native_workload import private_json, publish, require
from mldsafail.evaluator.workload import WorkloadBlocked
from mldsafail.evaluator.workload_service import call_private


class WorkloadClient:
    def __init__(self, socket, journal, *, transport=call_private):
        self.socket, self.journal, self.transport = str(socket), Path(journal), transport
        self.journal.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(not self.journal.is_symlink() and not self.journal.stat().st_mode & 0o077,
                'private_client_journal_required')
        self.mutex = threading.RLock()
        self.token = None
        self.generation = None
        self.sequence = 0

    def status(self):
        return self.transport(self.socket, dict(id='status', method='status', argument={}))

    def attach(self, state):
        self.token = state['workload_id']; self.generation = state['request_generation']
        self.sequence = state.get('request_sequence', 0)

    def mutation(self, method, **argument):
        with self.mutex:
            return self._mutation(method, **argument)

    def _mutation(self, method, **argument):
        if method == 'acquire':
            state = self.status()
            generation = (state['request_generation'] if state else 0) + 1
            sequence = 1
        else:
            require(self.token is not None, 'client_ownership_required')
            argument = {'ownership': self.token, **argument}
            generation = self.generation
            self.sequence += 1
            sequence = self.sequence
        request = dict(id=f'{generation}:{sequence}', method=method, argument=argument)
        path = self.journal/(uuid.uuid4().hex+'.json')
        publish(path, dict(request=request, phase='intent'))
        # The request is persisted before any bytes leave this client. A failed
        # call remains available for cleanup/reconciliation; never allocate a new
        # request ID to repeat an ambiguous launch or database commit.
        result = self.replay(path)
        if method == 'acquire':
            self.token = result; self.generation = generation; self.sequence = sequence
        return result

    def replay(self, path):
        record = private_json(path)
        if record['phase'] == 'complete': return record['result']
        result = self.transport(self.socket, record['request'])
        publish(Path(path), dict(record, phase='complete', result=result))
        completed = []
        for candidate in self.journal.glob('*.json'):
            if private_json(candidate).get('phase') == 'complete': completed.append(candidate)
        for candidate in sorted(completed, key=lambda item: item.stat().st_mtime_ns)[:-64]:
            candidate.unlink()
        return result

    def acquire(self, kind, reference): return self.mutation('acquire', kind=kind, reference=reference)
    def bind(self, reference): return self.mutation('bind', reference=reference)
    def launch(self, role): return self.mutation('launch', role=role)
    def heartbeat(self): return self.mutation('heartbeat')
    def result(self):
        self.sequence += 1
        return self.transport(self.socket, dict(id=f'{self.generation}:{self.sequence}', method='result',
                                               argument={'ownership': self.token}))

    def environment(self):
        self.sequence += 1
        return self.transport(self.socket, dict(id=f'{self.generation}:{self.sequence}', method='environment',
                                               argument={'ownership': self.token}))

    def finish(self, binding):
        self.mutation('postflight')
        self.mutation('commit_intent', binding=binding)

    def acknowledge(self, binding):
        self.mutation('acknowledge_commit', binding=binding)
        state = self.status()
        if not state['paused']: self.mutation('release')

    def unused(self):
        binding = {'disposition': 'unused_ownership'}
        self.finish(binding)
        self.acknowledge(binding)
