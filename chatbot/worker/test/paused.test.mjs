import assert from "node:assert/strict";
import { test } from "node:test";
import { handleRequest } from "../src/index.js";

const MSG = "The assistant is disabled for now. <b>Back soon</b> & thanks.";
const noModel = { client: { messages: { create: async () => assert.fail("model must not run while paused") } } };
const chat = (env) =>
  handleRequest(
    new Request("https://worker.test/chat", {
      method: "POST",
      headers: { origin: "https://hiappleseed.org", "content-type": "application/json", "cf-connecting-ip": "203.0.113.9" },
      body: JSON.stringify({ messages: [{ role: "user", content: "What is the Budget Primer?" }] }),
    }),
    env,
    noModel,
  );

test("paused: /chat answers 503 with the message, before any model call or rate-limit work", async () => {
  const kv = { get: async () => assert.fail("no KV work while paused"), put: async () => assert.fail("no KV work while paused") };
  const r = await chat({ PAUSED: MSG, RATE: kv });
  assert.equal(r.status, 503);
  const b = await r.json();
  assert.equal(b.error, "paused");
  assert.equal(b.answer, MSG);
});

test("paused: the page shows the notice (escaped) and hides the chat box", async () => {
  const r = await handleRequest(new Request("https://worker.test/"), { PAUSED: MSG }, noModel);
  const html = await r.text();
  assert.equal(r.status, 200);
  assert.match(html, /class="ha-ask__notice" role="status">The assistant is disabled for now\. &lt;b&gt;Back soon&lt;\/b&gt; &amp; thanks\./);
  assert.match(html, /\.ha-ask__panel[^}]*display: none/);
  assert.equal(html.includes("<b>Back soon</b>"), false);
});

test("paused: empty or unset means the assistant is on and the page is untouched", async () => {
  for (const env of [{}, { PAUSED: "" }, { PAUSED: "   " }]) {
    const html = await (await handleRequest(new Request("https://worker.test/"), env, noModel)).text();
    assert.equal(html.includes("display: none !important; }</style>"), false);
    assert.ok(html.includes("ha-ask__panel"));
  }
  const ok = { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok" }] };
  const r = await handleRequest(new Request("https://worker.test/chat", { method: "POST", headers: { origin: "https://hiappleseed.org", "content-type": "application/json" }, body: JSON.stringify({ messages: [{ role: "user", content: "What is the Budget Primer?" }] }) }), { PAUSED: "" }, { client: { messages: { create: async () => ok } } });
  assert.equal(r.status, 200);
});
