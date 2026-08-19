# docugen — monday.com app skeleton

Wraps the `docugen` engine (`../docugen.py`) in the two things monday needs: a **custom
action** the automation engine can call, and an **item view** people can click. The
rendering, PDF conversion, and file upload are unchanged — this layer only handles auth,
payload shapes, and job management.

```
monday automation  ──POST──▶  /monday/actions/generate  ─┐
                                                         ├─▶ jobs ─▶ docugen ─▶ .docx/.pdf ─▶ Files column
item view (iframe) ──POST──▶  /api/generate  ────────────┘
```

## Files

| File | Role |
|---|---|
| `app.py` | Flask routes — the monday-facing surface |
| `monday_auth.py` | JWT verification; the signing-secret and client-secret flows are **not** interchangeable |
| `generator.py` | Template resolution + the call into `docugen` |
| `jobs.py` | Background queue so the action URL can answer in milliseconds |
| `static/item-view.html` | The iframe UI (monday JS SDK from CDN) |
| `oauth.py` | OAuth 2.1 + PKCE, rotating refresh tokens, per-account token store |
| `fixtures.py` | Fake monday API responses for offline development |
| `tests_app.py` | 20 checks covering auth, both entry points, and output |
| `tests_oauth.py` | 36 checks covering PKCE, replay, rotation, and token precedence |

## Run it locally

```bash
cd ~/monday-docugen && .venv/bin/python monday-app/tests_app.py
```

Or serve it — the launch config **monday docugen app** (port 8302) is already registered,
so `preview_start` brings it up with `DOCUGEN_FAKE_MONDAY=1` and dev secrets. Drop `.docx`
templates into `monday-app/templates/`.

Outside a monday iframe the SDK has no session token, so the view will say so rather than
hang. To exercise it, stub `mondayClient.get` in the console and re-run `init()`.

## Environment

See `.env.example`. The essentials:

| Variable | Purpose |
|---|---|
| `MONDAY_SIGNING_SECRET` | Verifies action + remote-options requests |
| `MONDAY_CLIENT_SECRET` | Verifies item-view session tokens, and signs OAuth exchanges. **Different secret** |
| `MONDAY_CLIENT_ID` | OAuth client id |
| `PUBLIC_BASE_URL` | Your app's public URL. Enables the `aud` check and derives the redirect URI — unset means the check is skipped, fine while tunnelling, not in production |
| `MONDAY_SCOPES` | Requested scopes; must be a subset of what the Developer Center allows |
| `MONDAY_API_TOKEN` | Single-account fallback, used only when no OAuth token is stored |
| `DOCUGEN_TOKEN_STORE` | Where per-account tokens live (0600 JSON) |
| `MONDAY_OAUTH_LEGACY=1` | The older non-expiring flow (no PKCE, no refresh) |
| `DOCUGEN_TEMPLATE_DIR` / `DOCUGEN_OUTPUT_DIR` | Where templates live and output lands |
| `DOCUGEN_FAKE_MONDAY=1` | Serve fixture data instead of calling monday |

## OAuth

monday's current flow is OAuth 2.1: PKCE is mandatory, access tokens expire, and refresh
tokens rotate on every use.

```
GET  /oauth/install     mint state + PKCE verifier → redirect to auth.monday.com
GET  /oauth/callback    validate state (single-use), exchange code, identify, store
GET  /oauth/status      does this account have working credentials?
POST /oauth/disconnect  revoke upstream, forget locally
```

Which token gets used for an API call, in order:

1. **`shortLivedToken`** from the integration request's own JWT — scoped to that request,
   so the action path needs no stored credentials at all.
2. The account's **stored OAuth token**, refreshed automatically when it's within 120s of
   expiring. The rotated refresh token is persisted in the same write; losing it means the
   user has to reconnect.
3. **`MONDAY_API_TOKEN`**, the single-account development fallback.

With none of those, the API answers `428` with an `installUrl`, and the item view turns
that into a *Connect monday account* button.

Expiry comes from the access token's own `exp` claim — monday's token response has no
`expires_in` field, so don't look for one.

In the Developer Center, register `<PUBLIC_BASE_URL>/oauth/callback` as a redirect URL and
enable the new OAuth flow on a draft version before promoting it.

**Token storage is a 0600 JSON file.** That is appropriate for a single-tenant deployment
and *not* for a distributed app — those are live credentials to other people's accounts.
Swap `TokenStore` for monday code's secure storage or a KMS-backed store before you
distribute.

## Wiring it up in the Developer Center

1. **Create the app** → add a **Feature: Item View**, URL `https://<your-host>/`.
2. Add a **Feature: Integration**, then a **custom action** named e.g. *Generate document*:
   - Run URL: `https://<your-host>/monday/actions/generate`
   - Input fields: `itemId` (item id), `template` (custom field with **remote options**
     URL `https://<your-host>/monday/fields/templates`), `outputFormat` (dropdown:
     `docx`, `pdf`), `filesColumn` (column picker), `filename` (text, optional)
3. Build the recipe sentence, e.g. *When {status} changes to {something}, generate a
   {template} as {outputFormat} into {filesColumn}*.
4. Copy the **Signing Secret** and **Client Secret** into your environment.
5. Scopes: `boards:read`, `assets:read`, and write access for the Files column upload.
6. Deploy: `npx @mondaycom/apps-cli mapps code:push` (monday code builds Python via
   buildpacks), or host anywhere public and point the URLs there.

## Known limits

**PDF depends on where you host, not on this code.** Conversion uses LibreOffice, which is
installed here and works. monday code builds from buildpacks and won't have that binary,
so on *that* host you either ship `.docx`, call a conversion service, or keep generation on
a container you control and let monday code enqueue.

**`jobs.py` is in-memory.** Jobs die with the process and don't span replicas.

**Token storage is a local file.** Fine for one account, wrong for a distributed app — see
the OAuth section.
