# Monsieur Cuisine cookbook action

This composite GitHub Action validates Markdown recipes, prepares draft recipes during cookbook pull requests, publishes recipes after merge, and fetches existing recipes.

For a ready-made repository to store your recipes, start from the [Monsieur Cuisine cookbook template](https://github.com/fopina/monsieur-cuisine-cookbook-template). This guide remains the reference for the recipe format, validation rules, and action operations.

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
| ingredientGroupName | Ingredientes |
| Dificuldade | fácil |
| preparationTime | 10 |
| readyInTime | 35 |

## Ingredients

- 800 g ripe tomatoes
- 1 onion, quartered
- 500 ml vegetable stock

## Steps

1. Chop the onion for 5 seconds at speed 5.
2. Add tomatoes and stock. Cook for 25 minutes at 100°C, speed 2.
3. Blend for 1 minute, increasing gradually to speed 8.
```

Required table fields: the locale field must appear once and match a locale supported by the Monsieur Cuisine website; device type (one or more integer IDs or localized device names; comma-separated values are accepted); servings as a positive count followed by a unit from that locale's serving-unit list; complexity (an integer ID or localized complexity name); `readyInTime` as a positive integer; and a non-empty `ingredientGroupName`. `preparationTime` may be a positive integer or `null` when the source does not provide a preparation time. These values are validated in PRs. A details image is also required for private publishing: provide it immediately after the description or with the `detailsImage` Recipe-table property. Category values can also use IDs or localized names. Serving and ingredient units are checked against the selected locale. Recipe table labels can use the localized labels for that locale shown above or the existing CLI property names (for example, `languageLocale`, `deviceTypeIds`, `complexityId`, and `preparationTime`). Optional fields include recipe ID (positive integer or Monsieur Cuisine recipe link; selects update instead of create when publishing), categories, tips, nutrition, and thumbnail. Recipes are privately published by default; the action uses the API's `private-publish` status. Status is managed by the action rather than Markdown.

Nutrition can be supplied as a table under `## Nutrition` with `Nutrient`, `Amount`, and `Unit` columns. Ingredient lines use `- ingredient name — amount unit`, for example `- tomatoes — 800 g`; the amount may be omitted, and the exact suffix `(optional)` sets `isOptional`, as in `- parsley — 1 tsp (optional)`. Units are validated against the locale's ingredient-unit list. A bare line such as `- salt` has no amount or unit. Device settings appear immediately after each step with an explicit `Mode:` (or localized `Modo:`) marker, followed by the readable mode label and controls. The marker makes the line unambiguous to the converter: marked lines are parsed and validated, and malformed mode data fails conversion. `mode: null` is represented by no mode line.

For example, put this immediately after the corresponding numbered step:

````md
1. **Cozinhar**: Cozinhe lentamente.
   **Modo:** **Cozedura personalizada** (`customized`) · Temperatura: 100 °C · Duração: 8 min. · Velocidade: 2 · Direção: Direita
````

The older fenced JSON blocks and hidden `mc-mode` annotation remain accepted when converting existing Markdown. Legacy `mc-ingredient` annotations are also accepted, but new ingredient lines should use the readable text syntax above. The API mode key is kept in parentheses after its localized label so conversion can preserve the exact mode. When publishing, declared images are passed to the CLI's image-upload options for both creation and update; the generated payload never reuses old API media IDs.

## Use in a cookbook repository

The action has five operations:

- `validate` (the default) parses every matching Markdown recipe, checks required fields and localized dropdown values, and writes JSON payloads.
- `draft` converts selected Markdown recipes, creates a draft if no ID or matching account recipe exists, writes the ID into the recipe Markdown, and commits that change back to the same-repository pull request branch. Matching existing recipes are associated but not changed until merge.
- `publish` converts the Markdown and updates the existing recipe ID to private-published status. New recipes must already have an ID from the pull-request draft operation.
- `get` fetches one recipe by ID or full Monsieur Cuisine URL, writes the response to `recipe.json`, and creates a cookbook Markdown file.
- `compare` compares two recipe JSON documents and exposes `recipes-equal` and `comparison-report` outputs without treating a valid mismatch as an operation failure.

For `get`, enable GitHub Actions step debug logging to include the complete CLI stdout and stderr responses in the workflow logs. You can enable it for a rerun in GitHub's rerun dialog, or by setting the `ACTIONS_STEP_DEBUG` secret or variable to `true` in the workflow repository. No workflow YAML change is needed. Recipe response contents will be visible in the logs; the session token is redacted and is never logged by this debug output.

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

When a new recipe is opened as a same-repository pull request, the `draft` operation creates the recipe immediately in the connected Lidl/Monsieur Cuisine account with draft status. It then writes the returned `recipeId` into that recipe's Markdown file and commits the ID to the existing PR branch. This lets the PR review the exact recipe identity that will be published, without opening a second PR. The draft is not publicly published while the recipe PR is open. PR validation also checks fields required by the API for later private publishing, including positive preparation/ready-in times, a details image, and a non-empty ingredient group name.

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

Configure `MC_API_ACCESS_TOKEN` with the `accessToken` value from the CLI `session.json`. For a safe CLI-based setup, see the [token transfer commands](../README-CLI.md#transfer-an-api-token). Every token-authenticated operation (`get`, `draft`, and `publish`) requires both `session_token` and `secrets_write_token`. Configure `GH_SECRETS_WRITE_TOKEN` with a token that can update repository Actions secrets. The action stores the access token in a temporary session file, compares its value before and after the operation, and writes `MC_API_ACCESS_TOKEN` back to the repository secret if it changed—even when the CLI operation fails. The draft workflow's `GITHUB_TOKEN` separately needs `contents: write` to commit IDs to the same-repository PR branch. The repository setting that allows Actions to create pull requests is not needed because this workflow updates an existing PR rather than opening a new one.

To fetch an existing recipe on demand, set the `recipe` input to a positive numeric ID or a full HTTP(S) URL. IDs run `recipes get`; URLs run `recipes url`. The action writes the Markdown file under `recipes/` by default; set `markdown_output` to choose another directory. The `markdown-file` action output contains its path, and `recipe-title` contains the fetched title. The action compares the recipe author with the authenticated profile: account-owned recipes keep their ID in `recipeId`, while other recipes record it as `originalRecipeId` for reference. A downloaded details image is placed under an `assets/` directory beside the generated Markdown when the source recipe has one.

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
          secrets_write_token: ${{ secrets.GH_SECRETS_WRITE_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: recipe-json
          path: ${{ steps.recipe.outputs.output-directory }}
```

Inputs `recipes` and `output` can override `recipes/**/*.md` and `build/recipes`. Generated files are named after their Markdown file. A missing match, invalid recipe, publish failure, or ambiguous title match fails the operation.
