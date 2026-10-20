import json
from pathlib import Path

from click.testing import CliRunner

from monsieur_cuisine_cli.api import auth, recipes
from monsieur_cuisine_cli.commands.cli import CLI

FIXTURES = Path(__file__).parent / 'fixtures'


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def _assert_cli_json(args, expected):
    result = CliRunner().invoke(CLI.click, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert 'code' not in json.loads(result.output)
    assert 'message' not in json.loads(result.output)


def test_profile_command_matches_captured_response_shape(monkeypatch):
    expected = _fixture('profile.json')
    monkeypatch.setattr(auth, 'get_profile', lambda *args, **kwargs: expected)

    _assert_cli_json(['profile'], expected)


def test_recipes_list_command_matches_captured_response_shape(monkeypatch):
    expected = _fixture('recipes-list.json')
    monkeypatch.setattr(recipes, 'list_my_recipes', lambda *args, **kwargs: expected)

    _assert_cli_json(['recipes', 'list'], expected)


def test_recipes_get_command_matches_captured_response_shape(monkeypatch):
    expected = _fixture('recipe-get.json')
    monkeypatch.setattr(recipes, 'get_my_recipe', lambda *args, **kwargs: expected)

    _assert_cli_json(['recipes', 'get', '1'], expected)
