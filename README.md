# monsieur-cuisine-cli

A command-line client for managing recipes in a monsieur-cuisine.com account.

The CLI supports Lidl account sign-in, profile lookup, recipe listing and retrieval, recipe creation and updates, public recipe URL lookup, and direct API requests. It is an unofficial community project; see the [disclaimer](#disclaimer).

## Install

Run the latest release from PyPI without installing it permanently:

```sh
uvx monsieur-cuisine-cli --help
```

Or install it as a persistent uv tool:

```sh
uv tool install monsieur-cuisine-cli
monsieur-cuisine-cli --help
```

The executable is named `monsieur-cuisine-cli` in both cases. For project development setup, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Sign in

Start the Lidl OAuth login flow used by the Monsieur Cuisine Android app:

```sh
monsieur-cuisine-cli auth login
```

By default, login opens a visible Chromium window through Playwright and captures the app's OAuth callback automatically. If Playwright Chromium is missing, the CLI installs it automatically. Complete sign-in and any reCAPTCHA challenge in the browser.

To use your system browser instead, pass `--browser`:

```sh
monsieur-cuisine-cli auth login --browser
```

Copy the final redirect URL beginning with `lidl-com.monsieur-cuisine.companion://` and paste it into the terminal when prompted.

The session is saved beside the config file, by default at `~/.config/monsieur-cuisine/session.json` (or under `$XDG_CONFIG_HOME`). The file is restricted to the account owner. Check or clear the saved session with:

```sh
monsieur-cuisine-cli auth status
monsieur-cuisine-cli auth renew
monsieur-cuisine-cli auth logout
```

## Use the CLI

View your profile and list or fetch your recipes:

```sh
monsieur-cuisine-cli profile
monsieur-cuisine-cli recipes list
monsieur-cuisine-cli recipes list --page 2 --size 50
monsieur-cuisine-cli recipes get 238467
```

By default, recipe lists print a compact title, ID, and status summary, while recipe details show the main fields. Add `--json` to `profile`, `api`, `recipes url`, `recipes list`, `recipes get`, `recipes create`, or `recipes update` to print normalized response data as JSON.

Create and update recipes by passing JSON data:

```sh
monsieur-cuisine-cli recipes create --data '{"status":"draft","source":"member","languageLocale":"pt-PT","deviceTypeIds":[13],"title":"My recipe","servingSizes":[]}'
monsieur-cuisine-cli recipes update 238467 --data '{"status":"draft","source":"member","languageLocale":"pt-PT","deviceTypeIds":[13],"title":"Updated recipe","servingSizes":[]}'
```

Add `--thumbnail PATH` and/or `--details-image PATH` to upload local recipe images during creation or update. The CLI uploads them and adds the returned media IDs to the recipe payload.

Recipe listing and retrieval use the observed authenticated v3 routes by default. `--use-v1` selects the deprecated v1 routes for those commands. Recipe writes send data directly to the account API; use valid IDs and include fields you want to retain in an update.

Resolve a public recipe page URL to its API details:

```sh
monsieur-cuisine-cli recipes url 'https://www.monsieur-cuisine.com/pt-pt/recipe/pasta-de-abacate-com-salmao-2'
```

Call an API endpoint directly with the saved session:

```sh
monsieur-cuisine-cli api api/v2/recipes/238467
monsieur-cuisine-cli api api/v1/my-recipes/page/1/size/20
monsieur-cuisine-cli api api/v1/custom-endpoint --method POST --data '{"name":"My recipe"}'
```

Supported methods are `GET`, `POST`, `PUT`, `PATCH`, and `DELETE`. Supply a relative API path; requests always go to the Monsieur Cuisine API host. Write methods can change account data, and endpoints requiring the app's encrypted request/response format are not automatically encrypted or decrypted.

## Configuration

On first run, the CLI creates `~/.config/monsieur-cuisine/config.toml` (or the platform's user config location) from its packaged defaults. View or edit login defaults with:

```sh
monsieur-cuisine-cli config
monsieur-cuisine-cli config --edit
```

The global `--lang` option sets the locale for API requests and Lidl sign-in; it defaults to `en-US`. For example:

```sh
monsieur-cuisine-cli --lang pt-PT profile
```

Use `--config PATH` to select another config file, or `--env NAME` to merge a named `[env.NAME]` section. Use `--session-file NAME` to choose a different session filename; relative names resolve beside the config file.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, checks, and API research notes.

## Disclaimer

This is an unofficial community project and is not affiliated with or endorsed by monsieur-cuisine.com, Lidl, or their operators. Use it only with an account you are authorized to access, and follow the services' terms and applicable policies.
