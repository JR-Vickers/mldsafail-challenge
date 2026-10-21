import io,os,tarfile
import pytest
from deploy.workload_artifacts import archive_inventory,extract,verify_tree
from mldsafail.evaluator.workload import WorkloadBlocked


def archive(*,unsafe=False,hardlink=False):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as tar:
        data=b'bound executable';row=tarfile.TarInfo('tool/bin/python');row.size=len(data);row.mode=0o755
        tar.addfile(row,io.BytesIO(data))
        row=tarfile.TarInfo('tool/bin/python3');row.type=tarfile.LNKTYPE if hardlink else tarfile.SYMTYPE
        row.linkname='tool/bin/python' if hardlink else ('../../../outside' if unsafe else 'python');tar.addfile(row)
    return output.getvalue()


def test_archive_installation_is_exclusive_and_checks_actual_bytes(tmp_path):
    data=archive();rows=archive_inventory(data);root=tmp_path/'tools'
    extract(data,root,rows);verify_tree(root,rows)
    (root/'tool/bin/python').write_bytes(b'tamper')
    with pytest.raises(WorkloadBlocked):verify_tree(root,rows)


def test_tar_hardlinks_become_independent_files(tmp_path):
    data=archive(hardlink=True);root=tmp_path/'tools';extract(data,root,archive_inventory(data))
    a=root/'tool/bin/python';b=root/'tool/bin/python3'
    assert a.stat().st_ino!=b.stat().st_ino and a.stat().st_nlink==b.stat().st_nlink==1


def test_archive_cannot_escape_destination():
    with pytest.raises(WorkloadBlocked):archive_inventory(archive(unsafe=True))


def test_existing_destination_is_never_overwritten(tmp_path):
    root=tmp_path/'tools';root.mkdir();(root/'keep').write_bytes(b'unknown')
    with pytest.raises(FileExistsError):extract(archive(),root,archive_inventory(archive()))
    assert (root/'keep').read_bytes()==b'unknown'


def test_parent_symlink_is_rejected():
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as tar:
        row=tarfile.TarInfo('tool');row.type=tarfile.SYMTYPE;row.linkname='other';tar.addfile(row)
        row=tarfile.TarInfo('tool/child');row.size=1;tar.addfile(row,io.BytesIO(b'x'))
    with pytest.raises(WorkloadBlocked):archive_inventory(output.getvalue())


@pytest.mark.parametrize('name',['lib/python3.12/site.py','lib/libpython3.12.so','bin/uv'])
def test_installed_tool_verifier_detects_non_entrypoint_tamper(tmp_path,name):
    from deploy.workload_artifacts import verify_installed_tools
    from deploy.workload_release import digest
    root=tmp_path/'release';tool=root/'tools'/'interpreter';target=tool/name
    target.parent.mkdir(parents=True);tool.chmod(0o700);(root/'tools').chmod(0o700);target.write_bytes(b'approved');target.chmod(0o600)
    members={name:dict(kind='file',mode=0o600,bytes=8,sha256=digest(b'approved'))}
    for parent in target.parents:
        if parent==tool:break
        parent.chmod(0o700)
    manifest=dict(tools=dict(interpreter=dict(members=members)))
    verify_installed_tools(root,manifest)
    target.write_bytes(b'tampered')
    with pytest.raises(WorkloadBlocked,match='tool_installed_tree_changed'):verify_installed_tools(root,manifest)


def test_ancestor_symlink_rejected_before_any_mutation(tmp_path):
    external=tmp_path/'external';external.mkdir();(external/'keep').write_bytes(b'keep')
    link=tmp_path/'link';link.symlink_to(external,target_is_directory=True)
    before=list(external.iterdir())
    with pytest.raises(WorkloadBlocked,match='tool_parent_symlink'):
        extract(archive(),link/'tools',archive_inventory(archive()))
    assert list(external.iterdir())==before and (external/'keep').read_bytes()==b'keep'


def test_tool_root_permission_drift_blocks_verification(tmp_path):
    data=archive();root=tmp_path/'tool';rows=archive_inventory(data);extract(data,root,rows)
    root.chmod(0o755)
    with pytest.raises(WorkloadBlocked,match='tool_root_invalid'):verify_tree(root,rows)
