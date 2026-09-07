# SPDX-License-Identifier: GPL-3.0-only
# Matching snippets from MapleEve/lifesmart-for-homeassistant (GPL-3.0).
"""Patch the persistent local TCP task in a staged LifeSmart copy only."""
import argparse
import ast
import os
from pathlib import Path
import stat
import tempfile

OLD = '''            self._local_task = self.hass.async_create_task(
                self.client.async_connect(self._local_update_callback)
            )'''
NEW = '''            self._local_task = self.config_entry.async_create_background_task(
                self.hass,
                self.client.async_connect(self._local_update_callback),
                "lifesmart-local-tcp",
            )'''


def patched(source):
    """Fail closed on a different source; repeated application is a no-op."""
    normalized = source.replace('\r\n', '\n')
    ast.parse(normalized)
    if normalized.count(OLD) == 0 and normalized.count(NEW) == 1:
        return source, False
    if normalized.count(OLD) != 1 or normalized.count(NEW) != 0:
        raise ValueError('Unsupported source: expected exactly one original local task block')
    updated = normalized.replace(OLD, NEW, 1)
    ast.parse(updated)
    if '\r\n' in source:
        updated = updated.replace('\n', '\r\n')
    return updated, True


def apply(component, *, check=False):
    path = Path(component) / 'hub.py'
    if path.is_symlink():
        raise ValueError('Refusing a symlink; use an independent staged copy')
    original = path.read_bytes()
    updated, changed = patched(original.decode('utf-8'))
    if not changed or check:
        return changed
    fd, temporary = tempfile.mkstemp(prefix='.startup-', suffix='.py', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(updated.encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        if path.read_bytes() != original:
            raise ValueError('Source changed during staging; refusing replacement')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', type=Path)
    parser.add_argument('--check', action='store_true', help='Validate only; do not write')
    args = parser.parse_args()
    changed = apply(args.component, check=args.check)
    print('Patch applicable' if changed and args.check else 'Patched staged hub.py' if changed else 'Already patched')


if __name__ == '__main__':
    main()
