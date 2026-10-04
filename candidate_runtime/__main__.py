"""Inert until a trusted operator supplies an explicit private mounted config."""
import argparse
import json
from candidate_runtime.config import coordinator,web

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('role',choices=['web','coordinator']);parser.add_argument('--config',required=True)
args=parser.parse_args()
if args.role=='coordinator':print(json.dumps({'claimed':coordinator(args.config)}))
else:
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0',8000,web(args.config),use_reloader=False,use_debugger=False)
