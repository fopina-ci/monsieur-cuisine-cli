#!/usr/bin/env -S python3 -u

import argparse
import re
from pathlib import Path

VERSION_PY = Path(__file__).parent.parent / 'monsieur_cuisine_cli' / '__init__.py'
VERSION_RE = re.compile(r"__version__\s*=\s*(['\"])(.*?)\1")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--set', type=str, metavar='VERSION', help='New version')
    args = p.parse_args()

    data = VERSION_PY.read_text()
    match = VERSION_RE.search(data)
    if not match:
        raise Exception('could not find version')
    version = match.group(2)
    print(f'Current version: {version}')

    if args.set:
        VERSION_PY.write_text(VERSION_RE.sub(f"__version__ = '{args.set}'", data))
        print(f'New version: {args.set}')


if __name__ == '__main__':
    main()
