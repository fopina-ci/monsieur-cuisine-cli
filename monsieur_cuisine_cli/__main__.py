import json
from datetime import datetime
from pathlib import Path

import classyclick
import click

from . import __version__
from .auth import _session_path, call_api, get_profile, login, renew
from .recipes import get_my_recipe, get_recipe_from_url, list_my_recipes


def _selected_config_path() -> Path | None:
    context = click.get_current_context(silent=True)
    return context.find_root().meta.get('config_path') if context else None


def _selected_language() -> str:
    context = click.get_current_context(silent=True)
    root = context.find_root() if context else None
    return root.params.get('lang', 'en-US') if root else 'en-US'


class CLI(classyclick.helpers.ConfigFileMixin, classyclick.Group):
    """Manage recipes in a monsieur-cuisine.com account."""

    __config__ = classyclick.Group.Config(
        name='monsieur-cuisine',
        decorators=click.version_option(version=__version__),
    )
    CONFIG_DEFAULT_NAME = 'monsieur-cuisine'
    CONFIG_EXAMPLE_PATH = Path(__file__).with_name('default-config.toml')
    lang: str = classyclick.Option(default='en-US', show_default=True, help='Locale for API requests and Lidl sign-in.')

    def __call__(self):
        self.load_config()


class Auth(CLI.SubGroup):
    """Manage the account session."""


class Login(Auth.Command):
    """Sign in through Lidl's account login."""

    browser: bool = classyclick.Option(
        default=False, help='Use the system browser and paste the final mobile callback URL.'
    )
    def __call__(self):
        try:
            login(
                system_browser=self.browser,
                language=_selected_language(),
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
            path = renew(_selected_config_path(), language=_selected_language())
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
            profile = get_profile(_selected_config_path(), language=_selected_language())
            click.echo(json.dumps(profile, indent=2, ensure_ascii=False))
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc


class Recipes(CLI.SubGroup):
    """Look up recipe information."""


class Url(Recipes.Command):
    """Fetch a recipe from its Monsieur Cuisine page URL."""

    url: str = classyclick.Argument(help='Full Monsieur Cuisine recipe page URL.')

    def __call__(self):
        try:
            recipe = get_recipe_from_url(self.url, _selected_config_path())
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(recipe, indent=2, ensure_ascii=False))


class List(Recipes.Command):
    """List your recipes."""

    page: int = classyclick.Option(default=1, help='Page number (starting at 1).')
    size: int = classyclick.Option(default=20, help='Number of recipes per page.')

    def __call__(self):
        try:
            recipes = list_my_recipes(
                self.page,
                self.size,
                _selected_config_path(),
                language=_selected_language(),
            )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(recipes, indent=2, ensure_ascii=False))


class Get(Recipes.Command):
    """Fetch one of your recipes by ID."""

    recipe_id: int = classyclick.Argument(help='Recipe ID.')

    def __call__(self):
        try:
            recipe = get_my_recipe(
                self.recipe_id,
                _selected_config_path(),
                language=_selected_language(),
            )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(recipe, indent=2, ensure_ascii=False))


class Api(CLI.Command):
    """Call a custom Monsieur Cuisine API path with the saved session."""

    endpoint: str = classyclick.Argument(help='API path, for example api/v2/recipes/238467.')
    method: str = classyclick.Option(
        default='GET',
        type=click.Choice(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], case_sensitive=False),
        help='HTTP method to use.',
    )
    data: str = classyclick.Option(default=None, help='JSON request body for POST, PUT, PATCH, or DELETE.')

    def __call__(self):
        try:
            payload = json.loads(self.data) if self.data is not None else None
            result = call_api(
                self.endpoint,
                method=self.method,
                data=payload,
                language=_selected_language(),
                config_path=_selected_config_path(),
            )
        except json.JSONDecodeError as exc:
            raise click.ClickException(f'--data must contain valid JSON: {exc}') from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        if result is None:
            click.echo('Request completed with an empty response body.')
        elif isinstance(result, str):
            click.echo(result)
        else:
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))


class Config(classyclick.helpers.ConfigBaseCommand, CLI.Command):
    """Show or edit the current TOML configuration."""


def main() -> None:
    CLI.click()


if __name__ == '__main__':
    main()
