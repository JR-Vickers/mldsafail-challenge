"""Immutable provenance emitted only by the authorized installed-native watchdog.

These files do not grant authority. Readers must check the live watchdog/stage
ancestry, exact reviewed protocol and consumed owner claim before each effect.
"""
import time
from pathlib import Path

from deploy.workload_installation import exclusive,identity,private
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.native_workload import process_birth,require

SCHEMA='mldsafail.workload-native-supervision.v1'
STAGE='mldsafail.workload-native-stage.v1'
BIRTH='mldsafail.workload-native-stage-birth.v1'


def publish(root,protocol,grant,deadline):
    root=Path(root).absolute()
    require(protocol['origin']=='installed_native' and time.monotonic()<deadline,
            'native_supervision_authority_or_deadline_missing')
    kinds=['startup',*['case']*len(protocol['cases']),'cleanup','postflight']
    rows=[protocol['startup'],*protocol['cases'],protocol['cleanup'],protocol['postflight']]
    stages=[dict(index=index,kind=kind,name=row['name'],intent_path=str(root/f'native-stage-{index}.json'),
                 birth_path=str(root/f'native-stage-{index}-birth.json'))
            for index,(kind,row) in enumerate(zip(kinds,rows))]
    proof=dict(schema=SCHEMA,origin='installed_native',protocol_sha256=digest(canonical(protocol)),
        watchdog=process_birth(__import__('os').getpid()),root=identity(root),
        review=grant['review'],authorization=grant['authorization'],claim=grant['claim'],
        deadline_monotonic=deadline,created_monotonic=time.monotonic(),
        watchdog_source_sha256=digest(Path(__file__).with_name('workload_watchdog.py').read_bytes()),stages=stages)
    path=root/'native-supervision.json';exclusive(path,canonical(proof))
    return proof


def stage_intent(proof,index,row,deadline):
    stage=proof['stages'][index]
    require(stage['name']==row['name'] and time.monotonic()<deadline<=proof['deadline_monotonic'],
            'native_supervision_stage_changed_or_expired')
    value=dict(schema=STAGE,supervision_sha256=digest(canonical(proof)),protocol_sha256=proof['protocol_sha256'],
        index=index,kind=stage['kind'],name=stage['name'],argv_sha256=digest(canonical(row['argv'])),
        started_monotonic=time.monotonic(),deadline_monotonic=deadline)
    exclusive(stage['intent_path'],canonical(value))
    return value


def stage_birth(proof,index,birth):
    stage=proof['stages'][index];raw,_=private(stage['intent_path'])
    require(type(birth) is dict and set(birth)=={'pid','start_ticks'} and
        all(type(value) is int and value>0 for value in birth.values()),'native_supervision_stage_birth_invalid')
    value=dict(schema=BIRTH,intent_sha256=digest(raw),process=birth,
        supervision_sha256=digest(canonical(proof)))
    exclusive(stage['birth_path'],canonical(value))
    return value
