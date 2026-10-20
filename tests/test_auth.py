import base64
import json
import os
import urllib.parse

import pytest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from monsieur_cuisine_cli.api import auth


def test_api_data_unwraps_envelopes():
    assert auth._api_data({'data': {'id': 'user-1'}}) == {'id': 'user-1'}
    assert auth._api_data({'data': [{'id': 'user-1'}]}) == {'id': 'user-1'}
    assert auth._api_data({'id': 'user-1'}) == {'id': 'user-1'}


def test_api_data_rejects_unexpected_data():
    with pytest.raises(RuntimeError, match='Unexpected API response'):
        auth._api_data({'data': 'unexpected'})


def test_decrypt_api_response_decodes_encrypted_payload():
    key = bytes(range(32))
    iv = bytes(range(16))
    value = {'data': {'accessToken': 'api-token'}}
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(json.dumps(value).encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    response = {
        'code': 0,
        'iv': base64.b64encode(iv).decode(),
        'payload': base64.b64encode(ciphertext).decode(),
    }

    assert auth._decrypt_api_response(response, key) == value


def test_decrypt_api_response_rejects_api_error():
    with pytest.raises(RuntimeError, match='reported code 17'):
        auth._decrypt_api_response({'code': 17, 'iv': '', 'payload': ''}, bytes(32))


def test_config_path_places_session_beside_config(tmp_path):
    config = tmp_path / 'settings.toml'
    assert auth._session_path(config) == config.resolve().parent / 'session.json'


def test_companion_id_is_created_once_and_session_is_private(tmp_path):
    config = tmp_path / 'settings.toml'
    companion_id = auth._companion_id(config)

    assert len(companion_id) == 32
    assert auth._companion_id(config) == companion_id

    os.chmod(tmp_path, 0o755)
    session_path = auth._save_session({'accessToken': 'secret'}, config)
    assert json.loads(session_path.read_text()) == {'accessToken': 'secret'}
    assert os.stat(session_path).st_mode & 0o777 == 0o600
    assert os.stat(tmp_path).st_mode & 0o777 == 0o755


def test_callback_params_accepts_expected_deep_link():
    query = urllib.parse.urlencode({'code': 'auth-code', 'state': 'csrf-state'})
    assert auth._callback_params(f'{auth.REDIRECT_URI}?{query}') == {
        'code': ['auth-code'],
        'state': ['csrf-state'],
    }


def test_callback_params_rejects_unexpected_url():
    with pytest.raises(RuntimeError, match='does not match the app callback'):
        auth._callback_params('https://attacker.example/callback?code=stolen')


def test_login_completes_mocked_oauth_flow(tmp_path, monkeypatch):
    config = tmp_path / 'settings.toml'
    requests = []

    def fake_request(url, *, language):
        requests.append((url, language))
        return {
            'authorization_endpoint': 'https://accounts.test/authorize',
            'token_endpoint': 'https://accounts.test/token',
        }

    captured = {}

    def fake_capture(auth_url):
        captured['url'] = auth_url
        params = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)
        return f'{auth.REDIRECT_URI}?' + urllib.parse.urlencode({'code': 'auth-code', 'state': params['state'][0]})

    def fake_post_form(url, values, headers=None, *, language):
        assert url == 'https://accounts.test/token'
        assert language == 'de-DE'
        assert values['grant_type'] == 'authorization_code'
        assert values['code'] == 'auth-code'
        assert values['redirect_uri'] == auth.REDIRECT_URI
        assert headers['Authorization'].startswith('Basic ')
        id_token = f"header.{auth._b64url(json.dumps({'nonce': 'fixed-state'}).encode())}.signature"
        return {'access_token': 'oauth-access', 'id_token': id_token, 'refresh_token': 'refresh', 'expires_in': 60}

    def fake_api_login(oauth, config_path, *, language, session_file):
        assert oauth['access_token'] == 'oauth-access'
        assert oauth['id_token'] == 'oauth-id'
        assert config_path == config
        assert language == 'de-DE'
        assert session_file == 'session.json'
        return {'accessToken': 'api-access'}

    monkeypatch.setattr(auth, '_request', fake_request)
    monkeypatch.setattr(auth, '_capture_system_browser_callback', fake_capture)
    monkeypatch.setattr(auth, '_post_form', fake_post_form)
    monkeypatch.setattr(auth, '_api_token_login', fake_api_login)
    monkeypatch.setattr(auth.secrets, 'token_urlsafe', lambda _: 'fixed-state')
    monkeypatch.setattr(auth.secrets, 'token_bytes', lambda _: b'v' * 32)
    monkeypatch.setattr(auth.time, 'time', lambda: 1_000)

    session_path = auth.login(system_browser=True, language='de-DE', config_path=config)

    params = urllib.parse.parse_qs(urllib.parse.urlparse(captured['url']).query)
    assert params['state'] == ['fixed-state']
    assert params['nonce'] == ['fixed-state']
    assert params['Language'] == ['de-DE']
    assert params['CountryCode'] == ['DE']
    assert params['code_challenge_method'] == ['S256']
    assert len(params['code_challenge'][0]) == 43
    assert requests == [('https://accounts.lidl.com/.well-known/openid-configuration', 'de-DE')]
    assert json.loads(session_path.read_text()) == {
        'accessToken': 'api-access',
    }
