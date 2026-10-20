import json

import classyclick
import click

from ..api import recipes
from .cli import CLI, ContextProperties, OutputProperties
from .output import emit


class Recipes(CLI.SubGroup):
    """Look up recipe information."""


class Url(ContextProperties, OutputProperties, Recipes.Command):
    """Fetch a recipe from its Monsieur Cuisine page URL."""

    url: str = classyclick.Argument(help='Full Monsieur Cuisine recipe page URL.')

    def __call__(self):
        try:
            recipe = recipes.get_recipe_from_url(self.url, self.config_path, session_file=self.session_file)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(recipe, self.json)


class Create(ContextProperties, OutputProperties, Recipes.Command):
    """Create a recipe from a JSON payload using the v3 API."""

    data: str = classyclick.Option(required=True, help='Recipe payload as a JSON object.')
    thumbnail: str = classyclick.Option(default=None, help='Upload a landscape thumbnail image file.')
    details_image: str = classyclick.Option(default=None, help='Upload a landscape details image file.')

    def __call__(self):
        try:
            payload = json.loads(self.data)
            if self.thumbnail:
                media_id = recipes.upload_recipe_image(
                    self.thumbnail,
                    'thumbnail',
                    self.config_path,
                    language=self.language,
                    session_file=self.session_file,
                )
                recipes.attach_uploaded_image(payload, 'thumbnail', media_id)
            if self.details_image:
                media_id = recipes.upload_recipe_image(
                    self.details_image,
                    'details',
                    self.config_path,
                    language=self.language,
                    session_file=self.session_file,
                )
                recipes.attach_uploaded_image(payload, 'detailsImage', media_id)
            recipe = recipes.create_my_recipe(
                payload, self.config_path, language=self.language, session_file=self.session_file
            )
        except json.JSONDecodeError as exc:
            raise click.ClickException(f'--data must contain valid JSON: {exc}') from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(recipe, self.json)


class Update(ContextProperties, OutputProperties, Recipes.Command):
    """Update a recipe from a JSON payload using the v3 API."""

    recipe_id: int = classyclick.Argument(help='Recipe ID.')
    data: str = classyclick.Option(required=True, help='Recipe payload as a JSON object.')
    thumbnail: str = classyclick.Option(default=None, help='Upload a landscape thumbnail image file.')
    details_image: str = classyclick.Option(default=None, help='Upload a landscape details image file.')

    def __call__(self):
        try:
            payload = json.loads(self.data)
            if self.thumbnail:
                media_id = recipes.upload_recipe_image(
                    self.thumbnail,
                    'thumbnail',
                    self.config_path,
                    language=self.language,
                    session_file=self.session_file,
                )
                recipes.attach_uploaded_image(payload, 'thumbnail', media_id)
            if self.details_image:
                media_id = recipes.upload_recipe_image(
                    self.details_image,
                    'details',
                    self.config_path,
                    language=self.language,
                    session_file=self.session_file,
                )
                recipes.attach_uploaded_image(payload, 'detailsImage', media_id)
            recipe = recipes.update_my_recipe(
                self.recipe_id,
                payload,
                self.config_path,
                language=self.language,
                session_file=self.session_file,
            )
        except json.JSONDecodeError as exc:
            raise click.ClickException(f'--data must contain valid JSON: {exc}') from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(recipe, self.json)


class List(ContextProperties, OutputProperties, Recipes.Command):
    """List your recipes using the v3 API, or the deprecated v1 route on request."""

    page: int = classyclick.Option(default=1, help='Page number (starting at 1).')
    size: int = classyclick.Option(default=20, help='Number of recipes per page.')
    use_v1: bool = classyclick.Option(default=False, help='Use the deprecated v1 list endpoint.')

    def __call__(self):
        try:
            if self.use_v1:
                click.echo('Warning: --use-v1 selects the deprecated API v1 list route.', err=True)
                result = recipes.list_my_recipes_v1(
                    self.page, self.size, self.config_path, language=self.language, session_file=self.session_file
                )
            else:
                result = recipes.list_my_recipes(
                    self.page, self.size, self.config_path, language=self.language, session_file=self.session_file
                )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(result, self.json)


class Get(ContextProperties, OutputProperties, Recipes.Command):
    """Fetch one of your recipes by ID using the v3 API, or the deprecated v1 route on request."""

    recipe_id: int = classyclick.Argument(help='Recipe ID.')
    use_v1: bool = classyclick.Option(default=False, help='Use the deprecated v1 detail endpoint.')

    def __call__(self):
        try:
            if self.use_v1:
                click.echo('Warning: --use-v1 selects the deprecated API v1 detail route.', err=True)
                recipe = recipes.get_my_recipe_v1(
                    self.recipe_id, self.config_path, language=self.language, session_file=self.session_file
                )
            else:
                recipe = recipes.get_my_recipe(
                    self.recipe_id, self.config_path, language=self.language, session_file=self.session_file
                )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(recipe, self.json)
