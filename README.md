# monsieur-cuisine-cli

A command-line client for managing recipes in a monsieur-cuisine.com account.

The CLI supports Lidl account sign-in, profile lookup, recipe listing and retrieval, recipe creation and updates, public recipe URL lookup, and direct API requests. It is an unofficial community project; see the [disclaimer](#disclaimer).

## Install

Run the latest release from PyPI without installing it permanently:

```sh
uvx --from monsieur-cuisine-cli monsieur-cuisine --help
```

Or install it as a persistent uv tool:

```sh
uv tool install monsieur-cuisine-cli
monsieur-cuisine --help
```

The executable is named `monsieur-cuisine` in both cases. For project development setup, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Sign in

Start the Lidl OAuth login flow used by the Monsieur Cuisine Android app:

```sh
monsieur-cuisine auth login
```

By default, login opens a visible Chromium window through Playwright and captures the app's OAuth callback automatically. If Playwright Chromium is missing, the CLI installs it automatically. Complete sign-in and any reCAPTCHA challenge in the browser.

To use your system browser instead, pass `--browser`:

```sh
monsieur-cuisine auth login --browser
```

Copy the final redirect URL beginning with `lidl-com.monsieur-cuisine.companion://` and paste it into the terminal when prompted.

The session is saved beside the config file, by default at `~/.config/monsieur-cuisine/session.json` (or under `$XDG_CONFIG_HOME`). The file is restricted to the account owner. Check or clear the saved session with:

```sh
monsieur-cuisine auth status
monsieur-cuisine auth renew
monsieur-cuisine auth logout
```

## Use the CLI

View your profile and list or fetch your recipes:

```sh
monsieur-cuisine profile
monsieur-cuisine recipes list
monsieur-cuisine recipes list --page 2 --size 50
monsieur-cuisine recipes get 238467
```

Create and update recipes by passing JSON data:

```sh
monsieur-cuisine recipes create --data '{"status":"draft","source":"member","languageLocale":"pt-PT","deviceTypeIds":[13],"title":"My recipe","servingSizes":[]}'
monsieur-cuisine recipes update 238467 --data '{"status":"draft","source":"member","languageLocale":"pt-PT","deviceTypeIds":[13],"title":"Updated recipe","servingSizes":[]}'
```

Recipe listing and retrieval use the observed authenticated v3 routes by default. `--use-v1` selects the deprecated v1 routes for those commands. Recipe writes send data directly to the account API; use valid IDs and include fields you want to retain in an update.

Resolve a public recipe page URL to its API details:

```sh
monsieur-cuisine recipes url 'https://www.monsieur-cuisine.com/pt-pt/recipe/pasta-de-abacate-com-salmao-2'
```

Call an API endpoint directly with the saved session:

```sh
monsieur-cuisine api api/v2/recipes/238467
monsieur-cuisine api api/v1/my-recipes/page/1/size/20
monsieur-cuisine api api/v1/custom-endpoint --method POST --data '{"name":"My recipe"}'
```

Supported methods are `GET`, `POST`, `PUT`, `PATCH`, and `DELETE`. Supply a relative API path; requests always go to the Monsieur Cuisine API host. Write methods can change account data, and endpoints requiring the app's encrypted request/response format are not automatically encrypted or decrypted.

## Configuration

On first run, the CLI creates `~/.config/monsieur-cuisine/config.toml` (or the platform's user config location) from its packaged defaults. View or edit login defaults with:

```sh
monsieur-cuisine config
monsieur-cuisine config --edit
```

The global `--lang` option sets the locale for API requests and Lidl sign-in; it defaults to `en-US`. For example:

```sh
monsieur-cuisine --lang pt-PT profile
```

Use `--config PATH` to select another config file, or `--env NAME` to merge a named `[env.NAME]` section. Use `--session-file NAME` to choose a different session filename; relative names resolve beside the config file.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, checks, and API research notes.

## Disclaimer

This is an unofficial community project and is not affiliated with or endorsed by monsieur-cuisine.com, Lidl, or their operators. Use it only with an account you are authorized to access, and follow the services' terms and applicable policies.
