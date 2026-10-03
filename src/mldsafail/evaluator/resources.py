"""Host resource floors shared by admission and evaluation."""
from pathlib import Path
import shutil


def resource_floors_available(disk_path=Path('/'), meminfo=Path('/proc/meminfo')):
    try:
        available = int(next(line.split()[1] for line in meminfo.read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        return shutil.disk_usage(disk_path).free >= 5 * 1024**3 and available >= 128 * 1024**2
    except (OSError, ValueError, StopIteration):
        return False
