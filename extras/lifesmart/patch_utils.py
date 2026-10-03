# SPDX-License-Identifier: GPL-3.0-only
"""Validate all staged patch targets before writing any of them."""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Expected one matching block: {old[:90]!r}')
    return text.replace(old, new, 1)


def write_patches(updates):
    for path, text in updates.items():
        compile(text, str(path), 'exec')
    for path, text in updates.items():
        newline = '\r\n' if b'\r\n' in path.read_bytes() else '\n'
        path.write_bytes(text.replace('\n', newline).encode('utf-8'))
