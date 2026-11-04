"""Render and parse readable device-mode summaries in recipe Markdown."""

from __future__ import annotations

import re

_MODE_LABELS = {
    'en': {
        'scale': 'Scale',
        'customized': 'Customized cooking',
        'roasting': 'Roasting',
        'roastingGentle': 'Gentle roasting',
        'roastingIntense': 'Intense roasting',
        'ramp': 'Ramp',
        'steaming': 'Steaming',
        'turbo': 'Turbo',
        'kneading': 'Kneading',
        'kneadingSolidDough': 'Kneading firm dough',
        'kneadingSoftDough': 'Kneading soft dough',
        'kneadingLiquidDough': 'Kneading liquid dough',
        'kneadingProveDough': 'Proving dough',
        'foodProcessor': 'Food processor',
        'smoothie': 'Smoothie',
        'puree': 'Purée',
        'riceCooking': 'Rice cooking',
        'sousVide': 'Sous-vide',
        'slowCooking': 'Slow cooking',
        'cookingEggs': 'Cooking eggs',
        'precleaning': 'Pre-cleaning',
        'fermentation': 'Fermentation',
    },
    'pt': {
        'scale': 'Balança',
        'customized': 'Cozedura personalizada',
        'roasting': 'Dourar',
        'roastingGentle': 'Dourar suavemente',
        'roastingIntense': 'Dourar intensamente',
        'ramp': 'Aumento gradual',
        'steaming': 'Cozedura a vapor',
        'turbo': 'Turbo',
        'kneading': 'Amassar',
        'kneadingSolidDough': 'Amassar massa firme',
        'kneadingSoftDough': 'Amassar massa macia',
        'kneadingLiquidDough': 'Amassar massa líquida',
        'kneadingProveDough': 'Levedar massa',
        'foodProcessor': 'Processador de alimentos',
        'smoothie': 'Smoothie',
        'puree': 'Puré',
        'riceCooking': 'Cozer arroz',
        'sousVide': 'Sous-vide',
        'slowCooking': 'Cozedura lenta',
        'cookingEggs': 'Cozer ovos',
        'precleaning': 'Pré-limpeza',
        'fermentation': 'Fermentação',
    },
}
_FIELD_LABELS = {
    'en': {
        'weight': 'Weight',
        'temperature': 'Temperature',
        'time': 'Duration',
        'speed': 'Speed',
        'speedFloat': 'Precise speed',
        'reverse': 'Direction',
        'turbo': 'Turbo',
        'size': 'Size',
        'texture': 'Texture',
        'cleaningMode': 'Cleaning mode',
    },
    'pt': {
        'weight': 'Peso',
        'temperature': 'Temperatura',
        'time': 'Duração',
        'speed': 'Velocidade',
        'speedFloat': 'Velocidade precisa',
        'reverse': 'Direção',
        'turbo': 'Turbo',
        'size': 'Tamanho',
        'texture': 'Textura',
        'cleaningMode': 'Modo de limpeza',
    },
}
_LANGUAGE_LABELS = {
    'en': {'left': 'Left', 'right': 'Right', 'on': 'On', 'off': 'Off'},
    'pt': {'left': 'Esquerda', 'right': 'Direita', 'on': 'Ativo', 'off': 'Inativo'},
}
_MODE_ALIASES = {
    'kneading_solid_dough': 'kneadingSolidDough',
    'kneading_soft_dough': 'kneadingSoftDough',
    'kneading_liquid_dough': 'kneadingLiquidDough',
    'kneading_prove_dough': 'kneadingProveDough',
    'food_processor': 'foodProcessor',
    'rice_cooking': 'riceCooking',
    'slow_cooking': 'slowCooking',
    'cooking_eggs': 'cookingEggs',
}


def _language(locale: str) -> str:
    return 'pt' if locale.lower().startswith('pt') else 'en'


def _mode_name(mode_type: str, language: str) -> str:
    labels = _MODE_LABELS[language]
    if mode_type in labels:
        return labels[mode_type]
    alias = _MODE_ALIASES.get(mode_type, mode_type)
    if alias in labels:
        return labels[alias]
    # Keep previously unseen API mode names explicitly identifiable and parseable.
    return f'Mode: {mode_type}'


def _number(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _duration(value: object, language: str) -> str:
    seconds = float(value)
    if seconds >= 60 and seconds % 60 == 0:
        unit = 'min' if language == 'en' else 'min.'
        return f'{_number(seconds / 60)} {unit}'
    unit = 's' if language == 'en' else 'seg.'
    return f'{_number(seconds)} {unit}'


def _setting_fields(setting: dict, language: str) -> list[str]:
    labels = _FIELD_LABELS[language]
    fields = []
    if setting.get('weight') is not None:
        fields.append(f'{labels["weight"]}: {_number(setting["weight"])} g')
    if setting.get('temperature') is not None:
        degree = '°C'
        fields.append(f'{labels["temperature"]}: {_number(setting["temperature"])} {degree}')
    if setting.get('time') is not None:
        fields.append(f'{labels["time"]}: {_duration(setting["time"], language)}')
    speed = setting.get('speed')
    precise_speed = setting.get('speedFloat')
    if speed is not None:
        fields.append(f'{labels["speed"]}: {_number(speed)}')
    if precise_speed is not None and precise_speed != speed:
        fields.append(f'{labels["speedFloat"]}: {_number(precise_speed)}')
    return fields


def render_mode(mode: dict, locale: str) -> str:
    """Render normalized mode data as a readable localized Markdown line."""
    language = _language(locale)
    mode_type = str(mode.get('type') or '')
    name = _mode_name(mode_type, language) if mode_type else 'Mode'
    fields = []
    settings = mode.get('deviceSettings')
    if isinstance(settings, list):
        for index, setting in enumerate(settings, 1):
            if not isinstance(setting, dict):
                continue
            values = _setting_fields(setting, language)
            if len(settings) > 1 and values:
                fields.append(
                    f'Stage {index}: ' + '; '.join(values)
                    if language == 'en'
                    else f'Etapa {index}: ' + '; '.join(values)
                )
            else:
                fields.extend(values)

    labels = _FIELD_LABELS[language]
    if mode.get('reverse') is not None and (mode_type in {'customized', 'customizedCooking'}):
        direction = _LANGUAGE_LABELS[language]['left' if mode['reverse'] else 'right']
        fields.append(f'{labels["reverse"]}: {direction}')
    for field in ('size', 'texture', 'cleaningMode'):
        if mode.get(field) not in (None, '', False):
            fields.append(f'{labels[field]}: {mode[field]}')
    if mode.get('turbo'):
        fields.append(f'{labels["turbo"]}: {_LANGUAGE_LABELS[language]["on"]}')

    # Keep the API enum visible for exact round-tripping, while leading with
    # the same localized mode label shown by the cooker UI.
    marker = 'Modo' if language == 'pt' else 'Mode'
    return f'**{marker}:** **{name}** (`{mode_type}`)' + (f' · {" · ".join(fields)}' if fields else '')


def _parse_value(field: str, value: str, language: str) -> object:
    value = value.strip()
    if field in {'weight', 'temperature', 'speed', 'speedFloat'}:
        match = re.fullmatch(r'([\d.,]+)\s*(?:g|°c)?', value, re.IGNORECASE)
        if not match:
            raise ValueError(f'unsupported {field} value {value!r}')
        number = float(match.group(1).replace(',', '.'))
        return int(number) if number.is_integer() else number
    if field == 'time':
        match = re.fullmatch(r'([\d.,]+)\s*(?:s|sec\.?|seg\.?|seconds?)', value, re.IGNORECASE)
        if match:
            number = float(match.group(1).replace(',', '.'))
        else:
            match = re.fullmatch(r'([\d.,]+)\s*(?:min\.?|minutes?)', value, re.IGNORECASE)
            if not match:
                raise ValueError(f'unsupported duration value {value!r}')
            number = float(match.group(1).replace(',', '.')) * 60
        return int(number) if number.is_integer() else number
    if field == 'reverse':
        if value.casefold() in {'left', 'esquerda'}:
            return True
        if value.casefold() in {'right', 'direita'}:
            return False
        raise ValueError(f'unsupported direction value {value!r}')
    if field == 'turbo':
        if value.casefold() in {'on', 'ativo'}:
            return True
        if value.casefold() in {'off', 'inativo'}:
            return False
        raise ValueError(f'unsupported turbo value {value!r}')
    return value


def parse_mode(line: str, locale: str) -> dict:
    """Parse a rendered localized mode line to the recipe mode structure."""
    language = _language(locale)
    marker = re.match(r'^\*\*(?:Mode|Modo):\*\*\s+', line.strip(), re.IGNORECASE)
    if not marker:
        raise ValueError('device mode must start with **Mode:** or **Modo:**')
    mode_line = line.strip()[marker.end() :]
    match = re.fullmatch(r'\*\*(.+?)\*\*\s+\(`([^`]+)`\)(?:\s*·\s*(.*))?', mode_line)
    if not match:
        raise ValueError('device mode must use the semantic Markdown format')

    name, mode_type, field_text = match.groups()
    mode_type = mode_type or next((key for key, label in _MODE_LABELS[language].items() if label == name), None)
    if mode_type is None and name.startswith('Mode: '):
        mode_type = name[6:]
    if mode_type is None:
        alias = next(
            (key for key, label in _MODE_LABELS[language].items() if label.casefold() == name.casefold()), None
        )
        mode_type = alias
    if mode_type is None:
        raise ValueError(f'unknown device mode label {name!r} for locale {locale}')

    mode = {'type': mode_type}
    field_names = {label.casefold(): key for key, label in _FIELD_LABELS[language].items()}
    stages = []
    current_setting = None
    stage_prefix = 'Stage ' if language == 'en' else 'Etapa '
    for part in (field_text or '').split(' · '):
        if part.startswith(stage_prefix):
            stage_label, part = part.split(': ', 1)
            stage_order = int(stage_label[len(stage_prefix) :]) - 1
            current_setting = {'order': stage_order}
            stages.append(current_setting)
        elif current_setting is None:
            current_setting = {'order': 0}
        for field_part in part.split('; '):
            if not field_part:
                continue
            label, separator, value = field_part.partition(': ')
            if not separator:
                raise ValueError(f'invalid device mode field {field_part!r}')
            field = field_names.get(label.casefold())
            if field in {'reverse', 'size', 'texture', 'cleaningMode', 'turbo'}:
                mode[field] = _parse_value(field, value, language)
            elif field in {'weight', 'temperature', 'time', 'speed', 'speedFloat'}:
                current_setting[field] = _parse_value(field, value, language)
            else:
                raise ValueError(f'unknown device mode field {label!r} for locale {locale}')

    device_settings = [stage for stage in stages or ([current_setting] if current_setting else []) if len(stage) > 1]
    if device_settings:
        mode['deviceSettings'] = device_settings
    return mode
