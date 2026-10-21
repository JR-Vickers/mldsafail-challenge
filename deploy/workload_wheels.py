"""Offline wheel integrity checks using only the bound interpreter's stdlib.

This validates artifacts, not an installed environment or execution authority.
Dependency resolution remains a separate prerequisite.
"""
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
from pathlib import PurePosixPath
import re
import stat
import zipfile

from deploy.workload_release import digest, regular
from mldsafail.evaluator.native_workload import require


def python_requirement(value):
    """Require compatibility with every CPython 3.12 patch; reject uncertainty."""
    for clause in value.split(','):
        match = re.fullmatch(r'\s*(>=|<=|==|!=|>|<)\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?\s*', clause)
        if match is None:
            return False
        operator, *numbers = match.groups()
        version = tuple(int(number or 0) for number in numbers)
        lower, upper = (3, 12, 0), (3, 12, float("inf"))
        if operator == "!=":
            if lower <= version <= upper:
                return False
            continue
        if not all({'>=': target >= version, '<=': target <= version,
                '==': target == version, '!=': target != version,
                '>': target > version, '<': target < version}[operator] for target in (lower, upper)):
            return False
    return True


def compatible(tag, *, glibc_minor=17):
    parts = tag.split('-')
    if len(parts) != 3:
        return False
    python, abi, platform = parts
    universal = platform == 'any' and abi == 'none' and python in ('py3', 'py312', 'cp312')
    # Conservative portable baseline: glibc >= 2.17 must be observed on the
    # target separately. A generic linux tag does not establish libc ABI.
    version = re.fullmatch(r'manylinux_2_(\d+)_x86_64', platform)
    native = platform in ('manylinux1_x86_64', 'manylinux2010_x86_64', 'manylinux2014_x86_64') or (
        version is not None and int(version[1]) <= glibc_minor)
    interpreter = python == 'cp312' and abi in ('cp312', 'abi3', 'none')
    stable = re.fullmatch(r'cp3(\d+)', python)
    return universal or native and (interpreter or abi == 'abi3' and stable is not None and int(stable[1]) <= 12)


def inspect_wheel(path, expected_sha256, *, glibc_minor=17):
    """Validate ZIP paths, metadata, tags and every RECORD payload hash."""
    from pathlib import Path
    path = Path(path)
    data, _ = regular(path.parent, path.name)
    require(path.suffix == '.whl' and digest(data) == expected_sha256, 'wheel_artifact_changed')
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
        names = [row.filename for row in infos]
        require(len(names) == len(set(names)) and len(names) > 0, 'wheel_duplicate_members')
        for row in infos:
            name = row.filename
            pure = PurePosixPath(name)
            require(not pure.is_absolute() and '..' not in pure.parts and '\\' not in name and
                    str(pure) == name.rstrip('/') and
                    not stat.S_ISLNK(row.external_attr >> 16), 'wheel_unsafe_member')
        metadata_names = [name for name in names if name.endswith('.dist-info/METADATA')]
        require(len(metadata_names) == 1, 'wheel_metadata_missing')
        prefix = metadata_names[0].rsplit('/', 1)[0]
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        wheel = BytesParser().parsebytes(archive.read(prefix+'/WHEEL'))
        require(metadata.get('Name') and metadata.get('Version') and wheel.get('Wheel-Version') == '1.0',
                'wheel_metadata_invalid')
        require(all(len(metadata.get_all(key, [])) <= 1 for key in ('Name', 'Version', 'Requires-Python')),
                'wheel_duplicate_metadata')
        require(not metadata.get('Requires-Python') or python_requirement(metadata['Requires-Python']),
                'wheel_python_incompatible')
        tags = wheel.get_all('Tag', [])
        require(tags and any(compatible(tag, glibc_minor=glibc_minor) for tag in tags), 'wheel_incompatible')
        filename = path.name[:-4].split('-')
        require(len(filename) in (5, 6), 'wheel_filename_invalid')
        normalize = lambda value: re.sub(r'[-_.]+', '-', value).lower()
        require(normalize(filename[0]) == normalize(metadata['Name']) and filename[1] == metadata['Version'],
                'wheel_filename_metadata_mismatch')
        require(prefix == filename[0]+'-'+filename[1]+'.dist-info', 'wheel_dist_info_mismatch')
        filename_tags = {f'{p}-{a}-{s}' for p in filename[-3].split('.')
                         for a in filename[-2].split('.') for s in filename[-1].split('.')}
        require(set(tags) == filename_tags, 'wheel_tag_mismatch')
        record_name = prefix+'/RECORD'
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
        require(all(len(row) == 3 for row in rows) and len({row[0] for row in rows}) == len(rows),
                'wheel_record_invalid')
        files = {name for name in names if not name.endswith('/')}
        require({row[0] for row in rows} == files, 'wheel_record_incomplete')
        for name, checksum, size in rows:
            if name == record_name:
                require(checksum == size == '', 'wheel_record_self_hash')
                continue
            contents = archive.read(name)
            expected = 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(contents).digest()).rstrip(b'=').decode()
            require(checksum == expected and size == str(len(contents)), 'wheel_record_content_changed')
        return dict(name=metadata['Name'], version=metadata['Version'], tags=tags,
                    requires=metadata.get_all('Requires-Dist', []), sha256=digest(data))
    except (zipfile.BadZipFile, KeyError, UnicodeError, ValueError) as error:
        require(False, 'wheel_invalid_archive:'+str(error))
