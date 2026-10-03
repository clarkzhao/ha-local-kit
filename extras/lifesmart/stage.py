# SPDX-License-Identifier: GPL-3.0-only
"""Apply LifeSmart compatibility patches to a new independent directory."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def stage(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError('Output must be outside the source directory')
    shutil.copytree(source, output)
    tools = Path(__file__).resolve().parent
    for name in ('patch-vrf.py', 'patch-updates.py', 'patch-light.py', 'patch-refresh.py'):
        subprocess.run([sys.executable, str(tools / name), str(output)], check=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Unpatched integration at the documented upstream commit')
    parser.add_argument('output', type=Path, help='New directory outside the source')
    args = parser.parse_args()
    output = stage(args.source, args.output)
    print('Prepared:', output)
    print('Review the diff and run the HA regression scripts before installation.')


if __name__ == '__main__':
    main()
