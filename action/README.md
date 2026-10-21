# Monsieur Cuisine cookbook action

This composite GitHub Action validates Markdown recipes and converts each one to a JSON payload accepted by `monsieur-cuisine-cli recipes create --data`.

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

Required table fields: the locale field must be the first property and must match a locale supported by the Monsieur Cuisine website; device type (one or more integer IDs or localized device names; comma-separated values are accepted); and servings as a positive count followed by a unit from that locale's serving-unit list. Category and complexity values can also use IDs or their localized names. Serving and ingredient units are checked against the selected locale. Recipe table labels can use the localized labels for that locale shown above or the existing CLI property names (for example, `languageLocale`, `deviceTypeIds`, and `preparationTime`). Optional fields include recipe ID (positive integer or Monsieur Cuisine recipe link; selects update instead of create when publishing), ingredient group, preparation and total time, categories, difficulty, tips, nutrition, thumbnail, and recipe photo. Recipes are privately published by default; the action uses the API's `private-publish` status. Status is managed by the action rather than Markdown.

Nutrition can be supplied as a table under `## Nutrition` with `Nutrient`, `Amount`, and `Unit` columns. Ingredient lines are converted to ingredient entries with their text in `name`; steps become manual recipe steps with `mode: null`. The action does not infer machine modes, quantities, or units from prose. Review the generated JSON before publishing, and use `recipes get` to inspect existing recipes for the exact device-specific mode schema your cooker uses.

To retain structured ingredient data or machine modes, append hidden Markdown annotations to the readable line: `<!-- mc-ingredient: {"amount":"100","unit":"g","isOptional":false} -->` and `<!-- mc-mode: {"type":"slow_cooking","deviceSettings":[{"time":900,"temperature":50,"order":0}]} -->`. When publishing, declared images are passed to the CLI's image-upload options for both creation and update; the generated payload never reuses old API media IDs.

## Use in a cookbook repository

```yaml
name: Validate cookbook
on:
  pull_request:
  push:
    branches: [main]
jobs:
  recipes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: fopina/monsieur-cuisine-cli@github-action-cookbook
        id: cookbook
      - uses: actions/upload-artifact@v4
        with:
          name: recipe-json
          path: ${{ steps.cookbook.outputs.output-directory }}
```

Inputs `recipes` and `output` can override the defaults `recipes/**/*.md` and `build/recipes`. A missing recipe match or invalid recipe fails the action. Generated files are named after their Markdown file and written as UTF-8 JSON.
