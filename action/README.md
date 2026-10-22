# Monsieur Cuisine cookbook action

This composite GitHub Action validates Markdown recipes, publishes them through the CLI, fetches existing recipes, and opens follow-up pull requests with assigned recipe IDs.

## Recipe format

Store recipes as `.md` files under `recipes/`. Use the first-level Markdown heading (`#`) as the recipe title. The text immediately after it is the description, and an image immediately after that text is used as the details photo. The action creates an 800×600 thumbnail from a top-left 4:3 crop of that image; when the source is smaller, it keeps the largest available 4:3 crop without enlarging it. Put the other recipe metadata in a visible Markdown table under `## Recipe`, then add `## Ingredients` and `## Steps` sections.

```markdown
# Tomato soup

A simple weeknight soup.

![Tomato soup details photo](images/tomato-soup.jpg)

## Recipe

| Campo | Valor |
| --- | --- |
| Idioma | pt-PT |
| Tipo de aparelho | Monsieur Cuisine connect |
| Doses | 4 (porções) |
| Tempo de preparação | 10 |
| Tempo total | 35 |

## Ingredients

- 800 g ripe tomatoes
- 1 onion, quartered
- 500 ml vegetable stock

## Steps

1. Chop the onion for 5 seconds at speed 5.
2. Add tomatoes and stock. Cook for 25 minutes at 100°C, speed 2.
3. Blend for 1 minute, increasing gradually to speed 8.
```

Required table fields: the locale field must appear once and match a locale supported by the Monsieur Cuisine website; device type (one or more integer IDs or localized device names; comma-separated values are accepted); and servings as a positive count followed by a unit from that locale's serving-unit list. Category and complexity values can also use IDs or their localized names. Serving and ingredient units are checked against the selected locale. Recipe table labels can use the localized labels for that locale shown above or the existing CLI property names (for example, `languageLocale`, `deviceTypeIds`, and `preparationTime`). Optional fields include recipe ID (positive integer or Monsieur Cuisine recipe link; selects update instead of create when publishing), ingredient group, preparation and total time, categories, difficulty, tips, nutrition, thumbnail, and recipe photo. Recipes are privately published by default; the action uses the API's `private-publish` status. Status is managed by the action rather than Markdown.

Nutrition can be supplied as a table under `## Nutrition` with `Nutrient`, `Amount`, and `Unit` columns. Ingredient lines are converted to ingredient entries with their text in `name`; steps become manual recipe steps with `mode: null`. The action does not infer machine modes, quantities, or units from prose. Review the generated JSON before publishing, and use `recipes get` to inspect existing recipes for the exact device-specific mode schema your cooker uses.

To retain structured ingredient data or machine modes, append hidden Markdown annotations to the readable line: `<!-- mc-ingredient: {"amount":"100","unit":"g","isOptional":false} -->` and `<!-- mc-mode: {"type":"slow_cooking","deviceSettings":[{"time":900,"temperature":50,"order":0}]} -->`. When publishing, declared images are passed to the CLI's image-upload options for both creation and update; the generated payload never reuses old API media IDs.

## Use in a cookbook repository

The action has three operations:

- `validate` (the default) parses every matching Markdown recipe, checks required fields and localized dropdown values, and writes JSON payloads.
- `publish` converts the Markdown, creates or updates private recipes, and opens a pull request recording recipe IDs for recipes whose IDs are not in the Markdown yet.
- `get` fetches one recipe by ID or full Monsieur Cuisine URL, writes the response to `recipe.json`, and creates a cookbook Markdown file.

For `validate` and `publish`, `recipes` selects Markdown files with a glob and defaults to `recipes/**/*.md`. The optional `recipe_files` input accepts a JSON array of exact repo-relative Markdown paths and takes precedence over the glob. Use it when a workflow should publish only the files changed by a push.

The cookbook only needs small workflow files to choose when each operation runs. The validation workflow can run on recipe pull requests:

```yaml
name: Validate recipes
on:
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: fopina/monsieur-cuisine-cli@main
        with:
          operation: validate
```

Publishing runs after changes reach `main`, or manually after confirmation. The action handles authentication, title matching, create/update, ID recording, and the follow-up pull request; the cookbook workflow contains no publishing scripts.

```yaml
name: Publish recipes
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      confirm_publish:
        description: Publish every Markdown recipe as private
        type: boolean
        required: true
        default: false
permissions:
  contents: write
  pull-requests: write
jobs:
  publish:
    if: ${{ github.event_name == 'push' || inputs.confirm_publish }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: fopina/monsieur-cuisine-cli@main
        with:
          operation: publish
          session_token: ${{ secrets.MC_API_ACCESS_TOKEN }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          secrets_write_token: ${{ secrets.GH_SECRETS_WRITE_TOKEN }}
```

Configure `MC_API_ACCESS_TOKEN` with the `accessToken` value from the CLI `session.json`. `GH_SECRETS_WRITE_TOKEN` is optional; when supplied with permission to update repository Actions secrets, the action saves a rotated API token back to `MC_API_ACCESS_TOKEN`. Without it, update that secret if the API token is refreshed during a run. The workflow's `GITHUB_TOKEN` needs `contents: write` and `pull-requests: write`; repository settings must also allow GitHub Actions to create pull requests.

To fetch an existing recipe on demand, set the `recipe` input to a positive numeric ID or a full HTTP(S) URL. IDs run `recipes get`; URLs run `recipes url`. The action writes the Markdown file under `recipes/` by default; set `markdown_output` to choose another directory. The `markdown-file` action output contains its path. Numeric IDs are retained in the Markdown `recipeId` field; URL imports omit that field so publishing creates a cookbook-owned copy.

```yaml
name: Get recipe
on:
  workflow_dispatch:
    inputs:
      recipe:
        description: Recipe ID or full Monsieur Cuisine recipe URL
        required: true
        type: string
jobs:
  get-recipe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: recipe
        uses: fopina/monsieur-cuisine-cli@main
        with:
          operation: get
          recipe: ${{ inputs.recipe }}
          session_token: ${{ secrets.MC_API_ACCESS_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: recipe-json
          path: ${{ steps.recipe.outputs.output-directory }}
```

Inputs `recipes` and `output` can override `recipes/**/*.md` and `build/recipes`. Generated files are named after their Markdown file. A missing match, invalid recipe, publish failure, or ambiguous title match fails the operation.
