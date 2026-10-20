## Build

This project uses `uv`, so set up the virtualenv by running

```
uv sync --dev
```

Use `make test` to make sure all tests pass before pushing.

Use `make lint` to make sure lint check passes before pushing.

## Guidelines

...

## API research notes

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
