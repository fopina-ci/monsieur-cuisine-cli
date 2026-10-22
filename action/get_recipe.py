#!/usr/bin/env python3
"""Fetch one recipe through the CLI and save its JSON response."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from recipe_to_markdown import write_markdown_file


def main() -> None:
    recipe = os.environ.get('RECIPE', '').strip()
    session_token = os.environ.get('SESSION_TOKEN', '')
    output_dir = Path(os.environ.get('OUTPUT_DIR', 'build/recipes'))
    if not recipe:
        raise ValueError('recipe must be a positive recipe ID or a full Monsieur Cuisine recipe URL')
    if not session_token:
        raise ValueError('session_token is required to fetch a recipe; pass the accessToken from session.json')

    parsed_url = urlsplit(recipe)
    if parsed_url.scheme.lower() in {'http', 'https'}:
        if not parsed_url.netloc:
            raise ValueError('recipe URL must include a hostname')
        subcommand = 'url'
    elif re.fullmatch(r'[1-9][0-9]*', recipe):
        subcommand = 'get'
    else:
        raise ValueError('recipe must be a positive numeric ID or a full HTTP(S) recipe URL')

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mc-recipe-') as temp_dir:
        session_path = Path(temp_dir) / 'session.json'
        session_path.write_text(json.dumps({'accessToken': session_token}), encoding='utf-8')
        session_path.chmod(0o600)
        result = subprocess.run(
            [
                'monsieur-cuisine-cli',
                '--session-file',
                str(session_path),
                'recipes',
                subcommand,
                recipe,
                '--json',
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    if result.returncode:
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)
        raise SystemExit(result.returncode)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f'CLI did not return valid JSON: {exc}') from exc
    recipe_file = output_dir / 'recipe.json'
    recipe_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown_dir = Path(os.environ.get('MARKDOWN_OUTPUT_DIR', 'recipes'))
    markdown_file = write_markdown_file(payload, recipe, markdown_dir)
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write(f'output-directory={output_dir.resolve()}\n')
        output.write(f'markdown-file={markdown_file.as_posix()}\n')
    print(f'Fetched recipe JSON: {recipe_file.resolve()}')
    print(f'Created recipe Markdown: {markdown_file}')


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
