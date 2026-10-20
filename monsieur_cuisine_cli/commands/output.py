"""Human-readable and machine-readable command output helpers."""

import json

import click


def emit(data: object, as_json: bool = False) -> None:
    """Print normalized response data as JSON or readable field/value lines."""
    if as_json:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if data is None:
        click.echo('No data.')
        return

    if isinstance(data, dict):
        if isinstance(data.get('recipes'), list):
            recipes = data['recipes']
            click.echo(
                f'Recipes: {len(recipes)} (page {data.get("currentPage", "?")} of '
                f'{data.get("totalPage", "?")}; {data.get("total", "?")} total)'
            )
            for recipe in recipes:
                if not isinstance(recipe, dict):
                    click.echo(f'- {recipe}')
                    continue
                click.echo(
                    f'- {recipe.get("title", "Untitled")} (ID: {recipe.get("id", "?")}; '
                    f'Status: {recipe.get("status", "unknown")})'
                )
            return
        if isinstance(data.get('recipe'), dict):
            data = data['recipe']
        if 'title' in data and ('id' in data or 'status' in data):
            click.echo(f'Title: {data.get("title", "Untitled")}')
            fields = ('id', 'status', 'languageLocale', 'source', 'preparationTime', 'readyInTime', 'sharingUrl')
            for key in fields:
                if key in data and data[key] is not None:
                    click.echo(f'{_label(key)}: {data[key]}')
            return
        _emit_fields(data)
        return

    if isinstance(data, list):
        click.echo(f'Items: {len(data)}')
        for item in data:
            if isinstance(item, dict):
                _emit_fields(item, prefix='- ')
            else:
                click.echo(f'- {item}')
        return

    click.echo(f'Value: {data}')


def _emit_fields(values: dict, prefix: str = '', parent: str = '') -> None:
    for key, value in values.items():
        label = f'{parent}.{_label(key)}' if parent else _label(key)
        if isinstance(value, dict):
            _emit_fields(value, prefix=prefix, parent=label)
        elif isinstance(value, list):
            click.echo(f'{prefix}{label}: {json.dumps(value, ensure_ascii=False)}')
        else:
            click.echo(f'{prefix}{label}: {value if value is not None else "null"}')


def _label(key: str) -> str:
    return ''.join(f' {char.upper()}' if char.isupper() else char.upper() for char in key).strip()
