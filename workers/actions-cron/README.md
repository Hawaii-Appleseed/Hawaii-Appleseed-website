# ha-actions-cron

A Cloudflare Worker that runs on Cloudflare Cron Triggers and starts this repo's
GitHub Actions workflows through `workflow_dispatch`.

**Why it exists.** GitHub drops most scheduled triggers in this repo.
`fetch-bill-status.yml` asks for a run every 30 minutes, but in October 2026
it ran only 4-6 times a day, with gaps of up to 641 minutes. Bill status has to
be fresh during the legislative session, so an outside clock now starts the
runs. Each workflow keeps its own `schedule:` as a backup.

| Cron (UTC)     | Workflow                |
|----------------|-------------------------|
| `*/30 * * * *` | `fetch-bill-status.yml` |
| `20 * * * *`   | `canary.yml`            |

Two runs that start close together are safe. `fetch-bill-status.yml` has a
`concurrency` group that queues the second run, and its commit step rebases
before it pushes. `canary.yml` has a concurrency group too.

## Setup (one time)

1. Create a **fine-grained** GitHub token (GitHub → Settings → Developer
   settings → Fine-grained tokens):
   - Resource owner: `Hawaii-Appleseed`
   - Repository access: only `Hawaii-Appleseed/Hawaii-Appleseed-website`
   - Repository permissions: **Actions: Read and write** (Metadata: read is
     added automatically). Nothing else.
   - Expiry: the longest the org allows. Set a reminder to rotate it.
2. Store it as the Worker's secret. From this folder, run:
   ```bash
   npx wrangler secret put GITHUB_TOKEN
   ```
3. Deploy with `npx wrangler deploy`.

## Checking it

- Cloudflare dashboard → Workers → `ha-actions-cron` → Logs / Cron Events.
  A run that fails throws an error that contains GitHub's HTTP status.
- `gh api 'repos/Hawaii-Appleseed/Hawaii-Appleseed-website/actions/workflows/fetch-bill-status.yml/runs?per_page=50' -q '.workflow_runs[] | [.created_at, .event] | @tsv'`
  The Worker's runs show `workflow_dispatch`. GitHub's own runs show `schedule`.

If the token expires or the Worker stops, runs fall back to GitHub's own
schedule, and `canary.yml` alerts once `fetch-bill-status.yml` has had no run
for longer than its limit.
