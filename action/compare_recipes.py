"""Compare two recipe JSON documents and expose the result to GitHub Actions."""

import json
import os
import sys
import uuid
from pathlib import Path


def _write_outputs(equal: bool, report: str) -> None:
    output_file = os.environ.get('GITHUB_OUTPUT')
    if not output_file:
        return
    delimiter = f'comparison_report_{uuid.uuid4().hex}'
    with open(output_file, 'a', encoding='utf-8') as handle:
        handle.write(f'recipes-equal={str(equal).lower()}\n')
        handle.write(f'comparison-report<<{delimiter}\n{report}\n{delimiter}\n')


def main() -> int:
    source_name = os.environ.get('COMPARE_SOURCE', '')
    target_name = os.environ.get('COMPARE_TARGET', '')
    if not source_name or not target_name:
        print('compare_source and compare_target are required.', file=sys.stderr)
        return 1

    source_path = Path(source_name)
    target_path = Path(target_name)
    try:
        with source_path.open(encoding='utf-8') as source_file:
            source = json.load(source_file)
        with target_path.open(encoding='utf-8') as target_file:
            target = json.load(target_file)
    except (OSError, json.JSONDecodeError) as exc:
        message = f'Could not compare recipe JSON ({source_path}, {target_path}): {exc}'
        print(message, file=sys.stderr)
        return 1

    equal = source == target
    report = 'Recipe JSON documents are identical.' if equal else 'Recipe JSON documents differ.'
    print(report)
    _write_outputs(equal, report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
