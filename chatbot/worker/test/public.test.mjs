import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleChat } from "../src/handler.js";

const full = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
// What a --public build ships before any ready-made answer is approved: the same index with no faq entries.
const publicIndex = { ...full, faq: [] };
const spy = () => { const seen = []; return { seen, messages: { create: async (p) => { seen.push(p); return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "From the model. [C1]" }] }; } } }; };
const ask = (q, index, client) => handleChat({ messages: [{ role: "user", content: q }], index, client, env: {} });

test("public: with no ready-made answer approved, those questions go to the model instead of failing", async () => {
  for (const q of ["What is your mission?", "Hello", "Thanks!", "How do I contact you?"]) {
    const draft = await ask(q, full, spy());
    assert.ok(draft.body.flags.canned, `${q}: answered ready-made in the pilot`);
    const c = spy();
    const r = await ask(q, publicIndex, c);
    assert.equal(r.status, 200, q);
    assert.equal(c.seen.length, 1, `${q}: the model is asked`);
    assert.equal(r.body.flags.canned, undefined);
  }
});

test("public: the no-position reply being unapproved sends a deferral to the model, and everything else keeps working", async () => {
  const c = spy();
  const r = await ask("What is your position on cryptocurrency?", publicIndex, c);
  assert.equal(r.status, 200);
  assert.equal(c.seen.length, 1);
  assert.equal(r.body.flags.canned, undefined);
  const never = { messages: { create: async () => assert.fail("not for this one") } };
  assert.equal((await ask("I need a lawyer for my eviction", publicIndex, never)).body.flags.legal, true, "the legal gate needs no ready-made answer");
  assert.equal((await ask("What's your stance on the conveyance tax?", publicIndex, never)).body.flags.canned, "stance", "a stated position needs none either");
});
