# Monsieur Cuisine cookbook action

This composite GitHub Action validates Markdown recipes, prepares draft recipes during cookbook pull requests, publishes recipes after merge, and fetches existing recipes.

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
| Dificuldade | fácil |
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

Required table fields: the locale field must appear once and match a locale supported by the Monsieur Cuisine website; device type (one or more integer IDs or localized device names; comma-separated values are accepted); servings as a positive count followed by a unit from that locale's serving-unit list; and complexity (an integer ID or localized complexity name). Complexity is required in Markdown and validated in PRs so recipes are ready to publish after merge; the API's draft operation itself can omit it. Category values can also use IDs or localized names. Serving and ingredient units are checked against the selected locale. Recipe table labels can use the localized labels for that locale shown above or the existing CLI property names (for example, `languageLocale`, `deviceTypeIds`, `complexityId`, and `preparationTime`). Optional fields include recipe ID (positive integer or Monsieur Cuisine recipe link; selects update instead of create when publishing), ingredient group, preparation and total time, categories, tips, nutrition, thumbnail, and recipe photo. Recipes are privately published by default; the action uses the API's `private-publish` status. Status is managed by the action rather than Markdown.

Nutrition can be supplied as a table under `## Nutrition` with `Nutrient`, `Amount`, and `Unit` columns. Ingredient lines are converted to ingredient entries with their text in `name`; steps become manual recipe steps with `mode: null`. The action does not infer machine modes, quantities, or units from prose. Review the generated JSON before publishing, and use `recipes get` to inspect existing recipes for the exact device-specific mode schema your cooker uses.

To retain structured ingredient data or machine modes, append hidden Markdown annotations to the readable line: `<!-- mc-ingredient: {"amount":"100","unit":"g","isOptional":false} -->` and `<!-- mc-mode: {"type":"slow_cooking","deviceSettings":[{"time":900,"temperature":50,"order":0}]} -->`. When publishing, declared images are passed to the CLI's image-upload options for both creation and update; the generated payload never reuses old API media IDs.

## Use in a cookbook repository

The action has four operations:

- `validate` (the default) parses every matching Markdown recipe, checks required fields and localized dropdown values, and writes JSON payloads.
- `draft` converts selected Markdown recipes, creates a draft if no ID or matching account recipe exists, writes the ID into the recipe Markdown, and commits that change back to the same-repository pull request branch. Matching existing recipes are associated but not changed until merge.
- `publish` converts the Markdown and updates the existing recipe ID to private-published status. New recipes must already have an ID from the pull-request draft operation.
- `get` fetches one recipe by ID or full Monsieur Cuisine URL, writes the response to `recipe.json`, and creates a cookbook Markdown file.

For `validate`, `draft`, and `publish`, `recipes` selects Markdown files with a glob and defaults to `recipes/**/*.md`. The optional `recipe_files` input accepts a JSON array of exact repo-relative Markdown paths and takes precedence over the glob. Use it to process only the recipe files changed by a pull request or push.

The validation workflow can run on recipe pull requests:

```yaml
name: Validate recipes
on:
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: fopina/monsieur-cuisine-cli@main
        with:
          operation: validate
```

### Recipe pull-request workflow

When a new recipe is opened as a same-repository pull request, the `draft` operation creates the recipe immediately in the connected Lidl/Monsieur Cuisine account with draft status. It then writes the returned `recipeId` into that recipe's Markdown file and commits the ID to the existing PR branch. This lets the PR review the exact recipe identity that will be published, without opening a second PR. The draft is not publicly published while the recipe PR is open.

After the recipe PR is merged, the publish workflow uses that `recipeId` to update the same account recipe to private-published status. Existing recipes are only associated with the PR during draft preparation; they are not modified until merge. PR validation runs independently and requires all recipe fields, including complexity, even though the API's draft operation itself can omit complexity.

The draft workflow needs `contents: write` to update the existing same-repository PR branch and `MC_API_ACCESS_TOKEN` to create or find the account recipe. PRs from forks are skipped because their workflows do not receive write credentials. If a PR is abandoned after creating a draft, that draft may remain in the account. The workflow does not need the repository setting that allows Actions to create pull requests, because it updates the existing PR rather than opening a new one.

```yaml
name: Prepare recipe drafts
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: write
jobs:
  draft-recipes:
    if: ${{ github.event.pull_request.head.repo.full_name == github.repository }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - id: changed
        shell: bash
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          files="$(git diff --name-only -z --diff-filter=ACMR "$BASE_SHA" "$HEAD_SHA" -- recipes/ | python -c 'import json,sys; print(json.dumps([p for p in sys.stdin.buffer.read().decode().split("\0") if p.lower().endswith(".md")]))')"
          echo "recipe_files=$files" >> "$GITHUB_OUTPUT"
      - if: ${{ steps.changed.outputs.recipe_files != '[]' }}
        uses: fopina/monsieur-cuisine-cli@main
        with:
          operation: draft
          recipe_files: ${{ steps.changed.outputs.recipe_files }}
          session_token: ${{ secrets.MC_API_ACCESS_TOKEN }}
          secrets_write_token: ${{ secrets.GH_SECRETS_WRITE_TOKEN }}
```

After the PR is merged, publishing runs on `main` or manually after confirmation. The action updates recipes by their recorded IDs and does not open a second PR:

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
  contents: read
jobs:
  publish:
    if: ${{ github.event_name == 'push' || inputs.confirm_publish }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: fopina/monsieur-cuisine-cli@main
        with:
          operation: publish
          session_token: ${{ secrets.MC_API_ACCESS_TOKEN }}
          secrets_write_token: ${{ secrets.GH_SECRETS_WRITE_TOKEN }}
```

Configure `MC_API_ACCESS_TOKEN` with the `accessToken` value from the CLI `session.json`. `GH_SECRETS_WRITE_TOKEN` is optional; when supplied with permission to update repository Actions secrets, the action saves a rotated API token back to `MC_API_ACCESS_TOKEN`. Without it, update that secret if the API token is refreshed during a run. The draft workflow's `GITHUB_TOKEN` needs `contents: write` to commit IDs to the same-repository PR branch. The repository setting that allows Actions to create pull requests is not needed because this workflow updates an existing PR rather than opening a new one.

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
      - uses: actions/checkout@v5
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
