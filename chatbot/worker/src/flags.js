// Answers staff flagged as wrong in the pilot: read back from the fb: entries handleFeedback saves (rating "down"),
// for the /flags review page. Kept 90 days by the entries' own expiry.

/** Flagged entries, newest first. KV lists keys in order and each key starts with its timestamp. */
export async function readFlags(kv, limit = 200) {
  const names = [];
  let cursor;
  do {
    const page = await kv.list({ prefix: "fb:", cursor });
    names.push(...page.keys.map((k) => k.name));
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor && names.length < 2000);
  names.sort().reverse();
  const got = await Promise.all(names.slice(0, limit * 3).map(async (key) => {
    try { const raw = await kv.get(key); return raw ? { key, ...JSON.parse(raw) } : null; } catch { return null; }
  }));
  return got.filter((e) => e?.rating === "down").slice(0, limit);
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const when = (ts) => {
  try { return new Date(ts).toLocaleString("en-US", { timeZone: "Pacific/Honolulu", dateStyle: "medium", timeStyle: "short" }) + " HST"; } catch { return ts; }
};
// A source is saved as "Title https://…" (older entries: just the URL); link the URL, keep the rest as text.
const source = (s) => {
  const m = /(https?:\/\/\S+)\s*$/.exec(s);
  if (!m) return esc(s);
  const label = s.slice(0, m.index).trim() || m[1];
  return `<a href="${esc(m[1])}" target="_blank" rel="noopener">${esc(label)}</a>`;
};

function one(e, i) {
  const earlier = (e.context ?? []).map((m) => `<p class="turn"><b>${m.role === "user" ? "Asked" : "Answered"}:</b> ${esc(m.content)}</p>`).join("");
  return `<article id="f${i + 1}">
<p class="m">${esc(when(e.ts))} · ${esc(e.email ?? "unknown")} · ${esc(e.model ?? "")}${e.built ? ` · content built ${esc(e.built)}` : ""}</p>
<p class="why">${e.comment ? esc(e.comment) : '<span class="m">No note left.</span>'}</p>
${earlier ? `<details><summary>Earlier in the conversation (${e.context.length})</summary>${earlier}</details>` : ""}
<p class="q"><b>Question:</b> ${esc(e.question)}</p>
<div class="a">${esc(e.answer)}</div>
${(e.sources ?? []).length ? `<p class="m"><b>Sources:</b> ${e.sources.map(source).join(" · ")}</p>` : ""}
</article>`;
}

/** The review page: one card per flagged answer. No scripts. */
export function flagsPage(flags) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Ask Hawaiʻi Appleseed: flagged answers</title><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@700;800&family=Poppins:wght@400;500&display=swap" rel="stylesheet">
<style>
 body{margin:0;background:#F4F7F4;color:#2F3E46;font:15px/1.55 Poppins,Arial,sans-serif}
 main{max-width:860px;margin:0 auto;padding:32px 20px 64px}
 h1{font:800 28px/1.2 Manrope,Arial,sans-serif;letter-spacing:-.01em;margin:0 0 6px}
 .eyebrow{font:700 11px Manrope,Arial,sans-serif;letter-spacing:.22em;text-transform:uppercase;color:#3F5F57;margin:0 0 6px}
 .m{color:rgba(47,62,70,.74);font-size:13px;margin:2px 0 8px}
 article{background:#fff;border:1px solid rgba(53,79,82,.14);border-left:4px solid #52796F;border-radius:6px;padding:14px 16px;margin-top:16px;overflow-wrap:anywhere}
 .why{font-weight:500;margin:4px 0 10px;padding:8px 10px;background:#E5E9E2;border-radius:4px}
 .q{margin:10px 0 6px} .a{white-space:pre-wrap;padding:10px 12px;border:1px solid rgba(53,79,82,.14);border-radius:4px;font-size:14px}
 details{margin:6px 0;font-size:14px} summary{cursor:pointer;color:#3F5F57;font-weight:500} .turn{margin:6px 0 6px 12px}
 a{color:#3F5F57}
</style></head><body><main>
<p class="eyebrow">Ask Hawaiʻi Appleseed</p><h1>Flagged answers</h1>
<p class="m">${flags.length} flagged, newest first. Each is kept 90 days. Staff emails and questions are on this page: do not share it. To turn one into a test case, run <code>node eval/pull_feedback.mjs --cases</code>. <a href="/stats">Usage</a></p>
${flags.length ? flags.map(one).join("\n") : '<p class="m">Nothing flagged yet.</p>'}
</main></body></html>`;
}
