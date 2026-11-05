#!/usr/bin/env python3
"""Convert Markdown cookbook recipes into CLI-compatible recipe JSON."""

import glob
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from action.mode_markdown import parse_mode
from monsieur_cuisine_cli.api.recipe_validation import (
    canonical_locale,
    resolve_markdown_option,
    validate_nutrient_amounts,
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
    'originalrecipeid',
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

_AMOUNT_NUMBER = r'(?:\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?|[¼½¾⅐⅓⅔⅛⅜⅝⅞])'
_AMOUNT_PATTERN = re.compile(
    rf'^(?:ca\.?\s*)?{_AMOUNT_NUMBER}(?:\s+\d+\s*/\s*\d+)?(?:\s*[-–]\s*{_AMOUNT_NUMBER})?$',
    re.IGNORECASE,
)


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
        if field.casefold() in {'field', 'property'} or not field:
            continue
        raw_metadata_rows.append((field, value))

    locale_labels = {'languagelocale', 'locale', 'language', 'language/locale'}
    localized_locale_labels = {labels['languageLocale'].casefold() for labels in RECIPE_FIELD_LABELS.values()}
    locale_indexes = [
        index
        for index, (field, _) in enumerate(raw_metadata_rows)
        if field.casefold() in locale_labels | localized_locale_labels
    ]
    if not locale_indexes:
        raise ValueError('languageLocale is required in the Recipe table')
    if len(locale_indexes) > 1:
        raise ValueError('include languageLocale only once in the Recipe table')
    locale_index = locale_indexes[0]
    locale = canonical_locale(raw_metadata_rows[locale_index][1])
    metadata['languagelocale'] = locale
    localized_labels = RECIPE_FIELD_LABELS.get(locale, {})
    field_aliases = {label.casefold(): field.casefold() for field, label in localized_labels.items()}
    metadata_rows = []
    for index, (field, value) in enumerate(raw_metadata_rows):
        if index == locale_index:
            continue
        normalized = field.casefold()
        if normalized in locale_labels or normalized in localized_locale_labels:
            raise ValueError('include languageLocale only once in the Recipe table')
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
        if annotation:
            # Continue accepting the previous hidden representation so
            # existing cookbook files remain valid; new output is plain text.
            details = json.loads(annotation.group(1))
            item = item[: annotation.start()].strip()
            if not isinstance(details, dict):
                raise ValueError('mc-ingredient annotation must be a JSON object')
            amount = str(details.get('amount') or '')
            unit_value = str(details.get('unit') or '')
            unit = resolve_markdown_option('ingredient_unit', unit_value, locale)['unit_name'] if unit_value else ''
            is_optional = details.get('isOptional', False)
            if not isinstance(is_optional, bool):
                raise ValueError('mc-ingredient isOptional must be a boolean')
        else:
            item, amount, unit, is_optional = _parse_ingredient_text(item, locale)
        ingredients.append({'name': item, 'amount': amount, 'unit': unit, 'isOptional': is_optional})
    steps = []
    step_lines = section_lines('steps')
    index = 0
    while index < len(step_lines):
        line = step_lines[index]
        index += 1
        item = re.sub(r'^\d+[.)]\s+', '', line)
        annotation = re.search(r'<!--\s*mc-mode:\s*(\{.*\})\s*-->', item)
        mode = json.loads(annotation.group(1)) if annotation else None
        if annotation:
            item = item[: annotation.start()].strip()
        if index < len(step_lines) and re.match(r'^\*\*(?:Mode|Modo):\*\*', step_lines[index].strip(), re.IGNORECASE):
            try:
                mode = parse_mode(step_lines[index].strip(), locale)
            except ValueError as exc:
                raise ValueError(f'invalid device mode on step {len(steps) + 1}: {exc}') from exc
            index += 1
        elif index < len(step_lines) and step_lines[index].strip().casefold() in {'```json', '```'}:
            index += 1
            mode_lines = []
            while index < len(step_lines) and step_lines[index].strip() != '```':
                mode_lines.append(step_lines[index].strip())
                index += 1
            if index >= len(step_lines):
                raise ValueError('device settings code block is missing its closing fence')
            index += 1
            try:
                mode = json.loads('\n'.join(mode_lines))
            except json.JSONDecodeError as exc:
                raise ValueError(f'device settings code block must contain valid JSON: {exc}') from exc
        title_match = re.match(r'^\*\*(.+?)\*\*:\s*(.*)$', item)
        step_title = title_match.group(1) if title_match else title
        step_description = title_match.group(2) if title_match else item
        if mode is not None and not isinstance(mode, dict):
            raise ValueError('mc-mode annotation must be a JSON object')
        steps.append({'title': step_title, 'description': step_description, 'mode': mode})
    required = (
        'languagelocale',
        'devicetypeids',
        'servings',
        'complexityid',
        'readyintime',
        'ingredientgroupname',
    )
    missing = [field for field in required if field not in metadata]
    if missing:
        raise ValueError(f'missing Recipe table fields: {", ".join(missing)}')
    if not title:
        raise ValueError('add a recipe title as the first-level Markdown heading (for example, # Tomato soup)')
    if not ingredients:
        raise ValueError('add at least one item under ## Ingredients')
    if not steps:
        raise ValueError('add at least one numbered item under ## Steps')
    if metadata.get('preparationtime') is not None and metadata['preparationtime'] < 1:
        raise ValueError('preparationTime must be at least 1 when provided')
    if metadata['readyintime'] < 1:
        raise ValueError('readyInTime must be at least 1')
    if not metadata['ingredientgroupname'].strip():
        raise ValueError('ingredientGroupName must be a non-empty value')
    if details_image_path is None:
        raise ValueError(
            'a details image is required for private publishing; add an image immediately after the recipe description '
            'or set detailsImage to an image path in the Recipe table'
        )
    servings, serving_unit = metadata['servings']
    device_ids = metadata['devicetypeids']
    if not isinstance(device_ids, list) or not device_ids or any(type(value) is not int for value in device_ids):
        raise ValueError('deviceTypeIds must be a non-empty list of integer IDs')
    recipe_id = metadata.get('recipeid')
    if recipe_id is not None and (not isinstance(recipe_id, int) or isinstance(recipe_id, bool) or recipe_id < 1):
        raise ValueError('recipeId must be a positive integer')
    original_recipe_id = metadata.get('originalrecipeid')
    if original_recipe_id is not None and (
        not isinstance(original_recipe_id, int) or isinstance(original_recipe_id, bool) or original_recipe_id < 1
    ):
        raise ValueError('originalRecipeId must be a positive integer')

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
                'preparationTime': metadata.get('preparationtime'),
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
        validate_nutrient_amounts(payload)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    return payload, recipe_id, thumbnail_path, details_image_path


def _parse_ingredient_text(item: str, locale: str) -> tuple[str, str, str, bool]:
    """Parse ``name — amount unit (optional)`` ingredient lines."""
    is_optional = bool(re.search(r'\s+\(optional\)$', item, re.IGNORECASE))
    if is_optional:
        item = re.sub(r'\s+\(optional\)$', '', item, flags=re.IGNORECASE).rstrip()

    name, separator, details = item.rpartition(' — ')
    if not separator:
        if not item:
            raise ValueError('ingredient name must not be empty')
        return item, '', '', is_optional
    name = name.strip()
    details = details.strip()
    if not name or not details:
        raise ValueError('ingredients with an amount or unit must use "name — amount unit"')

    words = details.split()
    for start in range(len(words)):
        unit_text = ' '.join(words[start:])
        try:
            unit = resolve_markdown_option('ingredient_unit', unit_text, locale)['unit_name']
        except RuntimeError:
            continue
        amount = ' '.join(words[:start])
        if amount and not _AMOUNT_PATTERN.fullmatch(amount):
            continue
        return name, amount, unit, is_optional

    if _AMOUNT_PATTERN.fullmatch(details):
        return name, details, '', is_optional
    raise ValueError(
        f'ingredient details {details!r} must contain an amount and/or an ingredient unit available for {locale}'
    )


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
    if field in {'recipeid', 'originalrecipeid', 'preparationtime', 'readyintime'}:
        if field == 'recipeid':
            link = re.fullmatch(r'\[[^\]]+\]\((https?://[^)]+)\)', value)
            if link:
                identifiers = parse_qs(urlparse(link.group(1)).query).get('recipe-id', [])
                if len(identifiers) != 1:
                    raise ValueError('recipeId link must include one recipe-id query parameter')
                value = identifiers[0]
        elif field == 'originalrecipeid':
            link = re.fullmatch(r'\[([1-9][0-9]*)\]\(https?://[^)]+\)', value)
            if link:
                value = link.group(1)
        elif field == 'preparationtime' and value.casefold() == 'null':
            return None
        return int(value)
    if field == 'complexityid':
        try:
            return int(value)
        except ValueError:
            return resolve_markdown_option('complexity', value, locale)['id']
    return value


def _files_to_convert(recipe_glob: str, recipe_files_json: str | None = None) -> list[Path]:
    if recipe_files_json:
        try:
            selected_files = json.loads(recipe_files_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f'recipe_files must be a JSON array of Markdown paths: {exc}') from exc
        if not isinstance(selected_files, list) or any(not isinstance(name, str) for name in selected_files):
            raise ValueError('recipe_files must be a JSON array of Markdown paths.')
        paths = [Path(name) for name in selected_files]
        if any(path.is_absolute() or '..' in path.parts or path.suffix.lower() != '.md' for path in paths):
            raise ValueError('recipe_files must contain repo-relative Markdown paths.')
        missing = [path.as_posix() for path in paths if not path.is_file()]
        if missing:
            raise ValueError(f'recipe_files do not exist: {", ".join(missing)}')
        return sorted(set(paths))
    return sorted(Path(name) for name in glob.glob(recipe_glob, recursive=True) if Path(name).is_file())


def _write_action_outputs(output: Path, success: bool, report: str, converted_files: list[Path] | None = None) -> None:
    output_file = os.environ.get('GITHUB_OUTPUT')
    if not output_file:
        return
    delimiter = f'validation_report_{uuid.uuid4().hex}'
    with open(output_file, 'a', encoding='utf-8') as handle:
        handle.write(f'output-directory={output.as_posix()}\n')
        handle.write(f'validation-success={str(success).lower()}\n')
        handle.write(f'converted-json-files={json.dumps([path.as_posix() for path in (converted_files or [])])}\n')
        handle.write(f'validation-report<<{delimiter}\n{report}\n{delimiter}\n')


def main() -> int:
    recipe_glob = os.environ.get('RECIPE_GLOB', 'recipes/**/*.md')
    output = Path(os.environ.get('OUTPUT_DIR', 'build/recipes'))
    try:
        files = _files_to_convert(recipe_glob, os.environ.get('RECIPE_FILES_JSON'))
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(exc, file=sys.stderr)
        _write_action_outputs(output, False, str(exc))
        return 1
    if not files:
        message = f'No recipe files matched {recipe_glob!r}'
        print(message, file=sys.stderr)
        _write_action_outputs(output, False, message)
        return 1
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        message = f'Cannot create conversion output directory {output}: {exc}'
        print(message, file=sys.stderr)
        _write_action_outputs(output, False, message)
        return 1
    failed = False
    failures = []
    converted_files = []
    for path in files:
        try:
            payload, recipe_id, thumbnail_path, details_image_path = parse_recipe(path)
            if thumbnail_path and thumbnail_path == details_image_path:
                thumbnail_path = _create_thumbnail(thumbnail_path, output / f'{path.stem}.thumbnail.jpg')
            target = output / f'{path.stem}.json'
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            converted_files.append(target)
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
            message = f'{path}: {exc}'
            failures.append(message)
            print(message, file=sys.stderr)
    report = '\n'.join(failures) if failures else f'Converted {len(files)} recipe(s) successfully.'
    _write_action_outputs(output, not failed, report, converted_files)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
