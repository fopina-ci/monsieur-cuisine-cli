import json
from datetime import datetime
from pathlib import Path

import classyclick
import click

from . import __version__
from .auth import _session_path, get_profile, login, renew


def _selected_config_path() -> Path | None:
    context = click.get_current_context(silent=True)
    return context.find_root().meta.get('config_path') if context else None


class CLI(classyclick.helpers.ConfigFileMixin, classyclick.Group):
    """Manage recipes in a monsieur-cuisine.com account."""

    __config__ = classyclick.Group.Config(
        name='monsieur-cuisine',
        decorators=click.version_option(version=__version__),
    )
    CONFIG_DEFAULT_NAME = 'monsieur-cuisine'
    CONFIG_EXAMPLE_PATH = Path(__file__).with_name('default-config.toml')

    def __call__(self):
        self.load_config()


class Auth(CLI.SubGroup):
    """Manage the account session."""


class Login(Auth.Command):
    """Sign in through Lidl's account login."""

    browser: bool = classyclick.Option(
        default=False, help='Use the system browser and paste the final mobile callback URL.'
    )
    language: str = classyclick.Option(default='en-GB', help='Locale for Lidl sign-in, such as en-GB.')

    def __call__(self):
        try:
            login(
                system_browser=self.browser,
                language=self.language,
                config_path=_selected_config_path(),
            )
        except KeyboardInterrupt as exc:
            raise click.Abort() from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


class Status(Auth.Command):
    """Check whether an account session is saved locally."""

    def __call__(self):
        path = _session_path(_selected_config_path())
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

        expires_at = session.get('oauthAccessTokenExpiresAt')
        if expires_at is None:
            click.echo('Token expiry: unavailable.')
            return
        try:
            expiry = datetime.fromtimestamp(int(expires_at)).astimezone()
        except (TypeError, ValueError, OverflowError, OSError):
            click.echo('Token expiry: unavailable (invalid expiry value).')
            return
        click.echo(f'Token expires at {expiry.isoformat(timespec="seconds")}')


class Renew(Auth.Command):
    """Renew the saved OAuth access token using its refresh token."""

    def __call__(self):
        try:
            path = renew(_selected_config_path())
            click.echo(f'OAuth token renewed. Session saved to {path}')
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


class Logout(Auth.Command):
    """Remove the saved account session."""

    def __call__(self):
        path = _session_path(_selected_config_path())
        if path.exists():
            path.unlink()
            click.echo('Saved session removed.')
        else:
            click.echo('No saved session to remove.')


class Profile(CLI.Command):
    """Fetch the authenticated account profile."""

    def __call__(self):
        try:
            click.echo(json.dumps(get_profile(_selected_config_path()), indent=2, ensure_ascii=False))
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


class Config(classyclick.helpers.ConfigBaseCommand, CLI.Command):
    """Show or edit the current TOML configuration."""


def main() -> None:
    CLI.click()


if __name__ == '__main__':
    main()
