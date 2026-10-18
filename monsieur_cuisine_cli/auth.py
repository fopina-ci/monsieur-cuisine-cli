"""Monsieur Cuisine mobile-app OAuth login."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import string
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_public_key

ISSUER = 'https://accounts.lidl.com'
CLIENT_ID = 'monsieurcuisineappcompanionclient'
# AppAuth's ClientSecretBasic value, bundled in the mobile app at hf/i.smali.
CLIENT_SECRET = '12F42561-7F71-43D7-964A-4B2B1E2B19C3'
REDIRECT_URI = 'lidl-com.monsieur-cuisine.companion://login/prod'
API_BASE = 'https://mc-api.tecpal.com'
KEY_ID = '351756051523999'
PREPROD_KEY = '3afe90d2-7b78-434c-a174-8274c370dc11'
APP_VERSION_CODE = '10040213'


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    language: str = 'en-US',
) -> dict:
    request_headers = {
        'Accept-Language': language,
        'AppMinorVersion': APP_VERSION_CODE,
        'Device-Type': 'android',
        'X-Request-ID': str(uuid.uuid4()),
        'x-preprod-key': PREPROD_KEY,
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {exc.code} from {url}: {detail}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Could not reach {url}: {exc.reason}') from exc
    if not isinstance(result, dict):
        raise RuntimeError(f'Unexpected response from {url}')
    return result


def _post_form(
    url: str,
    values: dict[str, str],
    headers: dict[str, str] | None = None,
    *,
    language: str = 'en-US',
) -> dict:
    body = urllib.parse.urlencode(values).encode('ascii')
    request_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if headers:
        request_headers.update(headers)
    return _request(url, data=body, headers=request_headers, language=language)


def _api_data(response: dict) -> dict:
    """Unwrap the API's common response envelope."""
    data = response.get('data', response)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if not isinstance(data, dict):
        raise RuntimeError(f'Unexpected API response: {response}')
    return data


def _decrypt_api_response(response: dict, aes_key: bytes) -> dict:
    """Decode the app API's encrypted response wrapper, if present."""
    if 'payload' not in response or 'iv' not in response:
        return response
    if response.get('code', 0) != 0:
        raise RuntimeError(f'Encrypted API response reported code {response["code"]}: {response}')
    decryptor = Cipher(
        algorithms.AES(aes_key),
        modes.CBC(base64.b64decode(response['iv'])),
    ).decryptor()
    padded = decryptor.update(base64.b64decode(response['payload'])) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    result = json.loads(plaintext)
    if not isinstance(result, dict):
        raise RuntimeError('Decrypted API response was not a JSON object.')
    return result


def _api_token_login(oauth: dict, config_path: Path | None = None, language: str = 'en-US') -> dict:
    key_response = _request(f'{API_BASE}/api/v1/authkey/server/request-public-key', language=language)
    key_data = _api_data(key_response)
    encoded_key = key_data.get('serverPublicKey')
    if not encoded_key:
        raise RuntimeError(f'API response did not contain serverPublicKey: {key_response}')

    aes_key = secrets.token_bytes(32)
    iv = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16)).encode('ascii')
    payload = json.dumps(
        {
            'accessToken': oauth['access_token'],
            'idToken': oauth['id_token'],
            'clientId': CLIENT_ID,
            # The app persists a random, dashless UUID as its device ID and uses it as companionAppId.
            'companionAppId': _companion_id(config_path),
        },
        separators=(',', ':'),
    ).encode('utf-8')

    encryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).encryptor()
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    ciphertext = encryptor.update(padder.update(payload) + padder.finalize()) + encryptor.finalize()
    public_key = load_der_public_key(base64.b64decode(encoded_key))
    wrapped_key = public_key.encrypt(aes_key, asymmetric_padding.PKCS1v15())
    body = json.dumps(
        {
            'code': 0,
            'payload': base64.b64encode(ciphertext).decode('ascii'),
            'iv': base64.b64encode(iv).decode('ascii'),
        },
        separators=(',', ':'),
    ).encode('utf-8')
    response = _request(
        f'{API_BASE}/api/v2/users/login',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'x-app-aes': base64.b64encode(wrapped_key).decode('ascii'),
            'x-key-id': KEY_ID,
            'x-encrypt-method': 'AES',
        },
        language=language,
    )
    return _api_data(_decrypt_api_response(response, aes_key))


def _session_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return Path(config_path).expanduser().resolve().parent / 'session.json'
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return config_home / 'monsieur-cuisine' / 'session.json'


def _load_api_session(config_path: Path | None = None) -> dict:
    path = _session_path(config_path)
    try:
        session = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise RuntimeError('No saved session. Run `monsieur-cuisine auth login` first.') from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Saved session at {path} could not be read as valid JSON.') from exc

    if not isinstance(session, dict):
        raise RuntimeError(f'Saved session at {path} is not a JSON object.')
    return session


def _api_access_token(config_path: Path | None = None) -> str:
    path = _session_path(config_path)
    session = _load_api_session(config_path)
    access_token = session.get('accessToken')
    if not access_token:
        raise RuntimeError(f'Saved session at {path} does not contain an API accessToken. Run login again.')
    return access_token


def _api_url(endpoint: str) -> str:
    """Build an API URL from a path, rejecting absolute and host-relative URLs."""
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path:
        raise RuntimeError('API endpoint must be a path on the Monsieur Cuisine API, not a full URL.')
    if any(part == '..' for part in parsed.path.split('/')):
        raise RuntimeError('API endpoint cannot contain parent-directory path segments.')
    return f'{API_BASE}/{parsed.path.lstrip("/")}' + (f'?{parsed.query}' if parsed.query else '')


def call_api(
    endpoint: str,
    *,
    method: str = 'GET',
    data: object | None = None,
    language: str | None = None,
    config_path: Path | None = None,
) -> object | None:
    """Call a custom API path using the saved mobile-app API session."""
    session = _load_api_session(config_path)
    token = session.get('accessToken')
    if not token:
        path = _session_path(config_path)
        raise RuntimeError(f'Saved session at {path} does not contain an API accessToken. Run login again.')
    url = _api_url(endpoint)
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None
    headers = {
        'Accept-Language': language or 'en-US',
        'AppMinorVersion': APP_VERSION_CODE,
        'Device-Type': 'android',
        'X-Request-ID': str(uuid.uuid4()),
        'x-preprod-key': PREPROD_KEY,
        'Authorization': f'Bearer {token}',
    }
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {exc.code} from {url}: {detail}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Could not reach {url}: {exc.reason}') from exc

    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode('utf-8', errors='replace')


def _companion_id(config_path: Path | None = None) -> str:
    path = _session_path(config_path).with_name('companion-id')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        value = path.read_text(encoding='ascii').strip()
        if value:
            return value
    except FileNotFoundError:
        pass
    value = uuid.uuid4().hex
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='ascii') as output:
        output.write(value)
    return value


def _save_session(session: dict, config_path: Path | None = None) -> Path:
    path = _session_path(config_path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temp = path.with_suffix('.json.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        json.dump(session, output, indent=2)
        output.write('\n')
    os.replace(temp, path)
    os.chmod(path, 0o600)
    return path


def get_profile(config_path: Path | None = None, language: str = 'en-US') -> dict:
    """Fetch the authenticated user's profile using the stored API session."""
    response = _request(
        f'{API_BASE}/api/v1/users/',
        headers={'Authorization': f'Bearer {_api_access_token(config_path)}'},
        language=language,
    )
    return _api_data(response)


def renew(config_path: Path | None = None, language: str = 'en-US') -> Path:
    """Use the saved OAuth refresh token and persist the renewed OAuth tokens."""
    path = _session_path(config_path)
    try:
        session = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise RuntimeError('No saved session. Run `monsieur-cuisine auth login` first.') from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Saved session at {path} could not be read as valid JSON.') from exc

    refresh_token = session.get('oauthRefreshToken')
    if not refresh_token:
        raise RuntimeError('The saved session has no OAuth refresh token. Run `monsieur-cuisine auth login` again.')

    discovery = _request(f'{ISSUER}/.well-known/openid-configuration', language=language)
    token_endpoint = discovery.get('token_endpoint')
    if not token_endpoint:
        raise RuntimeError('OIDC discovery response is missing token_endpoint.')

    basic_auth = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode('utf-8')).decode('ascii')
    oauth = _post_form(
        token_endpoint,
        {
            'grant_type': 'refresh_token',
            'client_id': CLIENT_ID,
            'refresh_token': refresh_token,
        },
        headers={'Authorization': f'Basic {basic_auth}'},
        language=language,
    )
    if not oauth.get('access_token'):
        raise RuntimeError(f'OAuth refresh response did not include an access_token: {oauth}')

    session['oauthAccessToken'] = oauth['access_token']
    if oauth.get('id_token'):
        session['oauthIdToken'] = oauth['id_token']
    if oauth.get('refresh_token'):
        session['oauthRefreshToken'] = oauth['refresh_token']
    if oauth.get('expires_in') is not None:
        session['oauthAccessTokenExpiresAt'] = int(time.time()) + int(oauth['expires_in'])

    return _save_session(session, config_path)


def _callback_params(redirect: str) -> dict[str, list[str]]:
    parsed = urllib.parse.urlparse(redirect)
    expected = urllib.parse.urlparse(REDIRECT_URI)
    actual_base = parsed._replace(query='', fragment='').geturl().rstrip('/')
    expected_base = expected._replace(query='', fragment='').geturl().rstrip('/')
    if actual_base != expected_base:
        raise RuntimeError(f'The returned URL does not match the app callback {REDIRECT_URI!r}.')
    return urllib.parse.parse_qs(parsed.query)


def _capture_browser_callback(auth_url: str) -> str:
    """Open Chromium through Playwright and capture its custom-scheme redirect."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            'Playwright is required for managed-browser login. Install the project dependencies first.'
        ) from exc

    callback: dict[str, str] = {}

    def maybe_capture(url: str | None) -> None:
        if url and url.startswith(REDIRECT_URI) and not callback:
            callback['url'] = url

    try:
        with sync_playwright() as playwright:
            chromium = playwright.chromium
            if not Path(chromium.executable_path).is_file():
                print('Playwright Chromium is missing; installing it now…')
                try:
                    subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=True)
                except (OSError, subprocess.CalledProcessError) as exc:
                    raise RuntimeError(f'Could not install Playwright Chromium automatically: {exc}') from exc
            browser = chromium.launch(headless=False)
            page = browser.new_page()

            def on_response(response):
                # The OAuth server's Location header exposes custom-scheme redirects
                # before the browser tries (and fails) to hand them to the OS.
                maybe_capture(response.headers.get('location'))

            page.on('response', on_response)
            page.on('request', lambda request: maybe_capture(request.url))
            page.on('framenavigated', lambda frame: maybe_capture(frame.url) if frame == page.main_frame else None)
            print('Opening the Lidl sign-in page in a Playwright browser…')
            try:
                page.goto(auth_url, wait_until='domcontentloaded', timeout=60_000)
            except PlaywrightError:
                # The OAuth callback uses an app-only URI scheme. Chromium may
                # report navigation failure after the response has been captured.
                pass
            deadline = time.monotonic() + 300
            while not callback and time.monotonic() < deadline:
                try:
                    page.wait_for_timeout(200)
                except PlaywrightError:
                    break
            browser.close()
    except PlaywrightError as exc:
        raise RuntimeError(f'Could not launch Playwright Chromium: {exc}.') from exc
    if not callback:
        raise RuntimeError('Timed out waiting for the OAuth callback in the Playwright browser.')
    return callback['url']


def _capture_system_browser_callback(auth_url: str) -> str:
    """Open the system browser and ask the user to paste its final callback URL."""
    import webbrowser

    print('Opening Lidl sign-in in your system browser…')
    if not webbrowser.open(auth_url):
        print(f'Open this URL in your browser:\n{auth_url}')
    print(f'After sign-in, copy the final URL beginning with {REDIRECT_URI} and paste it below.')
    try:
        return input('Callback URL: ').strip()
    except EOFError as exc:
        raise RuntimeError('Could not read the callback URL from standard input.') from exc


def login(
    system_browser: bool = False,
    language: str = 'en-US',
    config_path: Path | None = None,
) -> Path:
    """Authenticate using the mobile app's OIDC and API token-login flow."""
    discovery = _request(f'{ISSUER}/.well-known/openid-configuration', language=language)
    try:
        authorization_endpoint = discovery['authorization_endpoint']
        token_endpoint = discovery['token_endpoint']
    except KeyError as exc:
        raise RuntimeError(f'OIDC discovery response is missing {exc.args[0]}') from exc

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode('ascii')).digest())
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid profile offline_access',
        'state': state,
        'nonce': nonce,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'login',
        'CountryCode': language.rsplit('-', 1)[-1].upper() if '-' in language else language.upper(),
        'Language': language,
    }
    auth_url = f'{authorization_endpoint}?{urllib.parse.urlencode(params)}'
    if system_browser:
        redirect = _capture_system_browser_callback(auth_url)
    else:
        redirect = _capture_browser_callback(auth_url)
    query = _callback_params(redirect)
    returned_state = query.get('state', [''])[0]
    if not secrets.compare_digest(returned_state, state):
        raise RuntimeError('OAuth state did not match. Start login again.')
    if query.get('error'):
        description = query.get('error_description', query['error'])[0]
        raise RuntimeError(f'OAuth sign-in failed: {description}')
    code = query.get('code', [''])[0]
    if not code:
        raise RuntimeError('The pasted URL did not contain an authorization code.')

    basic_auth = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode('utf-8')).decode('ascii')
    oauth = _post_form(
        token_endpoint,
        {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'code': code,
            'code_verifier': verifier,
        },
        headers={'Authorization': f'Basic {basic_auth}'},
        language=language,
    )
    if not oauth.get('access_token') or not oauth.get('id_token'):
        raise RuntimeError(f'OAuth response did not include the tokens needed by the app API: {oauth}')
    api_session = _api_token_login(oauth, config_path, language=language)
    if not api_session.get('accessToken'):
        raise RuntimeError(f'API login response did not contain an accessToken: {api_session}')
    if oauth.get('refresh_token'):
        api_session['oauthRefreshToken'] = oauth['refresh_token']
    if oauth.get('expires_in') is not None:
        api_session['oauthAccessTokenExpiresAt'] = int(time.time()) + int(oauth['expires_in'])
    path = _save_session(api_session, config_path)
    print(f'Logged in. API session saved to {path}')
    return path
