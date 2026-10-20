import json

import pytest
from click.testing import CliRunner

from monsieur_cuisine_cli.api import auth
from monsieur_cuisine_cli.commands.cli import CLI


@pytest.mark.parametrize(
    ('command', 'payload', 'message'),
    [
        (
            ['recipes', 'create'],
            {'deviceTypes': [{'id': 13, 'code': 'MC3.0'}]},
            'deviceTypes is a response field; use deviceTypeIds (integer IDs).',
        ),
        (
            ['recipes', 'update', '42'],
            {'categories': [{'id': 271, 'name': 'Example'}]},
            'categories is a response field; use categoryIds (integer IDs).',
        ),
        (
            ['recipes', 'update', '42'],
            {'thumbnail': {'landscapeMedia': {'id': 10, 'url': 'https://example.invalid/media'}}},
            'thumbnail.landscapeMedia is an expanded response object; use thumbnail.landscapeMediaId',
        ),
        (
            ['recipes', 'update', '42'],
            {'nutrients': [{'name': 'calories', 'amount': 10, 'amountFloat': 10.0}]},
            'nutrients[0].amountFloat is response-only; provide amount instead.',
        ),
        (
            ['recipes', 'update', '42'],
            {'servingSizes': [{'amount': 2, 'modules': [], 'steps': []}]},
            'servingSizes[0].modules is response-only; remove it from the payload.',
        ),
    ],
)
def test_recipe_write_commands_reject_response_shapes(monkeypatch, command, payload, message):
    calls = []
    monkeypatch.setattr(auth, 'call_api', lambda *args, **kwargs: calls.append((args, kwargs)))
    args = [*command, '--data', json.dumps(payload)]

    result = CliRunner().invoke(CLI.click, args)

    assert result.exit_code == 1
    assert message in result.output
    assert calls == []
