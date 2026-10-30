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
                            'mode': {'type': 'slow_cooking', 'deviceSettings': [{'time': 900, 'order': 0}]},
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
    assert '<!-- mc-ingredient: {"amount":"800","unit":"g","isOptional":false} -->' in text
    assert '<!-- mc-mode: {"type":"slow_cooking","deviceSettings":[{"time":900,"order":0}]} -->' in text

    payload, recipe_id, _, _ = parse_recipe(path)
    assert recipe_id is None
    assert payload['title'] == 'Tomato soup'
    assert payload['complexityId'] == 22
    assert payload['servingSizes'][0]['ingredientGroups'][0]['ingredients'][0]['amount'] == '800'
    assert payload['servingSizes'][0]['steps'][0]['mode']['type'] == 'slow_cooking'


def test_numeric_recipe_get_keeps_recipe_id_and_refuses_overwrite(recipe_response, tmp_path):
    path = write_markdown_file(recipe_response, '12345', tmp_path)
    assert '| recipeId | 12345 |' in path.read_text(encoding='utf-8')

    with pytest.raises(ValueError, match='refusing to overwrite'):
        write_markdown_file(recipe_response, '12345', tmp_path)
