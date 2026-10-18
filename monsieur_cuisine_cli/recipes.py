"""Helpers for resolving public Monsieur Cuisine recipe pages."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

from .auth import call_api

_RECIPE_ID = re.compile(r'["\']?recipeId["\']?\s*:\s*["\']?(\d+)', re.IGNORECASE)
_VIEWER_LANG = re.compile(
    r'["\']?viewer-lang["\']?\s*[:=]\s*["\']?([A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)', re.IGNORECASE
)


def _recipe_page_metadata(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.monsieur-cuisine.com', 'monsieur-cuisine.com'}:
        raise RuntimeError('Recipe URL must be an HTTPS page on monsieur-cuisine.com.')
    segments = parsed.path.strip('/').split('/')
    if len(segments) < 3 or segments[1] != 'recipe':
        raise RuntimeError('URL must point to a Monsieur Cuisine recipe page.')

    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'text/html,application/xhtml+xml',
            'User-Agent': 'Mozilla/5.0 (compatible; monsieur-cuisine-cli)',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            page = response.read().decode(charset, errors='replace')
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Could not load recipe page (HTTP {exc.code}): {url}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Could not reach recipe page {url}: {exc.reason}') from exc

    recipe_match = _RECIPE_ID.search(page)
    if not recipe_match:
        raise RuntimeError('Recipe page did not contain a recipeId in its script data.')

    language_match = _VIEWER_LANG.search(page)
    viewer_language = language_match.group(1) if language_match else segments[0]
    # The site path uses lowercase locale tags (pt-pt); the API expects `pt-PT`.
    parts = viewer_language.split('-')
    viewer_language = '-'.join([parts[0].lower(), *(part.upper() if len(part) == 2 else part for part in parts[1:])])
    return recipe_match.group(1), viewer_language


def get_recipe_from_url(url: str, config_path=None) -> dict:
    """Resolve a recipe page URL and fetch its API detail response."""
    recipe_id, viewer_language = _recipe_page_metadata(url)
    recipe = call_api(
        f'api/v2/recipes/{recipe_id}',
        language=viewer_language,
        config_path=config_path,
    )
    return {'recipeId': recipe_id, 'viewerLang': viewer_language, 'recipe': recipe}


def list_my_recipes(page: int = 1, size: int = 20, config_path=None, *, language: str = 'en-US') -> object | None:
    """Fetch one page of recipes authored by the signed-in user."""
    if page < 1:
        raise RuntimeError('Page must be 1 or greater.')
    if size < 1:
        raise RuntimeError('Page size must be 1 or greater.')
    return call_api(
        f'api/v1/my-recipes/page/{page}/size/{size}',
        language=language,
        config_path=config_path,
    )


def get_my_recipe(recipe_id: int, config_path=None, *, language: str = 'en-US') -> object | None:
    """Fetch an authored recipe by its ID."""
    if recipe_id < 1:
        raise RuntimeError('Recipe ID must be a positive integer.')
    return call_api(f'api/v1/my-recipes/{recipe_id}', language=language, config_path=config_path)
