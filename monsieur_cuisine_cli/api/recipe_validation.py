"""Locale-aware recipe dropdown validation shared by CLI and integrations."""

from __future__ import annotations

from ..locales import SUPPORTED_LOCALES
from ..recipe_validation_data import LOCALE_VALIDATION_DATA

_FIELD_TO_GUIDE = {
    'categoryIds': ('category_options', 'id'),
    'deviceTypeIds': ('device_options', 'id'),
    'complexityId': ('level_options', 'id'),
}


def canonical_locale(locale: str) -> str:
    """Return the canonical supported locale or raise a useful error."""
    canonical = next((supported for supported in SUPPORTED_LOCALES if supported.casefold() == locale.casefold()), None)
    if canonical is None:
        raise RuntimeError(f'Unsupported locale {locale!r}; choose one of: {", ".join(SUPPORTED_LOCALES)}.')
    return canonical


def resolve_markdown_option(field: str, value: str, locale: str) -> dict:
    """Resolve a localized dropdown label or slug parsed from Markdown.

    Integrations that parse recipe Markdown can use the same locale data as the
    CLI. Supported fields are categories, devices, complexity, serving units,
    and ingredient units. Text matching is case-insensitive after trimming.
    """
    canonical = canonical_locale(locale)
    guide_field, searchable_keys = _markdown_guide_field(field)
    options = LOCALE_VALIDATION_DATA.get(canonical, {}).get(guide_field, [])
    needle = value.strip().casefold()
    for option in options:
        candidates = [option.get(key, '') for key in searchable_keys]
        if any(isinstance(candidate, str) and candidate.strip().casefold() == needle for candidate in candidates):
            return option
    raise RuntimeError(f'Unknown {field} value {value!r} for locale {canonical}.')


def _markdown_guide_field(field: str) -> tuple[str, tuple[str, ...]]:
    fields = {
        'category': ('category_options', ('name', 'slug')),
        'device': ('device_options', ('name', 'slug')),
        'complexity': ('level_options', ('name', 'slug')),
        'serving_unit': ('serving_units', ('unit_name',)),
        'ingredient_unit': ('ingredient_units', ('unit_name', 'unit_short_name')),
    }
    if field not in fields:
        raise RuntimeError(f'Unsupported localized dropdown field {field!r}.')
    return fields[field]


def validate_recipe_options(payload: dict, locale: str) -> None:
    """Validate locale-specific dropdown IDs and unit labels in a write payload."""
    canonical = canonical_locale(locale)
    guide = LOCALE_VALIDATION_DATA.get(canonical)
    if not guide:
        raise RuntimeError(f'No dropdown validation data is available for {canonical}; refresh the locale data.')

    issues = []
    for field, (guide_field, _) in _FIELD_TO_GUIDE.items():
        if field not in payload:
            continue
        values = payload[field] if isinstance(payload[field], list) else [payload[field]]
        available = {option.get('id') for option in guide[guide_field] if isinstance(option.get('id'), int)}
        for value in values:
            if isinstance(value, int) and not isinstance(value, bool) and value not in available:
                issues.append(f'{field} value {value} is not available for {canonical}.')

    language_locale = payload.get('languageLocale')
    if 'languageLocale' in payload and not isinstance(language_locale, str):
        issues.append('languageLocale must be a supported locale string.')
    elif isinstance(language_locale, str):
        try:
            canonical_locale(language_locale)
        except RuntimeError:
            issues.append(
                f'languageLocale {language_locale!r} is unsupported; choose one of: {", ".join(SUPPORTED_LOCALES)}.'
            )

    serving_units = {option.get('unit_name') for option in guide['serving_units'] if isinstance(option, dict)}
    ingredient_units = {
        name
        for option in guide['ingredient_units']
        if isinstance(option, dict)
        for name in (option.get('unit_name'), option.get('unit_short_name'))
        if isinstance(name, str)
    }
    for size_index, serving_size in enumerate(payload.get('servingSizes', [])):
        if not isinstance(serving_size, dict):
            continue
        unit = serving_size.get('unit')
        if isinstance(unit, str) and unit not in serving_units:
            issues.append(f'servingSizes[{size_index}].unit {unit!r} is not available for {canonical}.')
        for group_index, group in enumerate(serving_size.get('ingredientGroups', [])):
            if not isinstance(group, dict):
                continue
            for ingredient_index, ingredient in enumerate(group.get('ingredients', [])):
                if not isinstance(ingredient, dict):
                    continue
                unit = ingredient.get('unit')
                if isinstance(unit, str) and unit not in ingredient_units:
                    issues.append(
                        f'servingSizes[{size_index}].ingredientGroups[{group_index}]'
                        f'.ingredients[{ingredient_index}].unit {unit!r} is not available for {canonical}.'
                    )

    if issues:
        raise RuntimeError('Recipe payload contains unavailable dropdown values:\n- ' + '\n- '.join(issues))
