// Local stand-in for the Worker: same handler, plain Node.
//   node dev-server.mjs                real model (needs ANTHROPIC_API_KEY or ~/.anthropic_api_key)
//   node dev-server.mjs --mock         no model call: answers from the top excerpt, for UI work
import { existsSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { homedir } from "node:os";
import Anthropic from "@anthropic-ai/sdk";
import { handleRequest } from "./src/index.js";

const PORT = Number(process.env.PORT ?? 8791);
// An in-memory stand-in for the Worker's KV store, so rate limits, the budget, and feedback work locally.
const memoryKv = () => {
  const m = new Map();
  return { m, get: async (k) => m.get(k) ?? null, put: async (k, v) => void m.set(k, v),
    list: async ({ prefix = "" } = {}) => ({ keys: [...m.keys()].filter((k) => k.startsWith(prefix)).sort().map((name) => ({ name })), list_complete: true }) };
};
const env = {
  RATE: memoryKv(), FEEDBACK: "1", PER_MINUTE: "100", PER_DAY: "1000", DAILY_CAP: "5000", DAILY_BUDGET_USD: "50",
  ALLOWED_ORIGINS: process.env.ALLOWED_ORIGINS ?? "http://localhost:8742,http://127.0.0.1:8742,http://localhost:8790",
  MODEL: process.env.MODEL,
  EFFORT: process.env.EFFORT,
};

let client;
if (process.env.MOCK_LLM || process.argv.includes("--mock")) {
  // Quotes the best excerpt back with its citation marker so retrieval, citations, and the UI can be seen working.
  client = {
    messages: {
      async create(params) {
        const ex = params.system[1].text;
        const m = ex.match(/\[1\] (.+?) \(.*?\)\n([\s\S]+?)(?:\n\n\[2\]|$)/);
        const text = m
          ? `This is a mock answer (no model was called). The closest passage is "${m[1]}": ${m[2].split(/(?<=[.!?])\s/)[0]} [1]`
          : "This is a mock answer (no model was called), and no passage matched.";
        return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text }] };
      },
    },
  };
  console.log("MOCK_LLM on: no model calls are made.");
} else {
  env.ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY ??
    (existsSync(`${homedir()}/.anthropic_api_key`) ? readFileSync(`${homedir()}/.anthropic_api_key`, "utf8").trim() : undefined);
  if (!env.ANTHROPIC_API_KEY) {
    console.error("No API key. Put one in ~/.anthropic_api_key, or run with --mock.");
    process.exit(1);
  }
  client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
}

createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = chunks.length ? Buffer.concat(chunks) : undefined;
  const request = new Request(`http://localhost:${PORT}${req.url}`, {
    method: req.method,
    headers: req.headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : body,
  });
  // Any localhost origin is fine in dev; the static server's port is assigned at launch.
  const origin = req.headers.origin ?? "";
  const reqEnv = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin) ? { ...env, ALLOWED_ORIGINS: origin } : env;
  const response = await handleRequest(request, reqEnv, { client });
  res.writeHead(response.status, Object.fromEntries(response.headers));
  res.end(Buffer.from(await response.arrayBuffer()));
}).listen(PORT, () => console.log(`ask worker on http://localhost:${PORT}  (allowed origins: ${env.ALLOWED_ORIGINS})`));
