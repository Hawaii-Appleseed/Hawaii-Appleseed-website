# docugen

A local, scriptable stand-in for the **DocuGen** monday.com app: pull data from a monday board,
drop it into your own Word template, save as .docx or PDF, and optionally push the result back
into a Files column on the item.

## Setup

```bash
cd ~/monday-docugen && .venv/bin/python docugen.py --help
```

The venv is already created with `docxtpl`, `python-docx`, and `requests`. To rebuild it:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**API token** — monday.com → avatar → *Developers* → *My access tokens*. Then either:

```bash
echo 'YOUR_TOKEN' > ~/.monday_api_key && chmod 600 ~/.monday_api_key
```

or set `MONDAY_API_TOKEN`, or pass `--token`.

**PDF output** uses LibreOffice, already installed here at
`/Applications/LibreOffice.app` (26.2.5, arm64) — `--pdf` works out of the box, roughly 2s per
document. On another machine, install LibreOffice or Microsoft Word and the script will find
either automatically.

## Workflow

**1. See what placeholders your board offers**

```bash
.venv/bin/python docugen.py columns --board 1234567890
```

```
PLACEHOLDER                        TYPE               COLUMN TITLE
{{ c.client_name }}                text               Client Name
{{ c.amount }}                     numbers            Amount
{{ c.due_date }}                   date               Due Date
```

**2. Get a starter template** (or just write your own .docx with those tags)

```bash
.venv/bin/python docugen.py scaffold --board 1234567890 --out templates/quote.docx
.venv/bin/python docugen.py scaffold --board 1234567890 --out templates/report.docx --mode board
```

Open it in Word, apply your letterhead/branding, and rearrange freely — the tags work anywhere,
including headers, footers, and table cells.

**3. Generate**

```bash
# one document for one item, as PDF, filed back onto the item
.venv/bin/python docugen.py generate --item 987654321 \
    --template templates/quote.docx \
    --out 'out/Quote - {{ c.client_name }}.docx' --pdf --upload-column files

# one combined report across a board (or one group of it)
.venv/bin/python docugen.py generate --board 1234567890 --group "Q3" \
    --template templates/report.docx --out out/q3-report.docx --pdf

# batch: a separate document for every item on the board
.venv/bin/python docugen.py generate --board 1234567890 --per-item \
    --template templates/quote.docx --out 'out/{{ name }}.docx'
```

`--dry-run` skips rendering and prints the exact data your template will see as JSON — the
fastest way to find out what a column is actually named.

## Template syntax

Standard Jinja2 inside an ordinary Word document.

| Tag | Gives you |
|---|---|
| `{{ name }}` | item name |
| `{{ c.client_name }}` | column by title (lowercased, non-alphanumerics → `_`) |
| `{{ col.text5 }}` | column by monday column id — use this if two columns share a title |
| `{{ group }}` `{{ board }}` `{{ url }}` | item metadata |
| `{{ today_str }}` `{{ now }}` | generation date |
| `{{ subitems }}` | list of subitem contexts, each with its own `.name` / `.c.*` |
| `{{ items }}` | board mode: list of item contexts |

Filters and helpers:

```
{{ c.amount | money }}                      →  $12,500.50
{{ c.due_date | date('%B %-d, %Y') }}       →  September 30, 2026
{{ c.services | join_list }}                →  Design, Copywriting
{{ c.signed | yesno }}                      →  Yes
{{ total(items, 'amount') | money }}        →  sum of a column across items
```

Loops in tables use docxtpl's row tags. Put `{%tr for x in items %}` alone in one row, the
content in the next row, and `{%tr endfor %}` alone in a third — the two tag rows are consumed:

| |
|---|
| `{%tr for it in items %}` |
| `{{ it.name }}` · `{{ it.c.status }}` |
| `{%tr endfor %}` |

Missing columns render as empty rather than erroring, so one template can serve boards that
don't all have every field.

## Column handling

Values are coerced to usable Python types: numbers → int/float, dates → `date` objects (so
`| date()` works), checkboxes → booleans, dropdowns/tags → lists, people → names, mirror /
formula / connect-boards / dependency → their display value. `{{ raw.<column_id> }}` exposes
the untouched monday payload if you need something exotic.

## Running it automatically

DocuGen's "trigger on status change" equivalent, since a script can't receive monday
automations directly:

- **Polling** — a cron/launchd job that queries the board for items in a given status and
  generates for each. `--per-item` plus `--upload-column` makes that a one-liner.
- **Webhook** — point a monday webhook at a small endpoint that shells out to
  `generate --item <pulseId>`; the payload's `event.pulseId` is the item id.

## Running it for free on Google Apps Script (the live setup)

[`apps-script/`](apps-script/) is the one that actually replaced DocuGen. It needs no server
and no LibreOffice: Google Docs does the PDF conversion, and Google hosts the endpoint.
Submitting a request on the board files a PDF back on the item in **under 20 seconds**.

```
monday status -> Submitted
   -> webhook POST -> doPost()  -> copy template Doc -> fill -> export PDF
   -> add_file_to_column -> "PDF of Request"
```

`pollBoard()` does the same sweep on a timer and exists only as a backstop for a webhook
monday failed to deliver; the webhook is the live path.

**Deploy with clasp, never by pasting.** A clipboard paste once overwrote the whole file
with unrelated text, and a paste of non-ASCII mangles the glottal in *Hawaiʻi*.

```bash
cd apps-script && npx clasp push
npx clasp deploy -i <DEPLOYMENT_ID>      # NOT a bare `clasp deploy`
```

The webhook points at a **versioned** deployment, which is a frozen snapshot: `clasp push`
alone updates the editor but leaves the live endpoint running the old code. Always redeploy
to the same id, which also keeps the registered webhook URL valid.

`clasp run` does not work here — it needs the `drive`/`documents` scopes, which Workspace
policy refuses for unverified apps. So nothing may depend on a human running a function by
hand: `setupTemplate()` is invoked automatically when `TEMPLATE_VERSION` in `Code.js` no
longer matches the stamp stored in Script Properties. **Bump that constant whenever you
change the template layout**, or the old template Doc keeps rendering the old design no
matter what the code says.

Configuration lives in Script Properties (see `CONFIG_KEYS`): `MONDAY_TOKEN`, `BOARD_ID`,
`PDF_COLUMN_ID`, `STATUS_COLUMN_ID`, `READY_STATUS`, and `WEBHOOK_SECRET` — the shared
secret in the webhook URL's `?key=`. The endpoint must be `ANYONE_ANONYMOUS` because monday
calls it unauthenticated, so it verifies the secret, pins the board id, ignores any status
other than `READY_STATUS`, and skips items that already have a PDF. Without those last two
guards a single submission produces duplicate PDFs, because the hook fires on *every* change
to the watched column and monday may redeliver an event.

```bash
node apps-script/tests_node_harness.js     # logic tests, no Google or monday needed
```

## Tests

`tests_selftest.py` exercises coercion, rendering, filters, loops, and output-path templating
against mock payloads — no API token or network needed.

```bash
.venv/bin/python tests_selftest.py
```

## Running it inside monday

[`monday-app/`](monday-app/README.md) wraps this engine in a real monday app: a custom
action the automation engine calls, plus an item view with a Generate button. Same
rendering code, plus JWT verification and a job queue.

## What it doesn't do

- The CLI itself has no in-monday UI — see `monday-app/` for that.
- Google Docs / Slides output isn't implemented; .docx (and PDF via conversion) only.
