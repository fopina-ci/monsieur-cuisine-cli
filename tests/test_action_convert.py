import json
from pathlib import Path

import pytest

from action.convert import _files_to_convert, parse_recipe


def test_sample_recipe_ignores_table_header_and_allows_unitless_ingredients():
    fixture = Path(__file__).parent / 'action-fixtures' / 'soup.md'

    payload, recipe_id, _, _ = parse_recipe(fixture)

    assert recipe_id == 42
    assert payload['languageLocale'] == 'en-US'
    ingredients = payload['servingSizes'][0]['ingredientGroups'][0]['ingredients']
    assert ingredients[1]['unit'] == ''


def test_recipe_validation_rejects_missing_complexity(tmp_path):
    fixture = Path(__file__).parent / 'action-fixtures' / 'soup.md'
    recipe = tmp_path / 'soup.md'
    recipe.write_text(
        fixture.read_text(encoding='utf-8')
        .replace('| complexityId | 22 |\n', '')
        .replace('![Tomato soup details photo](assets/tiny.png)\n', ''),
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='complexityid'):
        parse_recipe(recipe)


def test_recipe_files_json_selects_only_requested_markdown(tmp_path, monkeypatch):
    recipes = tmp_path / 'recipes'
    recipes.mkdir()
    selected = recipes / 'selected.md'
    untouched = recipes / 'untouched.md'
    selected.touch()
    untouched.touch()
    monkeypatch.chdir(tmp_path)

    files = _files_to_convert('recipes/**/*.md', json.dumps(['recipes/selected.md']))

    assert files == [Path('recipes/selected.md')]


def test_recipe_files_json_rejects_paths_outside_the_repository():
    with pytest.raises(ValueError, match='repo-relative Markdown paths'):
        _files_to_convert('recipes/**/*.md', json.dumps(['../outside.md']))
