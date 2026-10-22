from pathlib import Path

from action.convert import parse_recipe


def test_sample_recipe_ignores_table_header_and_allows_unitless_ingredients():
    fixture = Path(__file__).parent / 'action-fixtures' / 'soup.md'

    payload, recipe_id, _, _ = parse_recipe(fixture)

    assert recipe_id == 42
    assert payload['languageLocale'] == 'en-US'
    ingredients = payload['servingSizes'][0]['ingredientGroups'][0]['ingredients']
    assert ingredients[1]['unit'] == ''
