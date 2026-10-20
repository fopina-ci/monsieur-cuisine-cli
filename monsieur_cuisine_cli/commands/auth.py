import base64
import json
from datetime import datetime

import classyclick
import click

from ..api import auth
from .cli import CLI, ContextProperties


class Auth(CLI.SubGroup):
    """Manage the account session."""


class Login(ContextProperties, Auth.Command):
    """Sign in through Lidl's account login."""

    browser: bool = classyclick.Option(
        default=False, help='Use the system browser and paste the final mobile callback URL.'
    )

    def __call__(self):
        try:
            auth.login(
                system_browser=self.browser,
                language=self.language,
                config_path=self.config_path,
                session_file=self.session_file,
            )
        except KeyboardInterrupt as exc:
            raise click.Abort() from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


class Status(ContextProperties, Auth.Command):
    """Check whether an account session is saved locally."""

    def __call__(self):
        path = auth._session_path(self.config_path, self.session_file)
        if not path.is_file():
            click.echo('No session is saved.')
            return
        click.echo('A session is saved.')
        try:
            session = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            click.echo('Token expiry: unavailable (could not read the session file).')
            return
        user = session.get('user')
        name = user.get('displayName') if isinstance(user, dict) else None
        if not name and isinstance(user, dict):
            name = ' '.join(part for part in (user.get('firstName'), user.get('lastName')) if part)
        click.echo(f'Account: {name or "name unavailable"}')
        try:
            encoded_payload = session.get('accessToken').split('.')[1]
            encoded_payload += '=' * (-len(encoded_payload) % 4)
            expires_at = json.loads(base64.urlsafe_b64decode(encoded_payload)).get('exp')
        except (AttributeError, IndexError, TypeError, ValueError):
            expires_at = None
        if expires_at is None:
            click.echo('API token expiry: unavailable.')
            return
        try:
            expiry = datetime.fromtimestamp(int(expires_at)).astimezone()
        except (TypeError, ValueError, OverflowError, OSError):
            click.echo('API token expiry: unavailable (invalid expiry value).')
            return
        click.echo(f'API token expires at {expiry.isoformat(timespec="seconds")}')


class Renew(ContextProperties, Auth.Command):
    """Refresh the saved Monsieur Cuisine API access token."""

    def __call__(self):
        try:
            path = auth.renew(self.config_path, language=self.language, session_file=self.session_file)
            click.echo(f'API access token renewed. Session saved to {path}')
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


class Logout(ContextProperties, Auth.Command):
    """Remove the saved account session."""

    def __call__(self):
        path = auth._session_path(self.config_path, self.session_file)
        if path.exists():
            path.unlink()
            click.echo('Saved session removed.')
        else:
            click.echo('No saved session to remove.')


class Profile(ContextProperties, CLI.Command):
    """Fetch the authenticated account profile."""

    def __call__(self):
        try:
            profile = auth.get_profile(self.config_path, language=self.language, session_file=self.session_file)
            click.echo(json.dumps(profile, indent=2, ensure_ascii=False))
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
