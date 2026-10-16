from types import SimpleNamespace
import json
import pytest
from scripts import native_synthetic_database_restoration as restore


def test_preparation_failure_attempts_cleanup_preserves_original(tmp_path,monkeypatch):
    original=ValueError('tiny database preparation failed');cleaned=[]
    monkeypatch.setattr(restore.fixture,'database',lambda *a:(_ for _ in ()).throw(original))
    class Operation:
        data={'cleanup_complete':False}
        def __init__(self,*a):pass
        def cleanup(self):cleaned.append(True);self.data['cleanup_complete']=True
    monkeypatch.setattr(restore,'Journal',Operation)
    with pytest.raises(ValueError) as caught:restore.callback(SimpleNamespace(path=tmp_path/'driver.json'),{},dict(id='owned'))
    assert caught.value is original and cleaned==[True]
    result=json.loads((tmp_path/'synthetic-restoration/result.json').read_text())
    assert result['passed'] is False and result['cleanup_complete'] is True
    assert result['actual_offhost_storage'] is False
