from pathlib import Path

import pytest

from scripts import offline_volume_evidence as evidence


def test_offline_database_retention_verifies_every_byte_and_never_restores(tmp_path):
    data = tmp_path / 'data'
    data.mkdir(mode=0o700)
    (data / 'PG_VERSION').write_text('17\n')
    (data / 'base').mkdir()
    (data / 'base/fixture').write_bytes(b'synthetic database pages')
    archive = tmp_path / 'database.tar.gz'
    receipt = evidence.archive(data, archive)
    assert receipt['recovery_acceptance'] is False
    assert evidence.verify(data, receipt)
    with pytest.raises(FileExistsError): evidence.archive(data, archive)
    (data / 'base/fixture').write_bytes(b'changed')
    with pytest.raises(ValueError, match='inventory differs'): evidence.verify(data, receipt)


def test_offline_retention_refuses_links_and_cache_nested_output(tmp_path):
    data = tmp_path / 'data'
    data.mkdir(mode=0o700)
    (data / 'escape').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='regular files'): evidence.archive(data, tmp_path / 'archive.tar.gz')
    with pytest.raises(ValueError, match='outside'): evidence.archive(data, data / 'archive.tar.gz')
