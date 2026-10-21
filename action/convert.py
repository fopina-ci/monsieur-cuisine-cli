#!/usr/bin/env python3
"""Convert Markdown cookbook recipes into CLI-compatible recipe JSON."""

import glob
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monsieur_cuisine_cli.api.recipe_validation import (
    canonical_locale,
    resolve_markdown_option,
    validate_recipe_options,
)
from monsieur_cuisine_cli.locales import RECIPE_FIELD_LABELS

_METADATA_FIELDS = {
    'languagelocale',
    'locale',
    'language',
    'language/locale',
    'devicetypeids',
    'servings',
    'recipeid',
    'ingredientgroupname',
    'preparationtime',
    'readyintime',
    'categoryids',
    'complexityid',
    'hintsandtips',
    'nutrients',
    'thumbnail',
    'detailsimage',
}


def parse_recipe(path: Path) -> tuple[dict, int | None, Path | None, Path | None]:
    text = path.read_text(encoding='utf-8')
    title_match = re.search(r'^#\s+(.+?)\s*#*\s*$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ''
    description, cover_image = _recipe_intro(text)
    sections = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r'^##\s+(.+?)\s*$', line)
        if heading:
            current = heading.group(1).strip().casefold()
            sections[current] = []
        elif current and line.strip():
            sections[current].append(line.strip())

    metadata = {}
    raw_metadata_rows = []
    for row in _table_rows(sections.get('recipe', [])):
        if len(row) < 2:
            continue
        field, value = row[0].strip(), row[1].strip()
        if field in {'field', 'property'} or not field:
            continue
        raw_metadata_rows.append((field, value))

    locale_labels = {'languagelocale', 'locale', 'language', 'language/locale'}
    localized_locale_labels = {
        labels['languageLocale'].casefold() for labels in RECIPE_FIELD_LABELS.values()
    }
    if not raw_metadata_rows or raw_metadata_rows[0][0].casefold() not in locale_labels | localized_locale_labels:
        raise ValueError('languageLocale must be the first property in the Recipe table')
    locale = canonical_locale(raw_metadata_rows[0][1])
    metadata['languagelocale'] = locale
    localized_labels = RECIPE_FIELD_LABELS.get(locale, {})
    field_aliases = {label.casefold(): field.casefold() for field, label in localized_labels.items()}
    metadata_rows = []
    for field, value in raw_metadata_rows[1:]:
        normalized = field.casefold()
        if normalized in locale_labels or normalized in localized_locale_labels:
            raise ValueError('include languageLocale only once, as the first property in the Recipe table')
        field = field_aliases.get(normalized, normalized)
        if field not in _METADATA_FIELDS:
            raise ValueError(f'unknown Recipe table property {field!r}')
        if field in metadata:
            raise ValueError(f'duplicate Recipe table property {field!r}')
        metadata_rows.append((field, value))
    for field, value in metadata_rows:
        metadata[field] = _parse_metadata_value(field, value, locale)

    nutrients = []
    for row in _table_rows(sections.get('nutrition', [])):
        if len(row) < 3 or row[0].strip().casefold() in {'nutrient', 'name'}:
            continue
        amount = row[1].strip()
        nutrients.append(
            {
                'name': row[0].strip(),
                'amount': int(amount) if amount.isdigit() else amount,
                'unit': row[2].strip(),
            }
        )
    if nutrients:
        metadata['nutrients'] = nutrients

    def section_lines(name: str) -> list[str]:
        return sections.get(name, [])

    def asset_path(field: str) -> Path | None:
        value = metadata.get(field.casefold())
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError(f'{field} must be a non-empty path string')
        asset = Path(value).expanduser()
        if not asset.is_absolute():
            asset = path.parent / asset
        asset = asset.resolve()
        if not asset.is_file():
            raise ValueError(f'{field} image file does not exist: {asset}')
        return asset

    thumbnail_path = _resolve_asset(path, cover_image) if cover_image else asset_path('thumbnail')
    details_image_path = thumbnail_path if cover_image else asset_path('detailsImage')
    ingredients = []
    for line in section_lines('ingredients'):
        item = re.sub(r'^[-*+]\s+', '', line)
        annotation = re.search(r'<!--\s*mc-ingredient:\s*(\{.*\})\s*-->', item)
        details = json.loads(annotation.group(1)) if annotation else {}
        if annotation:
            item = item[: annotation.start()].strip()
        if not isinstance(details, dict):
            raise ValueError('mc-ingredient annotation must be a JSON object')
        unit = details.get('unit', '')
        if unit:
            unit = resolve_markdown_option('ingredient_unit', str(unit), locale)['unit_name']
        ingredients.append(
            {
                'name': item,
                'amount': details.get('amount', ''),
                'unit': unit,
                'isOptional': details.get('isOptional', False),
            }
        )
    steps = []
    for line in section_lines('steps'):
        item = re.sub(r'^\d+[.)]\s+', '', line)
        annotation = re.search(r'<!--\s*mc-mode:\s*(\{.*\})\s*-->', item)
        mode = json.loads(annotation.group(1)) if annotation else None
        if annotation:
            item = item[: annotation.start()].strip()
        title_match = re.match(r'^\*\*(.+?)\*\*:\s*(.*)$', item)
        step_title = title_match.group(1) if title_match else title
        step_description = title_match.group(2) if title_match else item
        if mode is not None and not isinstance(mode, dict):
            raise ValueError('mc-mode annotation must be a JSON object')
        steps.append({'title': step_title, 'description': step_description, 'mode': mode})
    required = ('languagelocale', 'devicetypeids', 'servings')
    missing = [field for field in required if field not in metadata]
    if missing:
        raise ValueError(f'missing Recipe table fields: {", ".join(missing)}')
    if not title:
        raise ValueError('add a recipe title as the first-level Markdown heading (for example, # Tomato soup)')
    if not ingredients:
        raise ValueError('add at least one item under ## Ingredients')
    if not steps:
        raise ValueError('add at least one numbered item under ## Steps')
    servings, serving_unit = metadata['servings']
    device_ids = metadata['devicetypeids']
    if not isinstance(device_ids, list) or not device_ids or any(type(value) is not int for value in device_ids):
        raise ValueError('deviceTypeIds must be a non-empty list of integer IDs')
    recipe_id = metadata.get('recipeid')
    if recipe_id is not None and (not isinstance(recipe_id, int) or isinstance(recipe_id, bool) or recipe_id < 1):
        raise ValueError('recipeId must be a positive integer')

    ingredient_groups = [
        {
            'name': metadata.get('ingredientgroupname', ''),
            'isDefault': True,
            'ingredients': ingredients,
        }
    ]
    payload = {
        'status': 'private-publish',
        'source': 'member',
        'languageLocale': metadata['languagelocale'],
        'deviceTypeIds': device_ids,
        'title': title,
        'description': description,
        'servingSizes': [
            {
                'amount': servings,
                'isDefault': True,
                'unit': serving_unit,
                'instruction': '',
                'preparationTime': int(metadata.get('preparationtime', 0)),
                'readyInTime': int(metadata.get('readyintime', 0)),
                'ingredientGroups': ingredient_groups,
                'steps': steps,
            }
        ],
    }
    for key, field in (
        ('categoryids', 'categoryIds'),
        ('complexityid', 'complexityId'),
        ('hintsandtips', 'hintsAndTips'),
        ('nutrients', 'nutrients'),
    ):
        if key in metadata:
            payload[field] = metadata[key]
    try:
        validate_recipe_options(payload, locale)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    return payload, recipe_id, thumbnail_path, details_image_path


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        if '|' not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if cells and all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _recipe_intro(text: str) -> tuple[str, str | None]:
    lines = text.splitlines()
    title_index = next((i for i, line in enumerate(lines) if re.match(r'^#\s+\S', line)), None)
    if title_index is None:
        return '', None
    index = title_index + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index == len(lines) or lines[index].startswith('## '):
        return '', None

    description_lines = []
    while index < len(lines) and lines[index].strip() and not lines[index].startswith('## '):
        if re.match(r'^!\[[^]]*\]\([^)]+\)$', lines[index].strip()):
            break
        description_lines.append(lines[index].strip())
        index += 1
    description = ' '.join(description_lines)
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        image_match = re.fullmatch(r'!\[[^]]*\]\(([^)]+)\)', lines[index].strip())
        if image_match:
            return description, image_match.group(1).strip()
    return description, None


def _resolve_asset(path: Path, value: str) -> Path:
    asset = Path(value).expanduser()
    if not asset.is_absolute():
        asset = path.parent / asset
    asset = asset.resolve()
    if not asset.is_file():
        raise ValueError(f'cover image file does not exist: {asset}')
    return asset


def _create_thumbnail(source: Path, target: Path) -> Path:
    from PIL import Image, ImageOps

    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        width, height = image.size
        units = min(width // 4, height // 3)
        if units:
            crop_width, crop_height = 4 * units, 3 * units
        elif width / height > 4 / 3:
            crop_width, crop_height = max(1, int(height * 4 / 3)), height
        else:
            crop_width, crop_height = width, max(1, int(width * 3 / 4))
        crop = image.crop((0, 0, crop_width, crop_height))
        if crop_width >= 800 and crop_height >= 600:
            crop = crop.resize((800, 600), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        crop.convert('RGB').save(target, format='JPEG', quality=90, optimize=True)
    return target


def _parse_metadata_value(field: str, value: str, locale: str = 'en-US'):
    value = value.strip().strip('`')
    if field == 'servings':
        match = re.fullmatch(r'(\d+)\s*\(([^()]+)\)', value)
        if not match or int(match.group(1)) < 1 or not match.group(2).strip():
            raise ValueError('servings must include a positive amount and unit, e.g. 4 (frasco)')
        unit = resolve_markdown_option('serving_unit', match.group(2).strip(), locale)['unit_name']
        return int(match.group(1)), unit
    if field in {'devicetypeids', 'categoryids'}:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [item.strip() for item in value.split(',') if item.strip()]
        if not isinstance(parsed, list):
            parsed = [parsed]
        option_field = 'device' if field == 'devicetypeids' else 'category'
        result = []
        for item in parsed:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                result.append(resolve_markdown_option(option_field, str(item), locale)['id'])
        return result
    if field in {'recipeid', 'preparationtime', 'readyintime'}:
        if field == 'recipeid':
            link = re.fullmatch(r'\[[^\]]+\]\((https?://[^)]+)\)', value)
            if link:
                identifiers = parse_qs(urlparse(link.group(1)).query).get('recipe-id', [])
                if len(identifiers) != 1:
                    raise ValueError('recipeId link must include one recipe-id query parameter')
                value = identifiers[0]
        return int(value)
    if field == 'complexityid':
        try:
            return int(value)
        except ValueError:
            return resolve_markdown_option('complexity', value, locale)['id']
    return value


def main() -> int:
    recipe_glob = os.environ.get('RECIPE_GLOB', 'recipes/**/*.md')
    files = sorted(Path(name) for name in glob.glob(recipe_glob, recursive=True) if Path(name).is_file())
    if not files:
        print(f'No recipe files matched {recipe_glob!r}', file=sys.stderr)
        return 1
    output = Path(os.environ.get('OUTPUT_DIR', 'build/recipes'))
    output.mkdir(parents=True, exist_ok=True)
    failed = False
    for path in files:
        try:
            payload, recipe_id, thumbnail_path, details_image_path = parse_recipe(path)
            if thumbnail_path and thumbnail_path == details_image_path:
                thumbnail_path = _create_thumbnail(thumbnail_path, output / f'{path.stem}.thumbnail.jpg')
            target = output / f'{path.stem}.json'
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            id_path = target.with_suffix('.id')
            source_path = target.with_suffix('.source')
            source_path.write_text(f'{path.resolve()}\n', encoding='utf-8')
            if recipe_id is not None:
                id_path.write_text(f'{recipe_id}\n', encoding='utf-8')
            else:
                id_path.unlink(missing_ok=True)
            for suffix, asset in (('.thumbnail', thumbnail_path), ('.details-image', details_image_path)):
                asset_sidecar = target.with_suffix(suffix)
                if asset is None:
                    asset_sidecar.unlink(missing_ok=True)
                else:
                    asset_sidecar.write_text(f'{asset}\n', encoding='utf-8')
            print(f'Converted {path} -> {target}')
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            failed = True
            print(f'{path}: {exc}', file=sys.stderr)
    output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        with open(output_file, 'a', encoding='utf-8') as handle:
            handle.write(f'output-directory={output.as_posix()}\n')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
