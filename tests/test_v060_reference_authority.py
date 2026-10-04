import pytest
from research.mlwe_v060_preparation.reference_authority import seal,require,digest,GATES


def test_draft_and_incomplete_reference_receipts_are_inadmissible():
    table={'costs_usec':{'case':1}}
    with pytest.raises(ValueError,match='draft'):
        require(table,None,key=b'x'*32)
    with pytest.raises(ValueError,match='Complete'):
        seal(table,audit_receipt={'ready':False,'remaining_gates':list(GATES)},key=b'x'*32)


def test_sealed_authority_binds_costs_audit_and_separate_key():
    table={'costs_usec':{'case':1}}
    receipt=dict(ready=True,remaining_gates=[],gates={name:True for name in GATES},reference_table_sha256=digest(table))
    authority=seal(table,audit_receipt=receipt,key=b'x'*32)
    require(table,authority,key=b'x'*32)
    with pytest.raises(ValueError,match='different costs'):
        require({'costs_usec':{'case':2}},authority,key=b'x'*32)
    with pytest.raises(ValueError,match='signature'):
        require(table,authority,key=b'y'*32)
    authority['payload']['audit_receipt']['gates']['epoch_sealing']=False
    with pytest.raises(ValueError,match='Complete'):
        require(table,authority,key=b'x'*32)
