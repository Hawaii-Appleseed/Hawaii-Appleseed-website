import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleChat } from "../src/handler.js";
import { resolveStance, stanceTopic } from "../src/stance.js";

const index = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
const kind = (q) => { const r = resolveStance(index, q); return r ? (r.kind === "position" ? `position:${r.section.title}` : r.kind) : null; };
const never = { messages: { create: async () => assert.fail("the model must not run for this question") } };
const ask = (q, client = never, env = {}) => handleChat({ messages: [{ role: "user", content: q }], index, client, env });

test("stance: each question about a position we hold finds that position", () => {
  const cases = {
    "What's your stance on the conveyance tax?": "Conveyance tax modernization",
    "What is Hawaiʻi Appleseed's position on the empty homes tax?": "Empty homes tax (Honolulu)",
    "Do you support the empty homes tax?": "Empty homes tax (Honolulu)",
    "What is your position on rent control?": "Rent control and rental vouchers", // our 2026 blog argues vouchers over rent control
    "What is your stance on vaping?": "Tobacco and vaping taxes",
    "What's your opinion on taxing vacant homes?": "Empty homes tax (Honolulu)", // our report says "empty"; visitors say "vacant"
    "Where does Appleseed stand on capital gains?": "Capital gains tax",
    "Do you support the millionaire's tax?": "Millionaire's income surcharge",
    "Do you oppose estate tax breaks?": "Estate tax breaks",
    "What is your position on the estate tax?": "Estate tax breaks",
    "Is Hawaiʻi Appleseed for or against jaywalking laws?": "Decriminalizing jaywalking",
    "Do you support decriminalizing jaywalking?": "Decriminalizing jaywalking",
    "What is your position on parking maximums?": "Parking mandates",
    "Do you support a child tax credit?": "Keiki Credit (state child tax credit)",
    "Where does Appleseed stand on indexing the minimum wage?": "Minimum wage",
    "What is your position on just cause eviction?": "Renter protections",
    "How does Appleseed feel about SNAP?": "SNAP access",
    "Do you support free school meals?": "Universal free school meals",
    "What is your stance on Keiki Ride Free?": "Transit equity and fare-free transit",
    "What is your stance on paid family leave?": "Paid family and medical leave",
    "Do you support taxing REITs?": "Taxing real estate investment trusts (REITs)",
    "Where does Appleseed stand on medical debt?": "Medical debt forgiveness",
    "What is your view on freezing Act 46?": "Freezing and adjusting Act 46",
    "Do you support unarmed traffic enforcement?": "Traffic enforcement",
    "Why does Appleseed support the conveyance tax?": "Conveyance tax modernization", // a "why" gets the position, which includes the reasons
  };
  const wrong = Object.entries(cases).filter(([q, t]) => kind(q) !== `position:${t}`).map(([q, t]) => `${q} -> ${kind(q)} (wanted ${t})`);
  assert.deepEqual(wrong, []);
});

test("stance: a topic whose words our work never uses is deferred on, and a near-typo of a word we do use is not", () => {
  for (const q of ["What is your position on cryptocurrency?", "Where does Appleseed stand on the legalization of marijuana?", "Do you support a ban on plastic straws?", "Where do you stand on the Thirty Meter Telescope?", "Where does Appleseed stand on cryptocurrency taxes?"]) assert.equal(kind(q), "defer", q);
});

test("stance: topics our work only touches go to the model; other questions are not stance questions at all", () => {
  for (const q of [
    "Do you support a wealth tax?", "Where does Appleseed stand on the Honolulu rail project?", "Do you oppose the gas tax?",
    "What is Hawaiʻi Appleseed's position on charter schools?", // the school meals text mentions charter schools in passing; that must not make it the answer
    "What is your position on the conveyence tax?", // a typo is not an absent topic
    "Do you support the death penalty?", "Do you support school vouchers?",
  ]) assert.equal(kind(q), "excerpts", q);
  for (const q of [
    "What's your stance on the conveyance tax and what happened in 2026?", // two questions in one
    "What is the Governor's position on the conveyance tax?", // someone else's position
    "Do you support taxes?", // too general
    "What is your position?", "What is the conveyance tax?", "Hello",
  ]) assert.equal(kind(q), null, q);
  assert.equal(stanceTopic("What's your stance on the conveyance tax and what happened in 2026?"), null);
});

test("stance: a position is answered at once with its own words, source, and reports, never calling the model", async () => {
  const r = await ask("What's your stance on the conveyance tax?");
  assert.equal(r.status, 200);
  assert.equal(r.body.flags.canned, "stance");
  assert.match(r.body.answer, /marginal-rate conveyance tax/);
  assert.match(r.body.answer, / \[1\]$/);
  assert.equal(r.body.sources[0].url, "https://hiappleseed.org/taxes-budget");
  assert.ok(r.body.related.some((x) => x.url.endsWith("/preserving-hawaii")));
  const eht = await ask("What is your position on the empty homes tax?");
  assert.match(eht.body.answer, /3 to 5 percent/);
  assert.match(eht.body.answer, /\$183\.4 million/);
  assert.ok(eht.body.related.some((x) => x.url.endsWith("/empty-homes-tax-honolulu")));
});

test("stance: deferral uses fixed words, points to the Issues page and the office, and never echoes the question", async () => {
  const r = await ask("What is your position on the <b>cryptocurrency</b> ban?");
  assert.equal(r.body.flags.canned, "no-position");
  assert.doesNotMatch(r.body.answer, /cryptocurrency|<b>|ban\b/i);
  assert.match(r.body.answer, /has not published a position/);
  assert.match(r.body.answer, /\(808\) 587-7605/);
  assert.deepEqual(r.body.sources.map((s) => s.url), ["https://hiappleseed.org/issues", "https://hiappleseed.org/contact"]);
  const other = await ask("Where does Appleseed stand on the legalization of marijuana?");
  assert.equal(other.body.answer, r.body.answer); // the same words every time
});

test("stance: a compound question is never deferred on, and goes to the model", async () => {
  let seen;
  const client = { messages: { create: async (p) => { seen = p; return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok" }] }; } } };
  const r = await ask("What's your stance on the conveyance tax and what happened in 2026?", client);
  assert.equal(r.body.answer, "ok");
  assert.ok(seen);
});

test("stance: a topic the work only touches reaches the model with the stance rule; CANNED=off sends everything there", async () => {
  let seen;
  const client = { messages: { create: async (p) => { seen = p; return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok" }] }; } } };
  await ask("Do you support a wealth tax?", client);
  assert.match(seen.system[1].text, /no position in KNOWLEDGE names/);
  assert.match(seen.system[0].text, /A passing mention, another organization's view, or a description of a debate is not a position/);
  seen = null;
  await ask("What's your stance on the conveyance tax?", client, { CANNED: "off" });
  assert.ok(seen, "CANNED=off must reach the model");
});

test("stance: the legal gate and the ready-made phrasings still come first", async () => {
  assert.equal((await ask("I need a lawyer to sue my landlord")).body.flags.legal, true);
  assert.equal((await ask("What is your mission?")).body.flags.canned, "mission");
});
