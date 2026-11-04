"""Temporary session-file helpers that persist API token rotations to GitHub."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def require_api_tokens(session_token: str, secret_writer: str, operation: str) -> None:
    if not session_token:
        raise RuntimeError(f'The session_token input is required for the {operation} operation.')
    if not secret_writer:
        raise RuntimeError(
            f'The secrets_write_token input is required for the {operation} operation '
            'to persist a refreshed MC_API_ACCESS_TOKEN.'
        )


def _read_access_token(session_file: Path) -> str:
    try:
        value = json.loads(session_file.read_text(encoding='utf-8')).get('accessToken')
    except (AttributeError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Could not read the temporary API session token: {exc}') from exc
    if not isinstance(value, str) or not value:
        raise RuntimeError('The temporary API session file has no accessToken.')
    return value


def _set_repository_secret(token: str, secret_writer: str) -> None:
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    if not repository:
        raise RuntimeError('GITHUB_REPOSITORY is required to persist a refreshed API token.')
    result = subprocess.run(
        ['gh', 'secret', 'set', 'MC_API_ACCESS_TOKEN', '--repo', repository],
        input=token,
        capture_output=True,
        check=False,
        text=True,
        env={**os.environ, 'GH_TOKEN': secret_writer},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Could not update the MC_API_ACCESS_TOKEN repository secret.')


@contextmanager
def temporary_session(token: str, secret_writer: str, operation: str) -> Iterator[Path]:
    """Initialize a private CLI session and persist any rotated token on exit."""
    require_api_tokens(token, secret_writer, operation)
    with tempfile.TemporaryDirectory(prefix=f'mc-{operation}-') as temp_dir:
        session_file = Path(temp_dir) / 'session.json'
        result = subprocess.run(
            ['monsieur-cuisine-cli', '--session-file', str(session_file), 'auth', 'set-token'],
            input=token,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode:
            detail = result.stderr.strip()
            raise RuntimeError(detail or 'Could not initialize the temporary API session with auth set-token.')
        try:
            yield session_file
        finally:
            current_token = _read_access_token(session_file)
            if current_token != token:
                _set_repository_secret(current_token, secret_writer)
