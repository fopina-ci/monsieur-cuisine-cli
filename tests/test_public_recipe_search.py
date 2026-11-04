import json

from click.testing import CliRunner

from monsieur_cuisine_cli.api import recipes
from monsieur_cuisine_cli.commands.cli import CLI


def test_search_public_recipes_uses_public_endpoint_and_language(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"data":{"total":1,"recipes":[{"id":1,"name":"Pure"}]}}'

    def open_url(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr(recipes.urllib.request, 'urlopen', open_url)

    result = recipes.search_public_recipes('pur\u00e9 ma\u00e7a', language='pt-PT')

    assert result == {'total': 1, 'recipes': [{'id': 1, 'name': 'Pure'}]}
    request, timeout = calls[0]
    assert request.full_url.startswith(f'{recipes.auth.API_BASE}/api/v1/recipes/search/page/1?')
    assert 'q=pur%C3%A9+ma%C3%A7a' in request.full_url
    assert request.get_header('Accept-language') == 'pt-PT'
    assert request.get_header('Authorization') is None
    assert timeout == 30


def test_search_public_recipes_rejects_empty_query_and_invalid_page():
    try:
        recipes.search_public_recipes('  ')
    except RuntimeError as exc:
        assert 'query cannot be empty' in str(exc)
    else:
        raise AssertionError('Empty query should fail.')

    try:
        recipes.search_public_recipes('soup', page=0)
    except RuntimeError as exc:
        assert 'Page must be 1 or greater' in str(exc)
    else:
        raise AssertionError('Invalid page should fail.')


def test_recipes_search_command_prints_json_and_passes_locale(monkeypatch):
    expected = {'total': 1, 'currentPage': 1, 'totalPage': 1, 'recipes': [{'id': 10219429, 'name': 'Puré de maçã'}]}
    calls = []
    monkeypatch.setattr(
        recipes,
        'search_public_recipes',
        lambda *args, **kwargs: calls.append((args, kwargs)) or expected,
    )

    result = CliRunner().invoke(
        CLI.click,
        ['--lang', 'pt-PT', 'recipes', 'search', 'puré maçã', '--json'],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert calls == [(('puré maçã', 1), {'language': 'pt-PT'})]


def test_recipes_search_command_human_output(monkeypatch):
    expected = {
        'total': 21,
        'currentPage': 1,
        'totalPage': 2,
        'recipes': [{'id': 10, 'name': 'Puré de maçã', 'author': {'name': 'Official'}}],
    }
    monkeypatch.setattr(recipes, 'search_public_recipes', lambda *args, **kwargs: expected)

    result = CliRunner().invoke(CLI.click, ['--lang', 'pt-PT', 'recipes', 'search', 'maçã'])

    assert result.exit_code == 0, result.output
    assert 'Public recipes: 1 results on page 1 of 2 (21 total)' in result.output
    assert '- Puré de maçã (ID: 10; by Official)' in result.output
