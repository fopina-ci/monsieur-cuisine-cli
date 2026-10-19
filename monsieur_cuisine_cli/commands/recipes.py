import json

import classyclick
import click

from ..recipes import get_my_recipe, get_recipe_from_url, list_my_recipes
from .cli import CLI, ContextProperties


class Recipes(CLI.SubGroup):
    """Look up recipe information."""


class Url(ContextProperties, Recipes.Command):
    """Fetch a recipe from its Monsieur Cuisine page URL."""

    url: str = classyclick.Argument(help='Full Monsieur Cuisine recipe page URL.')

    def __call__(self):
        try:
            recipe = get_recipe_from_url(self.url, self.config_path, session_file=self.session_file)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(recipe, indent=2, ensure_ascii=False))


class List(ContextProperties, Recipes.Command):
    """List your recipes."""

    page: int = classyclick.Option(default=1, help='Page number (starting at 1).')
    size: int = classyclick.Option(default=20, help='Number of recipes per page.')

    def __call__(self):
        try:
            recipes = list_my_recipes(
                self.page, self.size, self.config_path, language=self.language, session_file=self.session_file
            )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(recipes, indent=2, ensure_ascii=False))


class Get(ContextProperties, Recipes.Command):
    """Fetch one of your recipes by ID."""

    recipe_id: int = classyclick.Argument(help='Recipe ID.')

    def __call__(self):
        try:
            recipe = get_my_recipe(
                self.recipe_id, self.config_path, language=self.language, session_file=self.session_file
            )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(recipe, indent=2, ensure_ascii=False))
