# Repository instructions

## Website locales

The Monsieur Cuisine website's supported locales and recipe dropdown options can change over time. Refresh the checked-in locale map periodically with `python3 support/scripts/update_locales.py`, which reads the homepage's `siteLanguages` data. Refresh recipe validation data with `python3 support/scripts/update_validation_data.py`; it opens the site in Playwright so a maintainer can log in, verifies access to recipe data, closes the browser, then makes one `load_recipe_post` request per locale. Session cookies stay in memory. The script writes only dropdown guide data to `monsieur_cuisine_cli/recipe_validation_data.py`. Review generated diffs and keep the CLI's `--lang` choices, default, and packaged config aligned. The cookbook action converter uses the shared data in `action/convert.py` to validate its Recipe table and localized dropdown values.
