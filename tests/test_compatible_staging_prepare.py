import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'scripts/compatible_staging_prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_cleanup_attempts_watchdog_after_maintenance_failure(tmp_path):
    driver = SimpleNamespace(cleanup=Mock(side_effect=RuntimeError()), save=Mock())
    subject = SimpleNamespace(path=tmp_path / 'journal.json', directory=tmp_path)
    stop, thread, watcher = Mock(), Mock(), Mock()
    thread.is_alive.return_value = False
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        prepare.finish_cleanup(driver, subject, stop, thread, watcher)
    watcher.terminate.assert_called_once()
    watcher.wait.assert_called_once_with(timeout=10)
    driver.save.assert_called_once()


def test_cleanup_checks_thread_and_watcher_independently(tmp_path):
    driver = SimpleNamespace(cleanup=Mock(), save=Mock())
    subject = SimpleNamespace(path=tmp_path / 'journal.json', directory=tmp_path)
    stop, thread, watcher = Mock(), Mock(), Mock()
    thread.is_alive.return_value = True
    watcher.wait.side_effect = TimeoutError()
    with pytest.raises(RuntimeError):
        prepare.finish_cleanup(driver, subject, stop, thread, watcher)
    driver.cleanup.assert_called_once()
    assert driver.save.call_args.args[1]['errors'] == ['heartbeat_shutdown', 'watchdog_shutdown']


def test_driver_manifest_identity_before_import(tmp_path):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts/hosted_vps_failure_driver.py').write_text('raise AssertionError("must not execute")')
    config = {'operator_source': str(tmp_path), 'release_manifest': {'source_files_sha256':
              {'scripts/hosted_vps_failure_driver.py': '0' * 64}}}
    with pytest.raises(RuntimeError, match='differs'):
        prepare.load_driver(config)
