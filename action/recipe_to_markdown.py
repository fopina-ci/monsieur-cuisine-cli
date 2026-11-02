#!/usr/bin/env python3
"""Write a fetched recipe response in the cookbook Markdown format."""

import json
import re
import unicodedata
from pathlib import Path


def _markdown(value: object) -> str:
    if value is None:
        return ''
    return str(value).replace('|', r'\|').replace('\r\n', '<br>').replace('\n', '<br>').strip()


def _ids(values: object) -> str:
    if not isinstance(values, list):
        return ''
    return ', '.join(
        str(value.get('id') if isinstance(value, dict) else value)
        for value in values
        if value and (not isinstance(value, dict) or value.get('id'))
    )


def normalize_recipe_response(payload: object) -> object:
    """Normalize public-recipe CLI responses to the shape used by the exporter.

    ``recipes url`` may return a transport wrapper containing another ``recipe``
    object, with public-site field names (``name`` and ``language``). Keep the
    wrapper metadata, but make the actual recipe conform to the established
    ``title``/``languageLocale`` representation.
    """
    if not isinstance(payload, dict):
        return payload
    response = dict(payload)
    recipe = response.get('recipe')
    while isinstance(recipe, dict) and isinstance(recipe.get('recipe'), dict):
        recipe = recipe['recipe']
    if not isinstance(recipe, dict):
        return response
    normalized = dict(recipe)
    if not normalized.get('title') and normalized.get('name'):
        normalized['title'] = normalized['name']
    if not normalized.get('languageLocale') and normalized.get('language'):
        normalized['languageLocale'] = normalized['language']

    # The public endpoint uses product-generation codes; the cookbook format
    # requires IDs from the localized device dropdown.
    if not normalized.get('deviceTypeIds') and isinstance(normalized.get('deviceTypes'), list):
        device_ids = {'MC2.0': 12, 'MC3.0': 13}
        codes = normalized['deviceTypes']
        if codes and all(isinstance(code, str) and code in device_ids for code in codes):
            normalized['deviceTypeIds'] = [device_ids[code] for code in codes]

    serving_sizes = normalized.get('servingSizes')
    if isinstance(serving_sizes, list):
        converted_servings = []
        for item in serving_sizes:
            if not isinstance(item, dict):
                converted_servings.append(item)
                continue
            serving = dict(item)
            # Public recipe responses use the API's legacy field names while
            # the cookbook Markdown format uses the CLI's canonical names.
            for source, target in (
                ('servingUnit', 'unit'),
                ('preparationDuration', 'preparationTime'),
                ('duration', 'readyInTime'),
            ):
                if target not in serving and source in serving:
                    serving[target] = serving[source]

            groups = serving.get('ingredientGroups')
            ingredients = serving.get('ingredients')
            if isinstance(groups, list) and isinstance(ingredients, list):
                # Public API responses return group descriptors separately
                # from a flat ingredient list linked through group IDs.
                converted_groups = []
                assigned = set()
                for group in groups:
                    if not isinstance(group, dict):
                        converted_groups.append(group)
                        continue
                    converted_group = dict(group)
                    if not converted_group.get('ingredients'):
                        group_id = converted_group.get('id')
                        matching = [
                            ingredient
                            for ingredient in ingredients
                            if isinstance(ingredient, dict) and ingredient.get('ingredientGroupId') == group_id
                        ]
                        converted_group['ingredients'] = matching
                        assigned.update(id(ingredient) for ingredient in matching)
                    converted_groups.append(converted_group)
                unassigned = [
                    ingredient
                    for ingredient in ingredients
                    if not isinstance(ingredient, dict) or id(ingredient) not in assigned
                ]
                if unassigned:
                    converted_groups.append({'name': 'Ingredients', 'ingredients': unassigned})
                serving['ingredientGroups'] = converted_groups
            elif not groups and isinstance(ingredients, list):
                serving['ingredientGroups'] = [{'name': 'Ingredients', 'ingredients': ingredients}]

            steps = serving.get('steps')
            if isinstance(steps, list):
                serving['steps'] = [
                    (
                        {**step, 'title': step['name']}
                        if isinstance(step, dict) and not step.get('title') and step.get('name')
                        else step
                    )
                    for step in steps
                ]
            converted_servings.append(serving)
        normalized['servingSizes'] = converted_servings

    response['recipe'] = normalized
    return response


def write_markdown_file(payload: object, requested_recipe: str, output_dir: str | Path) -> Path:
    """Render a CLI recipe response to Markdown and return the created path."""
    payload = normalize_recipe_response(payload)
    response = payload if isinstance(payload, dict) else None
    recipe = response.get('recipe', response) if response else None
    if not isinstance(recipe, dict):
        raise ValueError('The CLI response did not contain a recipe object.')

    title = str(recipe.get('title') or '').strip()
    locale = str(recipe.get('languageLocale') or response.get('viewerLang') or '').strip()
    recipe_id = response.get('recipeId') or recipe.get('id')
    device_ids = _ids(recipe.get('deviceTypeIds') or recipe.get('deviceTypes'))
    serving_sizes = recipe.get('servingSizes')
    if not title or not locale or not device_ids or not isinstance(serving_sizes, list) or not serving_sizes:
        raise ValueError('The recipe is missing a title, locale, device type, or serving size.')

    serving = next((item for item in serving_sizes if isinstance(item, dict) and item.get('isDefault')), None)
    if serving is None:
        serving = next((item for item in serving_sizes if isinstance(item, dict)), None)
    unit = serving.get('unit') if serving else None
    if isinstance(unit, dict):
        unit = unit.get('name') or unit.get('unit')
    if serving is None or not unit or serving.get('amount') is None:
        raise ValueError('The recipe has no usable serving size.')

    metadata = [
        ('languageLocale', locale),
        ('deviceTypeIds', device_ids),
        ('servings', f'{serving["amount"]} ({unit})'),
    ]
    if re.fullmatch(r'[1-9][0-9]*', requested_recipe.strip()):
        metadata.append(('recipeId', requested_recipe.strip()))
    for field in ('preparationTime', 'readyInTime'):
        value = serving.get(field, recipe.get(field))
        if value is not None:
            metadata.append((field, value))

    groups = serving.get('ingredientGroups') or []
    if groups and isinstance(groups[0], dict) and groups[0].get('name'):
        metadata.append(('ingredientGroupName', groups[0]['name']))
    category_ids = _ids(recipe.get('categories') or recipe.get('categoryIds'))
    if category_ids:
        metadata.append(('categoryIds', category_ids))
    complexity = recipe.get('complexity')
    if isinstance(complexity, dict) and complexity.get('id'):
        metadata.append(('complexityId', complexity['id']))
    elif isinstance(complexity, str) and complexity.strip():
        # The legacy public response returns a localized label rather than the
        # dropdown ID; the Markdown importer resolves either representation.
        metadata.append(('complexityId', complexity))
    if recipe.get('hintsAndTips'):
        metadata.append(('hintsAndTips', recipe['hintsAndTips']))

    lines = [
        f'# {title}',
        '',
        _markdown(recipe.get('description')),
        '',
        '## Recipe',
        '',
        '| Field | Value |',
        '| --- | --- |',
    ]
    lines.extend(f'| {_markdown(key)} | {_markdown(value)} |' for key, value in metadata)
    lines.extend(['', '## Ingredients', ''])
    ingredient_count = 0
    for group in groups:
        if not isinstance(group, dict):
            continue
        for ingredient in group.get('ingredients') or []:
            if not isinstance(ingredient, dict) or not ingredient.get('name'):
                continue
            unit_value = ingredient.get('unit') or ''
            if isinstance(unit_value, dict):
                unit_value = unit_value.get('name') or unit_value.get('unit') or ''
            details = {
                'amount': str(ingredient.get('amount') if ingredient.get('amount') is not None else ''),
                'unit': unit_value,
                'isOptional': bool(ingredient.get('isOptional', False)),
            }
            annotation = json.dumps(details, ensure_ascii=False, separators=(',', ':'))
            lines.append(f'- {_markdown(ingredient["name"])} <!-- mc-ingredient: {annotation} -->')
            ingredient_count += 1
    if not ingredient_count:
        raise ValueError('The recipe has no ingredients to write to Markdown.')

    steps = [step for step in (serving.get('steps') or []) if isinstance(step, dict)]
    if not steps:
        raise ValueError('The recipe has no steps to write to Markdown.')
    lines.extend(['', '## Steps', ''])
    for index, step in enumerate(steps, 1):
        step_title = _markdown(step.get('title') or title)
        description = _markdown(step.get('description'))
        line = f'{index}. **{step_title}**: {description}'
        if isinstance(step.get('mode'), dict):
            mode = json.dumps(step['mode'], ensure_ascii=False, separators=(',', ':'))
            line += f' <!-- mc-mode: {mode} -->'
        lines.append(line)

    nutrients = recipe.get('nutrients') or []
    if nutrients:
        lines.extend(['', '## Nutrition', '', '| Nutrient | Amount | Unit |', '| --- | --- | --- |'])
        for nutrient in nutrients:
            if isinstance(nutrient, dict):
                amount = nutrient.get('amount', nutrient.get('amountFloat', ''))
                lines.append(
                    f'| {_markdown(nutrient.get("name"))} | {_markdown(amount)} | {_markdown(nutrient.get("unit"))} |'
                )

    slug = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-') or 'recipe'
    suffix = re.sub(r'[^A-Za-z0-9-]+', '', str(recipe_id)) if recipe_id else slug
    recipe_path = Path(output_dir) / f'{slug}-{suffix or slug}.md'
    if recipe_path.exists():
        raise ValueError(f'{recipe_path} already exists; refusing to overwrite it.')
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    return recipe_path
