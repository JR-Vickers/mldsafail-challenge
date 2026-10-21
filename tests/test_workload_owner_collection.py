from types import SimpleNamespace

import pytest

from scripts.workload_owner_collection import inventory, MAX_ACCOUNTS


def test_all_account_crontabs_and_inactive_manager_owners_are_inventoried():
    accounts = [SimpleNamespace(pw_uid=uid, pw_name=name, pw_dir=home)
                for uid, name, home in [(0, 'root', '/root'), (1000, 'operator', '/home/operator'),
                                        (999, 'service', '/nonexistent')]]
    sections, roots, owners = inventory(accounts)
    assert len(owners) == 3
    assert sections['account_service_cron'] == ['crontab', '-l', '-u', 'service']
    assert 'user@999.service' in sections['account_service_manager']
    assert '/home/operator/.config/systemd/user' in roots
    assert '/usr/lib/systemd/system' in roots


def test_owner_inventory_bound_is_an_error():
    with pytest.raises(ValueError, match='limit'): inventory([None]*(MAX_ACCOUNTS+1))
