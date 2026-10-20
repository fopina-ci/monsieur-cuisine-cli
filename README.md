# monsieur-cuisine-cli

A command-line client for managing recipes in a monsieur-cuisine.com account.

This project is at an early stage. Account sign-in and a read-only profile command are implemented; recipe management commands are planned.

The command tree is built with [classyclick](https://github.com/fopina/classyclick), a class-based wrapper around Click.

## Install for development

This project uses [uv](https://docs.astral.sh/uv/) for Python environment and dependency management.

```sh
uv sync --dev
```

## Sign in

Start the Lidl OAuth login flow used by the Monsieur Cuisine Android app:

```sh
uv run monsieur-cuisine auth login
```

By default, login opens its own visible Chromium window through Playwright and captures the app's OAuth callback automatically. If Playwright Chromium is missing, the CLI runs `python -m playwright install chromium` automatically before opening the browser. Complete sign-in and any reCAPTCHA challenge there; the CLI then exchanges the authorization code and performs the app's encrypted API login.

To use your system browser instead, pass the boolean `--browser` flag:

```sh
uv run monsieur-cuisine auth login --browser
```

After sign-in, copy the final redirect URL beginning with `lidl-com.monsieur-cuisine.companion://` and paste it into the terminal prompt. Depending on the browser, you may need to copy the URL from its address bar or redirect/error page. The CLI validates the callback's scheme, path, and OAuth `state` before exchanging the one-time authorization code.

The API session defaults to `session.json` beside the active config TOML file (by default `~/.config/monsieur-cuisine/session.json`, or under `$XDG_CONFIG_HOME`). Set the root `--session-file NAME` option to choose another filename; relative names resolve beside the config file, while an absolute path is used as given. The session has owner-only file permissions. The global `--lang` option sets the locale for API requests and Lidl sign-in, and defaults to `en-US`. The login flow uses that locale for the OAuth `Language` and `CountryCode` parameters. For example: `uv run monsieur-cuisine --lang de-DE auth login`.

Check or clear the saved session:

```sh
uv run monsieur-cuisine auth status
uv run monsieur-cuisine auth renew
uv run monsieur-cuisine profile
uv run monsieur-cuisine auth logout
```

`auth status` reports whether a session file is saved, the account name when available, and the API token expiry in your local timezone. `auth renew` refreshes the Monsieur Cuisine API access token using the saved API token and updates it in the session file. OAuth credentials are used only during login and are not stored in the session file.

## Call an API endpoint

Use `api` to call a path on the Monsieur Cuisine API with the saved app session. The command adds the app's standard request headers and bearer token, then prints the JSON response:

```sh
uv run monsieur-cuisine api api/v2/recipes/238467
uv run monsieur-cuisine api api/v1/my-recipes/page/1/size/20
uv run monsieur-cuisine api api/v1/custom-endpoint --method POST --data '{"name":"My recipe"}'
```

Supported methods are `GET`, `POST`, `PUT`, `PATCH`, and `DELETE`. Pass an optional JSON request body with `--data`. API calls default to `Accept-Language: en-US`, matching the mobile app's default API locale. Set the global option before the command to override it, for example `uv run monsieur-cuisine --lang pt-PT api api/v1/users`. Recipe URL lookups use the viewer language discovered from the recipe page. Supply a relative API path rather than a URL; the command always targets `mc-api.tecpal.com` so the saved bearer token is not sent to another host. Endpoints requiring the app's encrypted request/response format are not automatically encrypted or decrypted by this command. Write methods call the account API directly and can change account data.

Use `recipes list` to list recipes in your account, and `recipes get` to fetch one by ID. The list command defaults to page 1 with 20 recipes; use `--page` and `--size` to change the pagination:

```sh
uv run monsieur-cuisine recipes list
uv run monsieur-cuisine recipes list --page 2 --size 50
uv run monsieur-cuisine recipes list --use-v1
uv run monsieur-cuisine recipes get 238467
uv run monsieur-cuisine recipes get 238467 --use-v1
uv run monsieur-cuisine recipes create --data '{"status":"draft","source":"member","languageLocale":"pt-PT","deviceTypeIds":[13],"title":"My recipe","servingSizes":[]}'
uv run monsieur-cuisine recipes update 238467 --data '{"status":"draft","source":"member","languageLocale":"pt-PT","deviceTypeIds":[13],"title":"Updated recipe","servingSizes":[]}'
```

`recipes list` and `recipes get` use the observed authenticated v3 routes by default. The list request includes page and size, sorts by title ascending, and asks for draft, pending, private-publish, publish, and rejected recipes with an empty search query. Pass `--use-v1` to either command to use its deprecated v1 route; the CLI prints a warning when this flag is set. These direct API requests use the saved mobile-app bearer token. The global `--lang` option selects another locale.

Use `recipes url` to resolve a public recipe page URL. It extracts `recipeId` and the viewer locale from the page, calls the public recipe detail endpoint, and returns the ID, locale, and API response:

```sh
uv run monsieur-cuisine recipes url 'https://www.monsieur-cuisine.com/pt-pt/recipe/pasta-de-abacate-com-salmao-2'
```

## Configuration

The CLI reads TOML settings from `~/.config/monsieur-cuisine/config.toml` (or the platform's user config directory). On first run it creates this file from the packaged default config. Login defaults can be edited with:

```sh
uv run monsieur-cuisine config
uv run monsieur-cuisine config --edit
```

The default config stores the global locale as root-level `lang = "en-US"` and the browser setting under `[auth.login]`. Command-line options override config values. Use the root `--config PATH` option to select a different file, or `--env NAME` to merge a named `[env.NAME]` section.

## Planned capabilities

- Add a recipe to the account.
- Update an existing recipe.
- Remove a recipe from the account.

## Research notes

The Android app is used as a reference for the undocumented account and recipe API. Monsieur Cuisine App **1.4.2** was downloaded from the [APKMirror Monsieur Cuisine App listing](https://www.apkmirror.com/apk/lidl-digital-international-gmbh-co-kg/monsieur-cuisine-app/) and decoded to smali with [fopina/docker-dedroid](https://github.com/fopina/docker-dedroid). The APK and generated decompilation are kept in the local, gitignored `.apk-analysis/` directory; download the APK from APKMirror yourself before running the command below.

```sh
mkdir -p .apk-analysis
# Save the APKMirror download as .apk-analysis/monsieur-cuisine-1.4.2.apk
docker run --rm -v "$PWD/.apk-analysis:/work" fopina/dedroid apktool d \
  /work/monsieur-cuisine-1.4.2.apk -o /work/decompiled -f
```

The decoded manifest registers `lidl-com.monsieur-cuisine.companion://login/prod` as the app's login callback. The app uses `https://accounts.lidl.com` for sign-in and calls `https://mc-api.tecpal.com` directly for its API, authenticating account-specific requests with a bearer token. Decompiled Retrofit interfaces include public recipe routes such as `GET api/v2/recipes/page/{page}/size/{size}`, `GET api/v2/recipes/{id}`, and `GET api/v1/recipes/search/page/{page}/size/{size}`. They also include authenticated account routes `GET api/v1/my-recipes/page/{page}/size/{size}` and `GET api/v1/my-recipes/{id}`. No mobile API method for updating recipe content has been identified so far; the `RecipeUpdateModel` type is used as the response model for the recipe detail GET route.

### Website `proxy-api` requests

The web client does not call the API with the mobile app's JWT bearer token. It sends a same-origin `POST https://www.monsieur-cuisine.com/proxy-api` request, authenticated by the browser's website/session cookies. The JSON body describes the upstream API call with `endpoint`, `method`, and `lang`, and can include a `payload` for request data. For example, the browser profile request is equivalent to:

```sh
curl 'https://www.monsieur-cuisine.com/proxy-api' \
  -X POST \
  -H 'Content-Type: application/json' \
  -H 'device-type: web' \
  --data-raw '{"endpoint":"api/v1/users","lang":"pt-PT","method":"GET"}'
```

The browser also sends ordinary same-origin headers (such as `Origin`, `Referer`, and a request ID) and its session cookies. Do not copy session cookies, SSO tokens, or other credentials into research notes or source control. The wrapper forwards the described request and returns the API response envelope; the observed profile response has the user object at `data.user`. This is the web transport and cookie-authentication path, distinct from this CLI's direct calls to `https://mc-api.tecpal.com` with `Authorization: Bearer ...` and the Android request headers.

### Profile route comparison

The web profile example requests `GET api/v1/users` through `proxy-api` and returns a response shaped like `{"code":0,"message":"...","data":{"user":{...}}}`. The CLI's `profile` command instead requests `GET https://mc-api.tecpal.com/api/v1/users/` directly with its saved mobile API bearer token, `Accept-Language`, `Device-Type: android`, app version, request ID, and preproduction key. It passes the response through `_api_data`, which unwraps the common `data` envelope but does not additionally select the nested `user` property. The web response's `data.user` nesting therefore differs from the mobile helper's normalized result; callers should not assume both commands return identical JSON shapes. This comparison is based on the supplied web request/response and current CLI implementation.

### Recipe v3 observation

The website's recipe editor requested `GET api/v3/auth/user/recipes/{id}` through `proxy-api`; its response contained `data.recipe` with the full authored recipe. The CLI uses that observed path directly against `mc-api.tecpal.com` for `recipes get`, with its existing bearer-token transport.

The HAR from the “all my recipes” page shows a list request to `GET api/v3/auth/user/recipes` with `size`, `page`, `sortBy[0][field]=title`, `sortBy[0][direction]=ASC`, repeated `filters[status][]` values (`draft`, `pending`, `private-publish`, `publish`, `rejected`), and an empty `q`. Its response has pagination metadata and a `recipes` array inside `data`. The CLI's `recipes list` now uses this route and parameter set. Pass `--use-v1` to `recipes list` or `recipes get` to select the retained deprecated routes `GET api/v1/my-recipes/page/{page}/size/{size}` or `GET api/v1/my-recipes/{id}`. Direct bearer-token compatibility with these web-discovered v3 routes has not yet been verified; the proxy requests establish the routes and response shapes, not that every mobile-authenticated account can call them.

The recipe editor HAR also shows creation as `POST api/v3/auth/user/recipes/` with the recipe object in `payload`; the observed request returned HTTP 201 and `data.recipe`. The sample created a draft and included `status`, `source`, `languageLocale`, `deviceTypeIds`, `title`, thumbnail/details image media IDs, `complexityId`, `allowSocialSharing`, `categoryIds`, `nutrients`, and `servingSizes` (including steps and ingredient groups). The CLI exposes this as `recipes create --data '{...}'`, sending that object as JSON directly to the API. A v1 create route was not identified, so no v1 fallback is available for creation. Use valid IDs and payload fields for the target account and locale; the captured example's IDs are specific to that website account/content.

The update HAR shows `PUT api/v3/auth/user/recipes/{id}` with a recipe object in `payload`; the observed response was HTTP 200 with the updated recipe at `data.recipe`. The request includes the recipe's status, source, locale, device types, title, media references, complexity, sharing flag, categories, nutrients, and serving sizes with ingredient groups and steps. The CLI exposes this as `recipes update {id} --data '{...}'`, sending the JSON object as the PUT body. No v1 update endpoint was identified. This is a full recipe-shaped payload, so retain fields that should remain on the recipe when constructing an update.

The `recipes create` and `recipes update` commands check for known response-shaped fields before sending a write. They reject `deviceTypes`, `categories`, and `complexity` in favor of `deviceTypeIds`, `categoryIds`, and `complexityId`; expanded thumbnail/details-image media objects in favor of media ID fields; and response-only nutrient, serving-size, and step fields. The error lists each offending path and the expected write shape.

Recipe helpers unwrap the common top-level `data` envelope before printing results, matching the profile helper's behavior. This removes wrapper fields such as `code` and `message` while preserving the endpoint's resource keys (for example, `recipe` or `recipes`).

The normalized outputs from live `profile`, `recipes list`, and `recipes get` calls are represented by redacted fixtures in `tests/fixtures/`; unit tests use them to guard the command output shape. Account identifiers, personal details, recipe text, media URLs, and timestamps are replaced with safe examples.

These observations come from Android app version 1.4.2 and website request examples, not a supported public API contract.

## Disclaimer

This is an unofficial community project and is not affiliated with or endorsed by monsieur-cuisine.com, Lidl, or their operators. Use it only with an account you are authorized to access, and follow the services' terms and applicable policies.
