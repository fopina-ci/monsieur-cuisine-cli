from dataclasses import dataclass
from pathlib import Path

import classyclick
import click

from .. import __version__


@dataclass(init=False)
class ContextProperties:
    """Common values passed from the root Click context to commands."""

    config_path: Path = classyclick.ContextMeta('config_path')
    language: str = classyclick.ContextMeta('language')
    session_file: str = classyclick.ContextMeta('session_file')


class CLI(classyclick.helpers.ConfigFileMixin, classyclick.Group):
    """Manage recipes in a monsieur-cuisine.com account."""

    __config__ = classyclick.Group.Config(
        name='monsieur-cuisine',
        decorators=click.version_option(version=__version__),
        context_settings={'terminal_width': 10_000, 'max_content_width': 10_000},
    )
    CONFIG_DEFAULT_NAME = 'monsieur-cuisine'
    CONFIG_EXAMPLE_PATH = Path(__file__).parents[1] / 'default-config.toml'
    lang: str = classyclick.Option(default='en-US', show_default=True, help='Locale for API requests and Lidl sign-in.')
    session_file: str = classyclick.Option(
        default='session.json',
        show_default='session.json; relative paths resolve beside --config; absolute paths are used as given',
        help='Session file name or path.',
    )

    def __call__(self):
        self.load_config()
        self.ctx.meta['language'] = self.lang
        self.ctx.meta['session_file'] = self.session_file


class Config(classyclick.helpers.ConfigBaseCommand, CLI.Command):
    """Show or edit the current TOML configuration."""


classyclick.helpers.discover_commands(__package__)
