import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleChat } from "../src/handler.js";
import { graphicFor, graphicMenu, pickGraphics, publicGraphic, takeMarkers } from "../src/graphics.js";
import { buildSystem } from "../src/prompt.js";

const index = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
const never = { messages: { create: async () => assert.fail("the model must not run for this question") } };
const says = (text) => ({ messages: { create: async () => ({ stop_reason: "end_turn", content: [{ type: "text", text }], usage: {} }) } });
const ask = (q, client = never, env = {}) => handleChat({ messages: [{ role: "user", content: q }], index, client, env });
const ids = (r) => r.body.graphics.map((g) => g.id);

test("graphics: the library is built into the index and nothing but plain data is sent to the page", () => {
  assert.ok(index.graphics.length >= 10);
  for (const g of index.graphics) {
    const p = publicGraphic(g);
    assert.deepEqual(Object.keys(p).filter((k) => ["aliases", "auto", "proof", "proofs"].includes(k)), [], g.id);
    assert.ok(p.title && p.source?.url?.startsWith("https://hiappleseed.org/"), g.id);
    assert.ok(JSON.stringify(p).length < 3000, `${g.id} is small`);
    assert.doesNotMatch(JSON.stringify(p), /<|>|javascript:/i, `${g.id} carries no markup`);
  }
});

test("graphics: a question names a graphic through its aliases, and asking for a picture is what lets most of them show", () => {
  const f = (q) => graphicFor(index, q)?.id ?? null;
  assert.equal(f("Show me a chart of the empty homes tax revenue"), "eht-revenue");
  assert.equal(f("Can you explain how marginal rates work?"), "marginal-illustration");
  assert.equal(f("Make a graphic of the capital gains rate vs ordinary income"), "capital-gains-rates");
  assert.equal(f("Visualize the school meals income cliff"), "school-meals-cliff");
  assert.equal(f("Which bills passed in 2026?"), "session-2026-scoreboard"); // auto: the topic itself
  assert.equal(f("What is the capital gains rate?"), null); // no ask for a picture, and not an auto graphic
  assert.equal(f("Show me a timeline of the conveyance tax"), null); // "timeline" alone is not Appleseed's history
  assert.equal(f("Show me a chart of the cost of living"), null);
  assert.equal(f("Show me a chart"), null);
});

test("graphics: a stated position and a ready-made answer bring their graphic with them, without the model", async () => {
  let r = await ask("What's your stance on the conveyance tax?");
  assert.equal(r.body.flags.canned, "stance");
  assert.deepEqual(ids(r), ["conveyance-allocation"]);
  r = await ask("What is Hawaiʻi Appleseed's position on the empty homes tax?");
  assert.deepEqual(ids(r), ["eht-revenue"]);
  r = await ask("When was Hawaii Appleseed founded?");
  assert.deepEqual(ids(r), ["appleseed-history"]);
  r = await ask("What is your mission?");
  assert.deepEqual(r.body.graphics, []);
});

test("graphics: the model's marker is stripped, checked against the library, and kept only when the answer shares its figures", async () => {
  const text = (m) => `Hawaiʻi taxes capital gains at 7.25 percent versus 11 percent for ordinary income. [C1]\n${m}`;
  let r = await ask("How are capital gains taxed in Hawaii?", says(text("[[graphic: capital-gains-rates]]")));
  assert.deepEqual(ids(r), ["capital-gains-rates"]);
  assert.doesNotMatch(r.body.answer, /graphic|\[\[/);
  r = await ask("How are capital gains taxed in Hawaii?", says(text("[[graphic: not-a-real-one]]")));
  assert.deepEqual(r.body.graphics, []);
  assert.doesNotMatch(r.body.answer, /graphic|\[\[/);
  r = await ask("How are capital gains taxed in Hawaii?", says(text("[[graphic: eht-revenue]]"))); // real, but its figures are not in this answer
  assert.deepEqual(r.body.graphics, []);
  r = await ask("How are capital gains taxed in Hawaii?", says(text("[[graphic: capital-gains-rates")));
  assert.doesNotMatch(r.body.answer, /graphic|\[\[/);
  assert.deepEqual(r.body.graphics, []);
});

test("graphics: at most two, no repeats, and a graphic the visitor asked for comes before one the model added", () => {
  const answer = "7.25 percent and 11 percent; $183.4 million; $305.67 million; 66 percent; 1.5 percent";
  const out = pickGraphics(index, { question: "Show me a chart of the empty homes tax revenue", marked: ["capital-gains-rates", "transit-budget", "eht-revenue"], answer });
  assert.deepEqual(out.map((g) => g.id), ["eht-revenue", "capital-gains-rates"]);
  assert.deepEqual(takeMarkers("a [[graphic: eht-revenue]] b [[graphic: eht-revenue]]", index), { text: "a  b", ids: ["eht-revenue"] });
});

test("graphics: the model is shown the menu, in the cached block, and told it never draws", () => {
  const sys = buildSystem(index.core, index.graphics);
  assert.match(sys, /# GRAPHICS AVAILABLE/);
  for (const g of index.graphics) assert.ok(sys.includes(`- ${g.id}: `), g.id);
  assert.match(graphicMenu(index.graphics), /marginal-illustration: .*made-up illustration/);
  assert.equal(buildSystem(index.core, index.graphics), buildSystem(index.core, index.graphics)); // byte-identical, so it caches
});

test("graphics: legal-help and refusal replies carry none", async () => {
  const r = await ask("Can you give me legal advice about my eviction? Show me a chart.");
  assert.equal(r.body.flags.legal, true);
  assert.ok(!r.body.graphics?.length);
});
