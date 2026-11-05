// Cloudflare Cron Trigger -> GitHub workflow_dispatch.
// See ../README.md for why this exists and how to set it up.

const REPO = "Hawaii-Appleseed/Hawaii-Appleseed-website";
const REF = "main";

// Cron expression (exactly as written in wrangler.toml) -> workflow files to dispatch.
const SCHEDULE = {
  "*/30 * * * *": ["fetch-bill-status.yml"],
  "20 * * * *": ["canary.yml"],
};

async function dispatch(workflow, token) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ha-actions-cron",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: REF }),
    },
  );
  if (res.status !== 204) {
    const body = (await res.text()).slice(0, 300);
    throw new Error(`${workflow}: HTTP ${res.status} ${body}`);
  }
  console.log(`${workflow}: dispatched`);
}

export default {
  async scheduled(event, env, ctx) {
    const workflows = SCHEDULE[event.cron];
    if (!workflows) throw new Error(`no workflow mapped to cron "${event.cron}"`);
    if (!env.GITHUB_TOKEN) throw new Error("GITHUB_TOKEN secret is not set");
    const results = await Promise.allSettled(workflows.map((w) => dispatch(w, env.GITHUB_TOKEN)));
    const failed = results.filter((r) => r.status === "rejected");
    // Throwing marks the invocation as failed in the Worker's Cron Events log.
    if (failed.length) throw new Error(failed.map((r) => r.reason.message).join("; "));
  },
};
