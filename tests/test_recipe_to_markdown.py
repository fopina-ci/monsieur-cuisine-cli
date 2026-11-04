from pathlib import Path

import pytest

from action.convert import parse_recipe
from action.recipe_to_markdown import write_markdown_file


@pytest.fixture
def recipe_response():
    return {
        'recipeId': '12345',
        'viewerLang': 'en-US',
        'recipe': {
            'id': 12345,
            'languageLocale': 'en-US',
            'title': 'Tomato soup',
            'description': 'A simple soup.',
            'deviceTypes': [{'id': 13, 'name': 'Monsieur Cuisine connect'}],
            'complexity': {'id': 22, 'name': 'Easy'},
            'servingSizes': [
                {
                    'amount': 2,
                    'unit': 'servings',
                    'isDefault': True,
                    'preparationTime': 5,
                    'readyInTime': 20,
                    'ingredientGroups': [
                        {
                            'name': 'Main ingredients',
                            'ingredients': [{'name': 'Tomatoes', 'amount': '800', 'unit': 'g', 'isOptional': False}],
                        }
                    ],
                    'steps': [
                        {
                            'title': 'Tomato soup',
                            'description': 'Cook the tomatoes.',
                            'deviceSetting': {
                                'mode': 'slow_cooking',
                                'settings': [{'time': 900, 'order': 0}],
                            },
                        }
                    ],
                }
            ],
            'nutrients': [{'name': 'Energy', 'amount': 100, 'unit': 'kCal'}],
        },
    }


def test_recipe_response_exports_to_cookbook_markdown_and_round_trips(recipe_response, tmp_path):
    path = write_markdown_file(recipe_response, 'https://example.com/en/recipe/tomato-soup', tmp_path)

    text = path.read_text(encoding='utf-8')
    assert path.name == 'tomato-soup-12345.md'
    assert '| servings | 2 (servings) |' in text
    assert '| recipeId |' not in text
    assert '- Tomatoes — 800 g' in text
    assert '   **Mode:** **Slow cooking** (`slow_cooking`) · Duration: 15 min' in text

    # Fetching a recipe exports its text and metadata, but the cookbook still
    # needs a local details photo before it is publishable. Model the author
    # adding that required asset before validating the round trip.
    with pytest.raises(ValueError, match='details image is required'):
        parse_recipe(path)
    image = tmp_path / 'details.png'
    image.write_bytes((Path(__file__).parent / 'action-fixtures/assets/tiny.png').read_bytes())
    path.write_text(text.replace('## Recipe', '![Details photo](details.png)\n\n## Recipe'), encoding='utf-8')

    payload, recipe_id, _, _ = parse_recipe(path)
    assert recipe_id is None
    assert payload['title'] == 'Tomato soup'
    assert payload['complexityId'] == 22
    assert payload['servingSizes'][0]['ingredientGroups'][0]['ingredients'][0]['amount'] == '800'
    assert payload['servingSizes'][0]['steps'][0]['mode']['type'] == 'slow_cooking'
    assert payload['servingSizes'][0]['steps'][0]['mode']['deviceSettings'] == [{'order': 0, 'time': 900}]


def test_device_mode_markdown_uses_pt_pt_ui_terms_and_round_trips(recipe_response, tmp_path):
    recipe_response['recipe']['languageLocale'] = 'pt-PT'
    recipe_response['recipe']['complexity'] = {'id': 203, 'name': 'fácil'}
    recipe_response['recipe']['servingSizes'][0]['unit'] = 'porções'
    recipe_response['recipe']['servingSizes'][0]['steps'] = [
        {
            'title': 'Cozinhar',
            'description': 'Cozinhe a maçã.',
            'deviceSetting': {
                'mode': 'customized',
                'reverse': False,
                'settings': [{'temperature': 100, 'time': 480, 'speed': 2, 'speedFloat': 2, 'order': 0}],
            },
        },
        {
            'title': 'Adicionar água',
            'description': 'Adicione água.',
            'deviceSetting': {'mode': 'scale', 'settings': [{'weight': 20, 'order': 0}]},
        },
        {'title': 'Mexer', 'description': 'Mexa.', 'deviceSetting': None},
    ]

    path = write_markdown_file(recipe_response, '10219429', tmp_path)
    text = path.read_text(encoding='utf-8')
    assert (
        '**Modo:** **Cozedura personalizada** (`customized`) · Temperatura: 100 °C · Duração: 8 min. · Velocidade: 2 · Direção: Direita'
        in text
    )
    assert '**Modo:** **Balança** (`scale`) · Peso: 20 g' in text
    assert '3. **Mexer**: Mexa.' in text
    assert '**Mode**' not in text

    # Add the local asset required by cookbook validation.
    image = tmp_path / 'details.png'
    image.write_bytes((Path(__file__).parent / 'action-fixtures/assets/tiny.png').read_bytes())
    path.write_text(text.replace('## Recipe', '![Details photo](details.png)\n\n## Recipe'), encoding='utf-8')
    payload, _, _, _ = parse_recipe(path)
    steps = payload['servingSizes'][0]['steps']
    assert steps[0]['mode'] == {
        'type': 'customized',
        'deviceSettings': [{'order': 0, 'temperature': 100, 'time': 480, 'speed': 2}],
        'reverse': False,
    }
    assert steps[1]['mode'] == {'type': 'scale', 'deviceSettings': [{'order': 0, 'weight': 20}]}
    assert steps[2]['mode'] is None


def test_device_mode_marker_is_required_and_validated():
    from action.mode_markdown import parse_mode

    with pytest.raises(ValueError, match=r'must start with \*\*Mode:\*\* or \*\*Modo:\*\*'):
        parse_mode('**Cozedura personalizada** (`customized`) · Velocidade: 2', 'pt-PT')

    with pytest.raises(ValueError, match='unsupported direction'):
        parse_mode('**Modo:** **Cozedura personalizada** (`customized`) · Direção: Frente', 'pt-PT')


def test_numeric_recipe_get_keeps_recipe_id_and_refuses_overwrite(recipe_response, tmp_path):
    path = write_markdown_file(recipe_response, '12345', tmp_path)
    assert '| recipeId | 12345 |' in path.read_text(encoding='utf-8')

    with pytest.raises(ValueError, match='refusing to overwrite'):
        write_markdown_file(recipe_response, '12345', tmp_path)
