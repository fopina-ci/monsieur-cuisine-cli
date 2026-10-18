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

The API session is stored as `session.json` beside the active config TOML file (by default `~/.config/monsieur-cuisine/session.json`, or under `$XDG_CONFIG_HOME`). If you pass `--config PATH`, the session and companion ID are stored beside that file. The session has owner-only file permissions. The login flow always uses the mobile app's registered deep link and requests the English (UK) locale by default (`Language=en-GB`, `CountryCode=GB`). Use `--language` to request another locale, for example `uv run monsieur-cuisine auth login --language de-DE`.

Check or clear the saved session:

```sh
uv run monsieur-cuisine auth status
uv run monsieur-cuisine auth renew
uv run monsieur-cuisine profile
uv run monsieur-cuisine auth logout
```

`auth status` reports whether a session file is saved, the account name when available, and the OAuth token expiry in your local timezone. `auth renew` exchanges the saved OAuth refresh token and updates the OAuth access token, expiry, and rotated refresh token in the session file.

## Configuration

The CLI reads TOML settings from `~/.config/monsieur-cuisine/config.toml` (or the platform's user config directory). On first run it creates this file from the packaged example. Login defaults can be edited with:

```sh
uv run monsieur-cuisine config
uv run monsieur-cuisine config --edit
```

The example config stores the `browser` setting under `[auth.login]`. Command-line options override config values. Use the root `--config PATH` option to select a different file, or `--env NAME` to merge a named `[env.NAME]` section.

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

The decoded manifest registers `lidl-com.monsieur-cuisine.companion://login/prod` as the app's login callback. The app uses `https://accounts.lidl.com` for sign-in and `https://mc-api.tecpal.com` for its main API. Decompiled Retrofit interfaces include recipe list/detail/search routes such as `GET api/v2/recipes/page/{page}/size/{size}`, `GET api/v2/recipes/{id}`, and `GET api/v1/recipes/search/page/{page}/size/{size}`. These are implementation observations from app version 1.4.2, not a supported public API contract.

## Disclaimer

This is an unofficial community project and is not affiliated with or endorsed by monsieur-cuisine.com, Lidl, or their operators. Use it only with an account you are authorized to access, and follow the services' terms and applicable policies.
