#!/usr/bin/env python3
"""Publish converted cookbook recipes and open a PR for newly recorded IDs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, check=False, text=True, env=env)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f'Command failed: {command[0]}')
    return result


def summary(message: str) -> None:
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        with Path(path).open('a', encoding='utf-8') as output:
            output.write(f'- {message}\n')


def set_secret(token: str) -> None:
    repo = os.environ.get('GITHUB_REPOSITORY')
    secret_writer = os.environ.get('GH_SECRETS_WRITE_TOKEN', '')
    if not secret_writer:
        raise RuntimeError('GH_SECRETS_WRITE_TOKEN is required to persist a refreshed MC_API_ACCESS_TOKEN.')
    result = subprocess.run(
        ['gh', 'secret', 'set', 'MC_API_ACCESS_TOKEN', '--repo', repo or ''],
        input=token,
        capture_output=True,
        check=False,
        text=True,
        env={**os.environ, 'GH_TOKEN': secret_writer},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Could not update the MC_API_ACCESS_TOKEN repository secret.')


def recipe_id_from_result(raw: str) -> str:
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'CLI returned invalid JSON: {exc}') from exc
    if isinstance(result, dict) and isinstance(result.get('recipe'), dict):
        result = result['recipe']
    if isinstance(result, dict):
        identifier = result.get('id') or result.get('recipeId')
        if identifier:
            return str(identifier)
    return ''


def get_account_recipes(session_file: Path) -> list[dict]:
    from monsieur_cuisine_cli.api.recipes import list_my_recipes

    recipes: list[dict] = []
    page = 1
    while True:
        result = list_my_recipes(page, 100, session_file=str(session_file))
        if not isinstance(result, dict):
            raise RuntimeError(f'Recipe list returned an unexpected response for page {page}.')
        page_recipes = result.get('recipes', [])
        if isinstance(page_recipes, list):
            recipes.extend(recipe for recipe in page_recipes if isinstance(recipe, dict))
        if page >= int(result.get('totalPage', page)):
            return recipes
        page += 1


def match_recipe_id(account: list[dict], payload: dict) -> str:
    title = str(payload.get('title', '')).strip().casefold()
    locale = str(payload.get('languageLocale', '')).strip().casefold()
    matches = [recipe for recipe in account if str(recipe.get('title', '')).strip().casefold() == title]
    same_locale = [recipe for recipe in matches if str(recipe.get('languageLocale', '')).strip().casefold() == locale]
    if same_locale:
        matches = same_locale
    if len(matches) > 1:
        identifiers = ', '.join(str(recipe.get('id')) for recipe in matches)
        raise RuntimeError(
            f'Multiple recipes match title {payload.get("title")!r} (IDs: {identifiers}); set recipeId explicitly.'
        )
    return str(matches[0].get('id', '')) if matches else ''


def source_recipe_link(source: Path, recipe_id: str, payload: dict) -> bool:
    locale = str(payload.get('languageLocale') or 'pt-PT').replace('_', '-').lower()
    url = f'https://www.monsieur-cuisine.com/{locale}/previsao-da-receita?recipe-id={recipe_id}'
    replacement = f'| recipeId | [{url}]({url}) |'
    lines = source.read_text(encoding='utf-8').splitlines()
    heading = next((i for i, line in enumerate(lines) if re.match(r'^##\s+Recipe\s*$', line, re.I)), None)
    if heading is None:
        raise RuntimeError(f'{source} has no ## Recipe table')
    table_end = next((i for i in range(heading + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    id_row = next(
        (i for i in range(heading + 1, table_end) if re.match(r'^\s*\|\s*recipeId\s*\|', lines[i], re.I)), None
    )
    if id_row is not None:
        if lines[id_row] == replacement:
            return False
        lines[id_row] = replacement
    else:
        separator = next((i for i in range(heading + 1, table_end) if re.match(r'^\s*\|\s*:?-{3,}', lines[i])), None)
        if separator is None:
            raise RuntimeError(f'{source} has no Markdown table separator under ## Recipe')
        lines.insert(separator + 1, replacement)
    source.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return True


def publish_one(
    recipe_file: Path,
    account: list[dict],
    session_file: Path,
) -> tuple[str, bool, bool, dict]:
    payload = json.loads(recipe_file.read_text(encoding='utf-8'))
    id_file = recipe_file.with_suffix('.id')
    source_file = recipe_file.with_suffix('.source')
    if not source_file.is_file():
        raise RuntimeError(f'Missing Markdown source sidecar for {recipe_file.name}.')
    recipe_id = id_file.read_text(encoding='utf-8').strip() if id_file.is_file() else ''
    if not recipe_id:
        recipe_id = match_recipe_id(account, payload)

    cli = ['monsieur-cuisine-cli', '--session-file', str(session_file), 'recipes']
    cli += ['update', recipe_id] if recipe_id else ['create']
    for suffix, option in (('.thumbnail', '--thumbnail'), ('.details-image', '--details-image')):
        sidecar = recipe_file.with_suffix(suffix)
        if sidecar.is_file() and sidecar.stat().st_size:
            cli.extend((option, sidecar.read_text(encoding='utf-8').strip()))
    cli.extend(('--data', json.dumps(payload, ensure_ascii=False), '--json'))
    result = run(cli, check=False)
    publish_warning = False
    if result.returncode:
        publish_warning = True
        private_error = result.stderr.strip().replace('\n', ' ')
        draft = dict(payload)
        draft['status'] = 'draft'
        cli[cli.index('--data') + 1] = json.dumps(draft, ensure_ascii=False)
        draft_result = run(cli, check=False)
        if draft_result.returncode:
            raise RuntimeError(
                f'Unable to publish {recipe_file.name}; draft fallback failed. '
                f'Publish error: {private_error or "unknown"}. '
                f'Draft error: {draft_result.stderr.strip().replace(chr(10), " ") or "unknown"}.'
            )
        result = draft_result
        summary(
            f'{recipe_file.name} was saved as a draft because private publishing failed: {private_error or "unknown error"}'
        )
    print(result.stdout, end='')
    if recipe_id:
        saved_id = recipe_id
    else:
        saved_id = recipe_id_from_result(result.stdout)
    if not saved_id:
        raise RuntimeError(f'{recipe_file.name} was saved but the API response did not include a recipe ID.')
    source = Path(source_file.read_text(encoding='utf-8').strip())
    changed = source_recipe_link(source, saved_id, payload)
    return saved_id, changed, publish_warning, payload


def open_id_pull_request(changed_sources: list[Path]) -> None:
    if not changed_sources:
        return
    run_id = os.environ.get('GITHUB_RUN_ID', 'manual')
    run_attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    branch = f'recipe-ids/{run_id}-{run_attempt}'
    run(['git', 'config', 'user.name', 'github-actions[bot]'])
    run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    run(['git', 'switch', '-c', branch])
    run(['git', 'add', '--', *(str(path) for path in changed_sources)])
    staged = run(['git', 'diff', '--cached', '--quiet'], check=False)
    if staged.returncode == 0:
        return
    run(['git', 'commit', '-m', 'Record Monsieur Cuisine recipe IDs'])
    run(['git', 'push', 'origin', branch])
    result = run(
        [
            'gh',
            'pr',
            'create',
            '--base',
            os.environ.get('GITHUB_BASE_REF') or 'main',
            '--head',
            branch,
            '--title',
            'Record recipe IDs after publishing',
            '--body',
            'Adds Monsieur Cuisine recipe links to Markdown recipe metadata after publishing.',
        ],
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Could not open the recipe ID pull request.')
    print(result.stdout, end='')


def main() -> int:
    token = os.environ.get('SESSION_TOKEN', '')
    gh_token = os.environ.get('GH_TOKEN', '')
    recipe_dir = Path(os.environ.get('RECIPE_JSON_DIR', 'build/recipes'))
    if not token:
        raise RuntimeError('The session_token input is required for publishing.')
    if not gh_token:
        raise RuntimeError('The github_token input is required for publishing.')
    files = sorted(recipe_dir.glob('*.json'))
    if not files:
        raise RuntimeError(f'No converted recipe JSON files found in {recipe_dir}.')

    with tempfile.TemporaryDirectory(prefix='mc-publish-') as temp_dir:
        session_file = Path(temp_dir) / 'session.json'
        session_file.write_text(json.dumps({'accessToken': token}), encoding='utf-8')
        session_file.chmod(0o600)
        original_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        if os.environ.get('GH_SECRETS_WRITE_TOKEN'):
            run(['monsieur-cuisine-cli', '--session-file', str(session_file), 'auth', 'renew'])
            token = json.loads(session_file.read_text(encoding='utf-8'))['accessToken']
            set_secret(token)
            original_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        else:
            print(
                'GH_SECRETS_WRITE_TOKEN is not configured; token rotations will not persist between workflow runs.',
                file=sys.stderr,
            )

        failed = False
        try:
            account = get_account_recipes(session_file)
            print(f'Loaded {len(account)} existing recipes for title matching.')
            changed_sources: list[Path] = []
            for recipe_file in files:
                try:
                    recipe_id, changed, publish_warning, payload = publish_one(recipe_file, account, session_file)
                    print(f'Published {recipe_file.name} as recipe {recipe_id}.')
                    if not any(str(entry.get('id')) == recipe_id for entry in account):
                        account.append(
                            {
                                'id': recipe_id,
                                'title': payload.get('title'),
                                'languageLocale': payload.get('languageLocale'),
                            }
                        )
                    failed |= publish_warning
                    if changed:
                        source_file = Path(recipe_file.with_suffix('.source').read_text(encoding='utf-8').strip())
                        changed_sources.append(source_file)
                except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    message = f'{recipe_file.name}: {exc}'
                    print(message, file=sys.stderr)
                    summary(message)
                    failed = True
            if changed_sources:
                open_id_pull_request(changed_sources)
        finally:
            final_token = json.loads(session_file.read_text(encoding='utf-8'))['accessToken']
            final_hash = hashlib.sha256(final_token.encode('utf-8')).hexdigest()
            if final_hash != original_hash:
                if os.environ.get('GH_SECRETS_WRITE_TOKEN'):
                    set_secret(final_token)
                else:
                    summary(
                        'The API token was refreshed but could not be saved. '
                        'Update the MC_API_ACCESS_TOKEN secret before the next publish run.'
                    )
                    failed = True
    return int(failed)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
