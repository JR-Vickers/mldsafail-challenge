"""Install the pinned upstream Linux amd64 restic 0.18.1 archive without overwrite."""
import argparse
import bz2
import hashlib
import json
from pathlib import Path

ARCHIVE_SHA256 = '680838f19d67151adba227e1570cdd8af12c19cf1735783ed1ba928bc41f363d'
ARCHIVE_URL = 'https://github.com/restic/restic/releases/download/v0.18.1/restic_0.18.1_linux_amd64.bz2'


def install(archive, destination):
    compressed = archive.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Pinned upstream restic archive checksum mismatch')
    data = bz2.decompress(compressed)
    with destination.open('xb') as stream:
        stream.write(data)
    destination.chmod(0o700)
    return {'version': '0.18.1', 'restic_binary': str(destination.resolve()),
            'restic_sha256': hashlib.sha256(data).hexdigest()}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(install(args.archive, args.destination)))
