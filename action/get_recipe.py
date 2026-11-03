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
    default_config = Path(__file__).resolve().parents[1] / 'monsieur_cuisine_cli' / 'default-config.toml'
    with tempfile.TemporaryDirectory(prefix='mc-recipe-') as temp_dir:
        session_path = Path(temp_dir) / 'session.json'
        session_path.write_text(json.dumps({'accessToken': session_token}), encoding='utf-8')
        session_path.chmod(0o600)
        result = subprocess.run(
            [
                'monsieur-cuisine-cli',
                '--config',
                str(default_config),
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
        if os.environ.get('ACTION_DEBUG', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
            _log_cli_response(result, session_token)
        if result.returncode:
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            raise SystemExit(result.returncode)

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            detail = f'CLI did not return valid JSON: {exc}; stdout was {len(result.stdout)} characters'
            if result.stderr.strip():
                detail += f'; stderr: {result.stderr.strip()[:1000]}'
            raise ValueError(detail) from exc

        # Identify ownership using the authenticated profile, rather than
        # assuming every recipe fetched by ID belongs to the current account.
        from monsieur_cuisine_cli.api.auth import get_profile

        profile = get_profile(config_path=default_config, session_file=str(session_path))
        profile_user = profile.get('user') if isinstance(profile, dict) else None
        user_id = profile_user.get('id') if isinstance(profile_user, dict) else None
        recipe_data = payload
        while isinstance(recipe_data, dict) and isinstance(recipe_data.get('recipe'), dict):
            recipe_data = recipe_data['recipe']
        author = recipe_data.get('author') if isinstance(recipe_data, dict) else None
        author_id = author.get('id') if isinstance(author, dict) else None
        if user_id is None or author_id is None or not recipe_data.get('id'):
            raise ValueError('Could not determine recipe ownership from the authenticated profile and recipe response.')
        is_owned = str(user_id) == str(author_id)
    recipe_file = output_dir / 'recipe.json'
    recipe_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown_dir = Path(os.environ.get('MARKDOWN_OUTPUT_DIR', 'recipes'))
    markdown_file = write_markdown_file(payload, recipe, markdown_dir, is_owned=is_owned)
    recipe_title = ' '.join(str(recipe_data.get('title') or recipe_data.get('name') or '').split())
    image_match = None
    for line in markdown_file.read_text(encoding='utf-8').splitlines():
        image_match = re.fullmatch(r'!\[Details image\]\(([^)]+)\)', line.strip())
        if image_match:
            break
    details_image_file = (markdown_file.parent / image_match.group(1)).as_posix() if image_match else ''
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write(f'output-directory={output_dir.resolve()}\n')
        output.write(f'markdown-file={markdown_file.as_posix()}\n')
        output.write(f'recipe-title={recipe_title}\n')
        output.write(f'details-image-file={details_image_file}\n')
    print(f'Fetched recipe JSON: {recipe_file.resolve()}')
    print(f'Created recipe Markdown: {markdown_file}')


def _log_cli_response(result: subprocess.CompletedProcess, session_token: str) -> None:
    """Write the complete CLI response to Actions logs without exposing tokens.

    Each chunk is JSON-encoded on one line so response text cannot be treated as
    a GitHub Actions workflow command. Concatenating decoded chunks reproduces
    the captured stream exactly (apart from any session token, which is redacted).
    """
    print(f'::group::get-recipe CLI response (exit code {result.returncode})')
    for name, value in (('stdout', result.stdout), ('stderr', result.stderr)):
        if session_token:
            value = value.replace(session_token, '[REDACTED SESSION TOKEN]')
        print(f'{name}: {len(value)} characters')
        if not value:
            print('""')
            continue
        for offset in range(0, len(value), 1000):
            print(json.dumps(value[offset : offset + 1000], ensure_ascii=False))
    print('::endgroup::')


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
