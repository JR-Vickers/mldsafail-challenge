"""Execution admission for separately sealed fresh reference costs.

Draft cost-table syntax validation is deliberately insufficient. A trusted
independent reference operator holds this separate verification key and issues
an authority only after auditing the native receipts, full primitive viability,
and sealed epoch. This module performs no activation or native gate claim.
"""
import hashlib
import hmac
import json

SCHEMA='mldsafail.v060-reference-authority.v1'
GATES={'independent_reference_audit','full_primitive_viability','epoch_sealing'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def seal(table, *, audit_receipt, key):
    if not isinstance(key,bytes) or len(key)<32: raise ValueError('Separate private reference authority key required')
    if not isinstance(audit_receipt,dict) or audit_receipt.get('ready') is not True or audit_receipt.get('remaining_gates')!=[] or set(audit_receipt.get('gates',{}))!=GATES or any(value is not True for value in audit_receipt['gates'].values()):
        raise ValueError('Complete independently audited sealed reference receipt required')
    if audit_receipt.get('reference_table_sha256')!=digest(table):
        raise ValueError('Independent receipt differs from exact reference costs')
    payload=dict(schema=SCHEMA,table_sha256=digest(table),audit_receipt=audit_receipt)
    return dict(payload=payload,signature=hmac.new(key,b'mldsafail-v060-reference-authority\0'+json.dumps(payload,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest())


def require(table, authority, *, key):
    if not isinstance(authority,dict) or set(authority)!={'payload','signature'}:
        raise ValueError('Sealed independent reference authority required; draft costs are inadmissible')
    if not isinstance(key,bytes) or len(key)<32: raise ValueError('Separate reference verification key required')
    payload=authority['payload']
    if not isinstance(payload,dict) or set(payload)!={'schema','table_sha256','audit_receipt'} or payload['schema']!=SCHEMA or payload['table_sha256']!=digest(table):
        raise ValueError('Reference authority belongs to different costs')
    expected=seal(table,audit_receipt=payload['audit_receipt'],key=key)
    if not isinstance(authority['signature'],str) or not hmac.compare_digest(authority['signature'],expected['signature']):
        raise ValueError('Independent reference authority signature mismatch')
