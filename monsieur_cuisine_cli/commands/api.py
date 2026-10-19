import json

import classyclick
import click

from ..auth import call_api
from .cli import CLI, ContextProperties


class Api(ContextProperties, CLI.Command):
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
                language=self.language,
                config_path=self.config_path,
                session_file=self.session_file,
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
