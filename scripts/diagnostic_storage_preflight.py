"""Read-only lower bound for fresh diagnostic-daemon image unpacking.

A failure stops provisioning. A pass is not a capacity admission: content-store
copies, filesystem metadata, databases and transient writes need extra space.
"""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import time


class DigestReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, count=-1):
        data = self.stream.read(count)
        self.digest.update(data)
        return data


def inspect(paths, filesystem='/srv'):
    layers, names, rows = {}, {}, []
    for path in paths:
        count = 0
        with tarfile.open(path) as archive:
            manifest = json.load(archive.extractfile('manifest.json'))
            for image in manifest:
                for name in image['Layers']:
                    regular_bytes = 0
                    with archive.extractfile(name) as stream:
                        reader = DigestReader(stream)
                        with tarfile.open(fileobj=reader, mode='r|*') as layer:
                            for member in layer:
                                # Sparse files cannot supply a dense-size lower bound.
                                if member.isreg() and not member.issparse():
                                    regular_bytes += member.size
                        while reader.read(1024 * 1024):
                            pass
                        digest = reader.digest.hexdigest()
                    if name in names and names[name] != digest:
                        raise ValueError('Retained layer identity changed')
                    names[name] = digest
                    if digest in layers and layers[digest] != regular_bytes:
                        raise ValueError('Layer footprint mismatch')
                    layers[digest] = regular_bytes
                    count += 1
        rows.append(dict(path=str(path), archive_bytes=Path(path).stat().st_size, layer_count=count))
    available = shutil.disk_usage(filesystem).free
    floor = 5 * 1024**3
    footprint = sum(layers.values())
    return dict(schema='mldsafail.diagnostic-storage-preflight.v1', checked_at=time.time(),
                archives=rows, unique_layers=len(layers), regular_file_lower_bound_bytes=footprint,
                disk_available_bytes=available, minimum_free_bytes=floor,
                headroom_bytes=available - floor,
                provisioning_prohibited=available - footprint < floor,
                capacity_admitted=False, remote_writes=0)


if __name__ == '__main__':
    import argparse
    import signal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+')
    args = parser.parse_args()
    # Includes all hashing and archive reads. No automatic retry.
    signal.alarm(60)
    print(json.dumps(inspect(args.archives), indent=2))
