"""Helpers for resolving public Monsieur Cuisine recipe pages."""

from __future__ import annotations

import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import auth

_RECIPE_ID = re.compile(r'["\']?recipeId["\']?\s*:\s*["\']?(\d+)', re.IGNORECASE)
_VIEWER_LANG = re.compile(
    r'["\']?viewer-lang["\']?\s*[:=]\s*["\']?([A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)', re.IGNORECASE
)
_MEDIA_READY_TIMEOUT = 60
_MEDIA_POLL_INTERVAL = 2


def _call_api(*args, **kwargs) -> object | None:
    """Call the API and unwrap its top-level data envelope."""
    response = auth.call_api(*args, **kwargs)
    return response.get('data', response) if isinstance(response, dict) else response


def upload_recipe_image(
    path: str | Path,
    image_type: str,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> int:
    """Upload an image and return its media ID once it is ready for recipe use."""
    if image_type not in {'thumbnail', 'details'}:
        raise RuntimeError("Image type must be 'thumbnail' or 'details'.")
    image_path = Path(path).expanduser()
    try:
        content = image_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f'Could not read image file {image_path}: {exc.strerror or exc}.') from exc
    if not content:
        raise RuntimeError(f'Image file is empty: {image_path}')

    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type or not mime_type.startswith('image/'):
        raise RuntimeError(f'Could not determine an image MIME type for {image_path}.')
    suffix = image_path.suffix.lower()
    if not suffix:
        suffix = mimetypes.guess_extension(mime_type) or '.img'
    file_name = f'{uuid.uuid4()}_{image_type}{suffix}'
    upload = _call_api(
        'api/v1/media/image/upload-url',
        method='POST',
        data={'fileName': file_name, 'mimeType': mime_type},
        language=language,
        config_path=config_path,
        session_file=session_file,
    )
    if not isinstance(upload, dict) or not isinstance(upload.get('url'), str) or not upload.get('mediaId'):
        raise RuntimeError('Media upload URL response did not include a URL and media ID.')

    request = urllib.request.Request(upload['url'], data=content, headers={'Content-Type': mime_type}, method='PUT')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f'Image upload failed with HTTP {response.status}.')
    except urllib.error.HTTPError as exc:
        # Do not include the signed URL in errors; it grants temporary upload access.
        raise RuntimeError(f'Image upload failed with HTTP {exc.code}.') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Could not upload image: {exc.reason}') from exc

    media_id = upload['mediaId']
    deadline = time.monotonic() + _MEDIA_READY_TIMEOUT
    while True:
        query = urllib.parse.urlencode({'ids[]': media_id})
        media_result = _call_api(
            f'api/v1/media?{query}',
            language=language,
            config_path=config_path,
            session_file=session_file,
        )
        media_items = media_result.get('media', []) if isinstance(media_result, dict) else []
        item = next(
            (item for item in media_items if isinstance(item, dict) and str(item.get('id')) == str(media_id)),
            None,
        )
        if item and str(item.get('uploadStatus')) == '3':
            return int(media_id)
        if item and str(item.get('uploadStatus')) not in {'', '0', '1', '2', 'None'}:
            raise RuntimeError(f'Media upload processing failed for media ID {media_id}.')
        if time.monotonic() >= deadline:
            raise RuntimeError(f'Media ID {media_id} was not ready after {_MEDIA_READY_TIMEOUT} seconds.')
        time.sleep(_MEDIA_POLL_INTERVAL)


def attach_uploaded_image(payload: dict, field: str, media_id: int) -> None:
    if not isinstance(payload, dict):
        raise RuntimeError('Recipe payload must be a JSON object.')
    image = payload.setdefault(field, {})
    if not isinstance(image, dict):
        raise RuntimeError(f'{field} must be an object when uploading an image.')
    image['landscapeMediaId'] = media_id
    image['landscapeIsAiGenerated'] = False


def _validate_recipe_write_payload(payload: dict) -> None:
    """Reject known read-response shapes that do not match recipe write payloads."""
    if not isinstance(payload, dict):
        raise RuntimeError('Recipe payload must be a JSON object.')

    issues = []
    write_field_for_response = {
        'deviceTypes': 'deviceTypeIds (integer IDs)',
        'categories': 'categoryIds (integer IDs)',
        'complexity': 'complexityId (an integer ID)',
    }
    for response_field, write_field in write_field_for_response.items():
        if response_field in payload:
            issues.append(f'{response_field} is a response field; use {write_field}.')

    for id_field in ('deviceTypeIds', 'categoryIds'):
        values = payload.get(id_field)
        if id_field in payload and not isinstance(values, list):
            issues.append(f'{id_field} must be a list of integer IDs.')
        elif isinstance(values, list) and any(
            not isinstance(value, int) or isinstance(value, bool) for value in values
        ):
            issues.append(f'{id_field} must contain integer IDs, not objects or other values.')

    if 'complexityId' in payload and (
        not isinstance(payload['complexityId'], int) or isinstance(payload['complexityId'], bool)
    ):
        issues.append('complexityId must be an integer ID, not a complexity object.')

    for image_field in ('thumbnail', 'detailsImage'):
        image = payload.get(image_field)
        if isinstance(image, dict):
            for media_field, media_id_field in (
                ('portraitMedia', 'portraitMediaId'),
                ('landscapeMedia', 'landscapeMediaId'),
            ):
                if media_field in image:
                    issues.append(
                        f'{image_field}.{media_field} is an expanded response object; '
                        f'use {image_field}.{media_id_field} and the corresponding IsAiGenerated field.'
                    )
                media_id = image.get(media_id_field)
                if (
                    media_id_field in image
                    and media_id is not None
                    and (not isinstance(media_id, int) or isinstance(media_id, bool))
                ):
                    issues.append(f'{image_field}.{media_id_field} must be an integer ID or null.')

    nutrients = payload.get('nutrients')
    if isinstance(nutrients, list):
        for index, nutrient in enumerate(nutrients):
            if isinstance(nutrient, dict) and 'amountFloat' in nutrient:
                issues.append(f'nutrients[{index}].amountFloat is response-only; provide amount instead.')

    serving_sizes = payload.get('servingSizes')
    if isinstance(serving_sizes, list):
        for index, serving_size in enumerate(serving_sizes):
            if not isinstance(serving_size, dict):
                continue
            for field in ('maxServing', 'modules', 'order'):
                if field in serving_size:
                    issues.append(f'servingSizes[{index}].{field} is response-only; remove it from the payload.')
            steps = serving_size.get('steps')
            if isinstance(steps, list):
                for step_index, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    for field in ('duration', 'videoMedia', 'order'):
                        if field in step:
                            issues.append(
                                f'servingSizes[{index}].steps[{step_index}].{field} is response-only; '
                                'remove it from the payload.'
                            )

    if issues:
        raise RuntimeError('Recipe payload uses response-shaped fields:\n- ' + '\n- '.join(issues))


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


def get_recipe_from_url(url: str, config_path=None, *, session_file: str = 'session.json') -> dict:
    """Resolve a recipe page URL and fetch its API detail response."""
    recipe_id, viewer_language = _recipe_page_metadata(url)
    recipe = _call_api(
        f'api/v2/recipes/{recipe_id}',
        language=viewer_language,
        config_path=config_path,
        session_file=session_file,
    )
    return {'recipeId': recipe_id, 'viewerLang': viewer_language, 'recipe': recipe}


def list_my_recipes(
    page: int = 1,
    size: int = 20,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> object | None:
    """Fetch one page of recipes authored by the signed-in user."""
    if page < 1:
        raise RuntimeError('Page must be 1 or greater.')
    if size < 1:
        raise RuntimeError('Page size must be 1 or greater.')
    query = urllib.parse.urlencode(
        [
            ('size', size),
            ('page', page),
            ('sortBy[0][field]', 'title'),
            ('sortBy[0][direction]', 'ASC'),
            *(
                (
                    ('filters[status][]', status)
                    for status in ('draft', 'pending', 'private-publish', 'publish', 'rejected')
                )
            ),
            ('q', ''),
        ]
    )
    return _call_api(
        f'api/v3/auth/user/recipes?{query}',
        language=language,
        config_path=config_path,
        session_file=session_file,
    )


def list_my_recipes_v1(
    page: int = 1,
    size: int = 20,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> object | None:
    """Fetch a page of authored recipes through the retained legacy v1 endpoint."""
    if page < 1:
        raise RuntimeError('Page must be 1 or greater.')
    if size < 1:
        raise RuntimeError('Page size must be 1 or greater.')
    return _call_api(
        f'api/v1/my-recipes/page/{page}/size/{size}',
        language=language,
        config_path=config_path,
        session_file=session_file,
    )


def get_my_recipe(
    recipe_id: int,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> object | None:
    """Fetch an authored recipe by its ID using the current v3 endpoint."""
    if recipe_id < 1:
        raise RuntimeError('Recipe ID must be a positive integer.')
    return _call_api(
        f'api/v3/auth/user/recipes/{recipe_id}',
        language=language,
        config_path=config_path,
        session_file=session_file,
    )


def create_my_recipe(
    payload: dict,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> object | None:
    """Create an authored recipe using the observed v3 endpoint."""
    _validate_recipe_write_payload(payload)
    return _call_api(
        'api/v3/auth/user/recipes/',
        method='POST',
        data=payload,
        language=language,
        config_path=config_path,
        session_file=session_file,
    )


def update_my_recipe(
    recipe_id: int,
    payload: dict,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> object | None:
    """Update an authored recipe using the observed v3 endpoint."""
    if recipe_id < 1:
        raise RuntimeError('Recipe ID must be a positive integer.')
    _validate_recipe_write_payload(payload)
    return _call_api(
        f'api/v3/auth/user/recipes/{recipe_id}',
        method='PUT',
        data=payload,
        language=language,
        config_path=config_path,
        session_file=session_file,
    )


def get_my_recipe_v1(
    recipe_id: int,
    config_path=None,
    *,
    language: str = 'en-US',
    session_file: str = 'session.json',
) -> object | None:
    """Fetch an authored recipe through the retained legacy v1 endpoint."""
    if recipe_id < 1:
        raise RuntimeError('Recipe ID must be a positive integer.')
    return _call_api(
        f'api/v1/my-recipes/{recipe_id}',
        language=language,
        config_path=config_path,
        session_file=session_file,
    )
