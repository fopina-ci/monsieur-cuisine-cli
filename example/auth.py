"""Monsieur Cuisine mobile-app OAuth login."""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import string
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
DEFAULT_REDIRECT_URI = REDIRECT_URI
API_BASE = 'https://mc-api.tecpal.com'
KEY_ID = '351756051523999'
PREPROD_KEY = '3afe90d2-7b78-434c-a174-8274c370dc11'
APP_VERSION_CODE = '10040213'


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _request(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    request_headers = {
        'Accept-Language': 'en',
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


def _post_form(url: str, values: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    body = urllib.parse.urlencode(values).encode('ascii')
    request_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if headers:
        request_headers.update(headers)
    return _request(url, data=body, headers=request_headers)


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


def _api_token_login(oauth: dict) -> dict:
    key_response = _request(f'{API_BASE}/api/v1/authkey/server/request-public-key')
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
            'companionAppId': _companion_id(),
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
    )
    return _api_data(_decrypt_api_response(response, aes_key))


def _session_path() -> Path:
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return config_home / 'monsieur-cuisine' / 'session.json'


def _companion_id() -> str:
    path = _session_path().with_name('companion-id')
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


def _save_session(session: dict) -> Path:
    path = _session_path()
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


def get_profile() -> dict:
    """Fetch the authenticated user's profile using the stored API session."""
    path = _session_path()
    try:
        session = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise RuntimeError('No saved session. Run `example-cli login` first.') from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Saved session at {path} is not valid JSON.') from exc
    access_token = session.get('accessToken')
    if not access_token:
        raise RuntimeError(f'Saved session at {path} does not contain an API accessToken. Run login again.')
    response = _request(
        f'{API_BASE}/api/v1/users/',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    return _api_data(response)


def _callback_params(redirect: str, redirect_uri: str) -> dict[str, list[str]]:
    parsed = urllib.parse.urlparse(redirect)
    expected = urllib.parse.urlparse(redirect_uri)
    actual_base = parsed._replace(query='', fragment='').geturl().rstrip('/')
    expected_base = expected._replace(query='', fragment='').geturl().rstrip('/')
    if actual_base != expected_base:
        raise RuntimeError(f'The returned URL does not match the requested redirect URI {redirect_uri!r}.')
    return urllib.parse.parse_qs(parsed.query)


def _wait_for_local_callback(redirect_uri: str) -> str:
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1'}:
        raise RuntimeError('Automatic callback is supported only for http://localhost or http://127.0.0.1 redirect URIs.')
    port = parsed.port or 80
    expected_path = parsed.path or '/'
    callback: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split('?', 1)[0] != expected_path:
                self.send_error(404)
                return
            callback['url'] = f'{redirect_uri}{"&" if "?" in redirect_uri else "?"}{self.path.partition("?")[2]}'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'Login received. You can return to the CLI.\n')

        def log_message(self, _format, *_args):
            pass

    try:
        server = http.server.HTTPServer(('127.0.0.1', port), Handler)
    except OSError as exc:
        raise RuntimeError(f'Could not listen on 127.0.0.1:{port}: {exc}') from exc
    server.timeout = 180
    try:
        server.handle_request()
    finally:
        server.server_close()
    if not callback:
        raise RuntimeError('Timed out waiting for the browser callback.')
    return callback['url']


def _capture_browser_callback(auth_url: str, redirect_uri: str, browser_name: str | None) -> str:
    """Open the OAuth page in Playwright and capture its custom-scheme redirect."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('Playwright is required for browser login. Install it with `pip install playwright` and run `playwright install chromium`.') from exc

    callback: dict[str, str] = {}
    browser_type_name = (browser_name or 'chromium').lower()
    if browser_type_name not in {'chromium', 'firefox', 'webkit'}:
        raise RuntimeError('Playwright browser must be chromium, firefox, or webkit.')

    def maybe_capture(url: str | None) -> None:
        if url and url.startswith(redirect_uri) and not callback:
            callback['url'] = url

    try:
        with sync_playwright() as playwright:
            browser_type = getattr(playwright, browser_type_name)
            browser = browser_type.launch(headless=False)
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
        raise RuntimeError(f'Could not launch Playwright browser {browser_type_name!r}: {exc}. Install its browser with `playwright install {browser_type_name}`.') from exc
    if not callback:
        raise RuntimeError('Timed out waiting for the OAuth callback in the Playwright browser.')
    return callback['url']


def login(
    language: str = 'pt-PT',
    browser_name: str | None = None,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> Path:
    """Authenticate using the mobile app's OIDC and API token-login flow."""
    discovery = _request(f'{ISSUER}/.well-known/openid-configuration')
    try:
        authorization_endpoint = discovery['authorization_endpoint']
        token_endpoint = discovery['token_endpoint']
    except KeyError as exc:
        raise RuntimeError(f'OIDC discovery response is missing {exc.args[0]}') from exc

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode('ascii')).digest())
    country = language.rsplit('-', 1)[-1].upper()
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid profile offline_access',
        'state': state,
        'nonce': nonce,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'login',
        'CountryCode': country,
        'Language': language,
    }
    auth_url = f'{authorization_endpoint}?{urllib.parse.urlencode(params)}'
    local_http = urllib.parse.urlparse(redirect_uri)
    if local_http.scheme == 'http' and local_http.hostname in {'localhost', '127.0.0.1'}:
        print('Opening the Lidl sign-in page in your browser…')
        import webbrowser

        try:
            browser = webbrowser.get(browser_name) if browser_name else webbrowser
        except webbrowser.Error as exc:
            raise RuntimeError(f'Could not find browser {browser_name!r}. Try a browser name such as chrome, safari, or firefox.') from exc
        if not browser.open(auth_url):
            print(f'Open this URL in a browser:\n{auth_url}')
        print(f'\nWaiting for the browser to return to {redirect_uri} …')
        redirect = _wait_for_local_callback(redirect_uri)
    else:
        redirect = _capture_browser_callback(auth_url, redirect_uri, browser_name)
    query = _callback_params(redirect, redirect_uri)
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
            'redirect_uri': redirect_uri,
            'code': code,
            'code_verifier': verifier,
        },
        headers={'Authorization': f'Basic {basic_auth}'},
    )
    if not oauth.get('access_token') or not oauth.get('id_token'):
        raise RuntimeError(f'OAuth response did not include the tokens needed by the app API: {oauth}')
    api_session = _api_token_login(oauth)
    if not api_session.get('accessToken'):
        raise RuntimeError(f'API login response did not contain an accessToken: {api_session}')
    if oauth.get('refresh_token'):
        api_session['oauthRefreshToken'] = oauth['refresh_token']
    if oauth.get('expires_in') is not None:
        api_session['oauthAccessTokenExpiresAt'] = int(time.time()) + int(oauth['expires_in'])
    path = _save_session(api_session)
    print(f'Logged in. API session saved to {path}')
    return path
