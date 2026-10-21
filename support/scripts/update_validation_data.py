#!/usr/bin/env python3
"""Fetch localized recipe dropdown values and refresh checked-in constants.

Opens the Monsieur Cuisine website in a visible browser so the user can log
in. The authenticated browser session is used only in memory and is not saved.
"""

from __future__ import annotations

import argparse
import json
import pprint
import runpy
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCALE_SITE_CODES = runpy.run_path(str(ROOT / 'monsieur_cuisine_cli' / 'locales.py'))['LOCALE_SITE_CODES']

ENDPOINT = 'https://www.monsieur-cuisine.com/wp-admin/admin-ajax.php'
OUTPUT_FILE = ROOT / 'monsieur_cuisine_cli' / 'recipe_validation_data.py'
GUIDE_FIELDS = (
    'serving_units',
    'ingredient_units',
    'category_options',
    'device_options',
    'level_options',
    'module_options',
)
_WPML_COOKIE = 'wp-wpml_current_language'
SITE_URL = 'https://www.monsieur-cuisine.com/'


def _authenticated_cookie() -> str:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit('Playwright is required; install the project dependencies first.') from exc

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=False)
        except PlaywrightError as exc:
            raise SystemExit(f'Could not launch Playwright Chromium: {exc}') from exc
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(SITE_URL, wait_until='domcontentloaded')
            input('Log in to Monsieur Cuisine in the browser, then press Enter here to check the session... ')
            result = page.evaluate(
                """async () => {
                    const form = new FormData();
                    form.set('action', 'load_recipe_post');
                    const response = await fetch('/wp-admin/admin-ajax.php', {
                        method: 'POST',
                        headers: {'X-Requested-With': 'XMLHttpRequest'},
                        body: form,
                    });
                    return {ok: response.ok, data: await response.json()};
                }"""
            )
            guide = result.get('data', {}).get('guide') if result.get('ok') else None
            if not isinstance(guide, dict) or not isinstance(guide.get('device_options'), list):
                raise SystemExit('The session is not authenticated for recipe data. Log in and run the script again.')
            cookies = context.cookies(SITE_URL)
            cookie = '; '.join(f"{item['name']}={item['value']}" for item in cookies)
            if not cookie:
                raise SystemExit('The browser session did not provide any site cookies.')
            print('Authenticated session confirmed; closing browser before fetching locale data.')
            return cookie
        finally:
            browser.close()


def _cookie_for_site_language(cookie: str, site_code: str) -> str:
    parts = [part.strip() for part in cookie.split(';') if part.strip()]
    replaced = False
    for index, part in enumerate(parts):
        if part.partition('=')[0] == _WPML_COOKIE:
            parts[index] = f'{_WPML_COOKIE}={site_code}'
            replaced = True
            break
    if not replaced:
        parts.append(f'{_WPML_COOKIE}={site_code}')
    return '; '.join(parts)


def _request_guide(locale: str, site_code: str, cookie: str) -> dict:
    boundary = '----mc-cli-locale-validation'
    body = f'--{boundary}\r\nContent-Disposition: form-data; name="action"\r\n\r\nload_recipe_post\r\n--{boundary}--\r\n'
    referer = f'https://www.monsieur-cuisine.com/{site_code}/'
    request = urllib.request.Request(
        ENDPOINT,
        data=body.encode('ascii'),
        headers={
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': locale,
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Cookie': _cookie_for_site_language(cookie, site_code),
            'Origin': 'https://www.monsieur-cuisine.com',
            'Referer': referer,
            'User-Agent': 'Mozilla/5.0 (compatible; monsieur-cuisine-cli locale data updater)',
            'X-Requested-With': 'XMLHttpRequest',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode(response.headers.get_content_charset() or 'utf-8'))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'{locale}: endpoint returned HTTP {exc.code}.') from exc
    except (urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'{locale}: could not retrieve or decode dropdown data.') from exc

    guide = result.get('guide') if isinstance(result, dict) else None
    if not isinstance(guide, dict):
        raise RuntimeError(f'{locale}: response did not include guide data; check whether the HAR session is valid.')
    normalized = {}
    for field in GUIDE_FIELDS:
        options = guide.get(field)
        if not isinstance(options, list):
            raise RuntimeError(f'{locale}: response is missing guide list {field}.')
        if field != 'module_options' and not options:
            raise RuntimeError(f'{locale}: {field} is empty; check whether the HAR session is valid.')
        # Translation expansions repeat the same cross-locale table on every
        # request. The localized option itself carries the labels and IDs we
        # need for validation and Markdown value resolution.
        normalized[field] = [
            {key: value for key, value in option.items() if key != 'translations'}
            if isinstance(option, dict)
            else option
            for option in options
        ]
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    cookie = _authenticated_cookie()

    all_data = {}
    for index, (locale, site_code) in enumerate(LOCALE_SITE_CODES.items()):
        try:
            all_data[locale] = _request_guide(locale, site_code, cookie)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print(f'Fetched localized dropdown values for {locale}.')
        if index + 1 < len(LOCALE_SITE_CODES):
            time.sleep(0.25)

    generated = (
        '"""Generated by support/scripts/update_validation_data.py; do not edit manually."""\n\n'
        'LOCALE_VALIDATION_DATA = ' + pprint.pformat(all_data, sort_dicts=True, width=120) + '\n'
    )
    OUTPUT_FILE.write_text(generated, encoding='utf-8')
    print(f'Updated {OUTPUT_FILE.relative_to(ROOT)} for {len(all_data)} locales.')


if __name__ == '__main__':
    main()
