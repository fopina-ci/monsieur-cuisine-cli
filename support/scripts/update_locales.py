#!/usr/bin/env python3
"""Refresh the hardcoded locale to website-language mapping from the homepage."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCALES_FILE = ROOT / 'monsieur_cuisine_cli' / 'locales.py'
HOME_URL = 'https://www.monsieur-cuisine.com/'


def _normalize_locale(value: str) -> str:
    parts = value.replace('_', '-').split('-')
    return '-'.join(part.lower() if index == 0 else part.upper() for index, part in enumerate(parts))


def main() -> None:
    request = urllib.request.Request(
        HOME_URL,
        headers={'Accept': 'text/html,application/xhtml+xml', 'User-Agent': 'Mozilla/5.0'},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            page = response.read().decode(charset, errors='replace')
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise SystemExit(f'Could not fetch Monsieur Cuisine homepage: {exc}') from exc

    site_languages = re.search(r'"siteLanguages"\s*:\s*\{', page)
    if not site_languages:
        raise SystemExit('No siteLanguages data found; locale list was not changed.')
    data_start = page.find('{', site_languages.start())
    try:
        language_data, _ = json.JSONDecoder().raw_decode(page[data_start:])
    except json.JSONDecodeError as exc:
        raise SystemExit('Could not parse siteLanguages data; locale list was not changed.') from exc

    locale_site_codes = {
        _normalize_locale(language['default_locale']): language['code']
        for language in language_data.values()
        if isinstance(language, dict)
        and isinstance(language.get('default_locale'), str)
        and isinstance(language.get('code'), str)
    }
    if not locale_site_codes:
        raise SystemExit('No locale codes found; locale list was not changed.')

    mapping_lines = ''.join(f"    {locale!r}: {code!r},\n" for locale, code in sorted(locale_site_codes.items()))
    replacement = 'LOCALE_SITE_CODES = {\n' + mapping_lines + '}\n\nSUPPORTED_LOCALES = tuple(LOCALE_SITE_CODES)'
    source = LOCALES_FILE.read_text(encoding='utf-8')
    updated, count = re.subn(
        r'LOCALE_SITE_CODES = \{.*?\}\n\nSUPPORTED_LOCALES = tuple\(LOCALE_SITE_CODES\)',
        replacement,
        source,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit(f'Could not find SUPPORTED_LOCALES in {LOCALES_FILE}.')
    LOCALES_FILE.write_text(updated, encoding='utf-8')
    print(f'Updated {LOCALES_FILE.relative_to(ROOT)} with {len(locale_site_codes)} locales.')


if __name__ == '__main__':
    main()
