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

The API session is stored as `session.json` beside the active config TOML file (by default `~/.config/monsieur-cuisine/session.json`, or under `$XDG_CONFIG_HOME`). If you pass `--config PATH`, the session and companion ID are stored beside that file. The session has owner-only file permissions. The global `--lang` option sets the locale for API requests and Lidl sign-in, and defaults to `en-US`. The login flow uses that locale for the OAuth `Language` and `CountryCode` parameters. For example: `uv run monsieur-cuisine --lang de-DE auth login`.

Check or clear the saved session:

```sh
uv run monsieur-cuisine auth status
uv run monsieur-cuisine auth renew
uv run monsieur-cuisine profile
uv run monsieur-cuisine auth logout
```

`auth status` reports whether a session file is saved, the account name when available, and the OAuth token expiry in your local timezone. `auth renew` exchanges the saved OAuth refresh token and updates the OAuth access token, expiry, and rotated refresh token in the session file.

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
uv run monsieur-cuisine recipes get 238467
```

These use the authenticated mobile API routes `GET api/v1/my-recipes/page/{page}/size/{size}` and `GET api/v1/my-recipes/{id}`, with `Accept-Language: en-US` by default. Use the global `--lang` option to select another locale.

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

The website uses a same-origin `POST https://www.monsieur-cuisine.com/proxy-api` wrapper. Its JSON body contains an upstream `endpoint`, `lang`, and HTTP `method`, with an optional `payload`; for example, a profile request uses `{"endpoint":"api/v1/users","lang":"pt-PT","method":"GET"}`. The website authenticates these requests through its browser session cookies, rather than the mobile app's bearer-token request flow. The proxy forwards requests to the same API routes used by the app, so endpoint methods and payloads discovered through either client are likely useful for the other as well. The transport, authentication, and required headers still differ, and this cross-client compatibility has not been verified for every route. These observations come from app version 1.4.2 and a website request example, not a supported public API contract.

## Disclaimer

This is an unofficial community project and is not affiliated with or endorsed by monsieur-cuisine.com, Lidl, or their operators. Use it only with an account you are authorized to access, and follow the services' terms and applicable policies.
