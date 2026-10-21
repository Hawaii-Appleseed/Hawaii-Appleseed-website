import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { matchCanned } from "../src/canned.js";
import { handleChat } from "../src/handler.js";

const here = new URL(".", import.meta.url);
const index = JSON.parse(readFileSync(new URL("../src/index.json", here), "utf8"));
const sets = JSON.parse(readFileSync(new URL("../../eval/canned_sets.json", here), "utf8"));
const ask = (q) => matchCanned(index, [{ role: "user", content: q }])?.id ?? null;

test("canned: no question that belongs to the model ever gets a ready-made answer", () => {
  const wrong = sets.negatives.filter((q) => ask(q) !== null).map((q) => `${q} -> ${ask(q)}`);
  assert.deepEqual(wrong, []);
});

test("canned: the recorded phrasings find their answers", () => {
  const miss = sets.positives.filter(([id, q]) => ask(q) !== id).map(([id, q]) => `${q} -> ${ask(q)} (wanted ${id})`);
  assert.ok(miss.length <= Math.ceil(sets.positives.length * 0.05), `${miss.length} of ${sets.positives.length} missed:\n${miss.join("\n")}`);
});

test("canned: style differences do not matter, extra or missing topic words do", () => {
  for (const q of ["What is your mission?", "what's your MISSION", "What is the mission of Hawaiʻi Appleseed?", "  what  is your mission  "]) assert.equal(ask(q), "mission", q);
  for (const q of ["What is your mission regarding housing?", "What is your position?", "Hello, what is your mission?", "How do I contact my legislator about HB2049?", "Is Hawaiʻi Appleseed's executive director married?"]) assert.equal(ask(q), null, q);
  assert.equal(ask("who are you"), "ai"); // a phrasing with no topic words matches only itself
  assert.equal(ask("who is"), null);
});

test("canned: asking who is not asking what: 'who should I ask' goes to the model, not to 'what can I ask'", () => {
  for (const q of ["Who should I ask?", "Who's the best person to talk to?", "who can I ask about this", "Who can help me?"]) assert.equal(ask(q), null, q);
  assert.equal(ask("what can I ask"), "capabilities");
  assert.equal(ask("Who do I contact?"), "contact");
});

test("canned: greetings and thanks, however worded, but not stray words", () => {
  for (const q of ["Hi", "Aloha, good morning", "Hello there!", "Good evening"]) assert.equal(ask(q), "greeting", q);
  for (const q of ["Thanks!", "Thank you so much", "Thanks a ton", "Mahalo nui loa", "thanks that was helpful"]) assert.equal(ask(q), "thanks", q);
  for (const q of ["so", "ok", "there", "good", "much", "was"]) assert.equal(ask(q), null, q);
});

test("canned: the handler answers without a model call, with its sources, and the legal gate still wins", async () => {
  const client = { messages: { create: async () => assert.fail("a ready-made answer must not call the model") } };
  const r = await handleChat({ messages: [{ role: "user", content: "What is your mission?" }], index, client });
  assert.equal(r.status, 200);
  assert.equal(r.body.flags.canned, "mission");
  assert.match(r.body.answer, /economic justice/);
  assert.equal(r.body.sources[0].url, "https://hiappleseed.org/our-mission");
  assert.equal(r.usage, undefined); // costs nothing
  const legal = await handleChat({ messages: [{ role: "user", content: "I need a lawyer" }], index, client });
  assert.equal(legal.body.flags.legal, true);
  // CANNED=off sends everything to the model (for comparing answers)
  let called = false;
  await handleChat({ messages: [{ role: "user", content: "What is your mission?" }], index, env: { CANNED: "off" }, client: { messages: { create: async () => { called = true; return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok" }] }; } } } });
  assert.equal(called, true);
});

test("canned: every answer cites only its own sources, uses its markers, and names a real page", () => {
  for (const e of index.faq) {
    const used = [...e.answer.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1]));
    assert.deepEqual([...new Set(used)].sort(), e.sources.map((s) => s.n), e.id);
    for (const s of e.sources) assert.match(s.url, /^https:\/\//, e.id);
  }
  assert.ok(index.faq.length >= 20);
});
