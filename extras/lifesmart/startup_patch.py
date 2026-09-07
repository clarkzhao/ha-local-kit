# SPDX-License-Identifier: GPL-3.0-only
# Matching snippets from MapleEve/lifesmart-for-homeassistant (GPL-3.0).
"""Generate a patched LifeSmart hub.py; never modify the source file."""
import argparse
import ast
import os
from pathlib import Path

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


def apply(component, *, output=None, check=False):
    path = Path(component) / 'hub.py'
    if path.is_symlink():
        raise ValueError('Refusing a symlink; use an independent staged copy')
    original = path.read_bytes()
    updated, changed = patched(original.decode('utf-8'))
    if not changed or check:
        return changed
    if output is None:
        raise ValueError('An independent output file is required')
    output = Path(output)
    if output.resolve() == path.resolve() or output.is_symlink():
        raise ValueError('Output must not be the source or a symlink')
    # Exclusive output creation avoids overwriting either a concurrent source
    # edit or an existing output. No lock can protect against unrelated editors.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(updated.encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', type=Path)
    parser.add_argument('--output', type=Path, help='New file to review; its parent directory must exist')
    parser.add_argument('--check', action='store_true', help='Validate only; do not write')
    args = parser.parse_args()
    if not args.check and args.output is None:
        parser.error('--output is required unless --check is used')
    changed = apply(args.component, output=args.output, check=args.check)
    print('Patch applicable' if changed and args.check else 'Generated separate patched file; source unchanged' if changed else 'Source already patched; no output written')


if __name__ == '__main__':
    main()
