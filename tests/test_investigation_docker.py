import json
from pathlib import Path

import pytest

from deploy.investigation_docker import Router, WORKER_FLAGS, LABEL


@pytest.fixture
def router(tmp_path):
    tmp_path.chmod(0o700)
    config = dict(operation_id='a'*32, parent='investigation.slice', image='sha256:'+'b'*64,
                  journal=str(tmp_path), daemon='daemon', solver_root='/srv/epoch')
    containers, calls = {}, []
    def command(args):
        calls.append(args)
        if args[0] == 'info': return b'{"ID":"daemon"}'
        if args[:2] == ['image', 'inspect']:
            return json.dumps([dict(Id=config['image'], Os='linux', Architecture='amd64')]).encode()
        if args[0] == 'create':
            cid = 'c'*64
            name = args[args.index('--name')+1]
            containers[cid] = dict(Id=cid, Name='/'+name,
                Config=dict(Image=config['image'], Labels={LABEL:config['operation_id']}),
                HostConfig=dict(CgroupParent=config['parent']),
                State=dict(Running=False, StartedAt='birth', ExitCode=0))
            return cid.encode()
        if args[0] == 'inspect': return json.dumps([containers[args[1]]]).encode()
        if args[0] == 'kill': containers[args[1]]['State']['Running'] = False
        if args[0] == 'rm': containers.pop(args[1])
        return b''
    class Client:
        def poll(self): return 0
        def wait(self, timeout): return 0
    result = Router(config, command, lambda args: Client())
    return result, containers, calls


def test_frozen_lifecycle_and_exact_ownership(router, capsys):
    route, containers, calls = router
    name='mlwe-'+'d'*32
    assert route.dispatch(['run','--name',name,*WORKER_FLAGS,route.config['image']]) == 0
    record=json.loads((route.root/(name+'.json')).read_text())
    assert record['container_id']=='c'*64 and record['started_at']=='birth'
    route.dispatch(['inspect','--format','{{json .State}}',name])
    assert '"Running": false' in capsys.readouterr().out
    containers['c'*64]['Config']['Labels'][LABEL]='other'
    with pytest.raises(ValueError): route.dispatch(['rm','-f',name])
    containers['c'*64]['Config']['Labels'][LABEL]=route.config['operation_id']
    assert route.dispatch(['rm','-f',name]) == 0
    assert json.loads((route.root/(name+'.json')).read_text())['state']=='removed'


def test_second_worker_and_restarted_birth_rejected(router):
    route, containers, calls = router
    name='mlwe-'+'d'*32
    route.dispatch(['run','--name',name,*WORKER_FLAGS,route.config['image']])
    with pytest.raises(ValueError,match='unsettled'):
        route.dispatch(['run','--name','mlwe-'+'e'*32,*WORKER_FLAGS,route.config['image']])
    containers['c'*64]['State']['StartedAt']='replacement'
    with pytest.raises(ValueError,match='restarted'):
        route.dispatch(['kill',name])


@pytest.mark.parametrize('arguments',[
 ['run','--privileged','sha256:'+'b'*64],
 ['run','--name','mlwe-'+'d'*32,'--env','X=sha256:'+'b'*64,'different-image'],
 ['inspect','unowned'],['kill','web'],['rm','-f','db'],['system','prune'],
])
def test_no_generic_docker_surface(router, arguments):
    with pytest.raises((ValueError,FileNotFoundError)):
        router[0].dispatch(arguments)


def test_artifact_read_is_labeled_bounded_and_removed(router):
    route, containers, calls=router
    assert route.dispatch(['run','--rm','--network=none','--read-only','--entrypoint=cat',
                           route.config['image'],'/artifacts.json'])==0
    create=next(c for c in calls if c[0]=='create')
    assert '--memory=64m' in create and '--cgroup-parent' in create
    assert not containers


def test_solver_mount_cannot_escape_epoch(router):
    route,_,_=router
    with pytest.raises(ValueError):
        route.dispatch(['run','--name','mlwe-'+'d'*32,*WORKER_FLAGS,'--mount',
                        'type=bind,src=/etc,dst=/solver,readonly',route.config['image']])
