// How one refresh run's fetch results are folded into the bill-status.json already on disk.
//
// Why this exists: capitol.hawaii.gov sometimes refuses the fetch (HTTP 403 from GitHub's runners). The first version wrote
// whatever the run got, so one bad run replaced good data with `{"error": "HTTP 403"}` for every bill, and every tracker
// on hitaxfairness.org showed a red "Error" badge until a later run happened to succeed (2026-10-21). Three rules:
//
//   1. A bill that fetched fine this run is taken as fetched.
//   2. A bill that failed keeps its last good entry (flagged `staleError`, and `staleSince` the first time it went stale),
//      so a bad run never turns good data into an error. It is only an error entry if there never was good data.
//   3. If EVERY fetch failed the run is not a data point at all: the caller leaves the file untouched and fails the job,
//      which is what triage.yml and canary.yml watch for.

/**
 * @param {Record<string, any>|undefined} previous  `bills` from the existing bill-status.json
 * @param {Record<string, any>} fresh               this run's results keyed like `previous`; an entry with `error` failed
 * @param {string} now                              ISO timestamp, for `staleSince`
 * @returns {{bills: Record<string, any>, ok: number, failed: string[], stale: string[], abort: boolean}}
 */
export function reconcile(previous, fresh, now) {
  const bills = {};
  const failed = [];
  const stale = [];
  for (const [key, entry] of Object.entries(fresh)) {
    if (!entry.error) {
      bills[key] = entry;
      continue;
    }
    failed.push(`${key} (${entry.error})`);
    const prior = previous?.[key];
    if (prior && Array.isArray(prior.updates) && prior.updates.length) {
      bills[key] = { ...prior, staleError: entry.error, staleSince: prior.staleSince ?? now };
      stale.push(key);
    } else {
      bills[key] = entry;
    }
  }
  const total = Object.keys(fresh).length;
  const ok = total - failed.length;
  return { bills, ok, failed, stale, abort: total > 0 && ok === 0 };
}
