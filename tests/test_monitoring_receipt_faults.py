from datetime import datetime, timezone

from scripts.monitoring_fault_acceptance import backup_receipt_cases


def test_monitoring_faults_use_actual_versioned_receipt_validator(tmp_path):
    cases = backup_receipt_cases(tmp_path, datetime.now(timezone.utc))
    assert len(cases) == 11
    assert all(case['passed'] for case in cases)
    assert cases[-1]['check'] == 'recent-verification-cannot-refresh-old-upload'
    assert (tmp_path / 'synthetic-backup-state.json').stat().st_mode & 0o077 == 0
