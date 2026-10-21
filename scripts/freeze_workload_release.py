"""Freeze a complete V3 offline release; this command never installs or activates."""
import argparse
import json
from pathlib import Path
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
from deploy.workload_installation import exclusive,private
from deploy.workload_release import canonical,freeze_runtime,public_manifest
from deploy.workload_units import render_v3


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--bindings',type=Path,required=True,help='Private image/environment/configuration bindings JSON')
    parser.add_argument('--installation',type=Path,required=True,help='Private installation settings used to generate exact units')
    parser.add_argument('--wheels',type=Path,required=True)
    parser.add_argument('--interpreter-archive',type=Path,required=True)
    parser.add_argument('--installer-archive',type=Path,required=True)
    parser.add_argument('--public-manifest',type=Path,required=True)
    args=parser.parse_args()
    _,bindings=private(args.bindings);_,installation=private(args.installation)
    if args.public_manifest.exists() or args.public_manifest.is_symlink():
        raise FileExistsError(args.public_manifest)
    wheels=sorted(args.wheels.iterdir())
    if not wheels or any(not path.name.endswith('.whl') for path in wheels):
        raise ValueError('wheel_directory_must_contain_only_bound_wheels')
    manifest=freeze_runtime(args.source,args.destination,generated_units=render_v3(installation),
        wheels=wheels,bindings=bindings,interpreter_archive=args.interpreter_archive,installer_archive=args.installer_archive)
    exclusive(args.public_manifest,canonical(public_manifest(manifest)))
    print(json.dumps(dict(manifest_sha256=__import__('hashlib').sha256(canonical(manifest)).hexdigest(),execution_authority=False)))


if __name__=='__main__':main()
