import json

from click.testing import CliRunner

from monsieur_cuisine_cli.commands.cli import CLI


def test_api_command_prints_json_and_passes_options(monkeypatch, tmp_path):
    from monsieur_cuisine_cli.commands import api

    calls = []
    monkeypatch.setattr(api.auth, 'call_api', lambda *args, **kwargs: calls.append((args, kwargs)) or {'ok': True})

    config = tmp_path / 'config.toml'
    config.touch()
    result = CliRunner().invoke(
        CLI.click,
        ['--config', str(config), '--lang', 'de-DE', 'api', 'api/v2/test', '--method', 'POST', '--data', '{"x": 1}'],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {'ok': True}
    assert calls[0][0] == ('api/v2/test',)
    assert calls[0][1]['method'] == 'POST'
    assert calls[0][1]['data'] == {'x': 1}
    assert calls[0][1]['language'] == 'de-DE'


def test_api_command_reports_invalid_json():
    result = CliRunner().invoke(CLI.click, ['api', 'api/v2/test', '--data', '{'])

    assert result.exit_code == 1
    assert '--data must contain valid JSON' in result.output


def test_recipes_get_reports_runtime_error(monkeypatch):
    from monsieur_cuisine_cli.api import recipes

    def fail(*args, **kwargs):
        raise RuntimeError('session is missing')

    monkeypatch.setattr(recipes, 'get_my_recipe', fail)
    result = CliRunner().invoke(CLI.click, ['recipes', 'get', '42'])

    assert result.exit_code == 1
    assert 'Error: session is missing' in result.output
