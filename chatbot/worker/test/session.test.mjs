import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleChat, newerSession } from "../src/handler.js";
import { buildExcerpts, buildSystem } from "../src/prompt.js";

const index = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
const asks = (q, today, client) => handleChat({ messages: [{ role: "user", content: q }], index, client, env: {}, today });
const spy = () => { const seen = []; return { seen, messages: { create: async (p) => { seen.push(p); return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok [C1]" }] }; } } }; };

test("session: the content says which session it covers, and the generated bill section follows it", () => {
  assert.equal(index.session.covered, 2026);
  assert.ok(index.core.some((c) => c.title === `${index.session.covered} bill outcomes`));
});

test("session: the switch flips at the new calendar year, not before", () => {
  assert.equal(newerSession(index, "2026-12-31"), null);
  assert.equal(newerSession(index, "2027-01-01"), 2026);
  assert.equal(newerSession(index, "2031-06-01"), 2026);
  assert.equal(newerSession({}, "2027-01-01"), null, "no session recorded, no notice");
});

test("session: a stated position carries a note once the calendar has moved past the session, and not before", async () => {
  const q = "What's your stance on the conveyance tax?";
  const before = await asks(q, "2026-11-15", spy());
  const after = await asks(q, "2027-02-01", spy());
  assert.doesNotMatch(before.body.answer, /legislative session/);
  assert.match(after.body.answer, /This reflects the 2026 legislative session\. The Legislature has met since, so check capitol\.hawaii\.gov/);
  assert.ok(after.body.answer.startsWith(before.body.answer.replace(/\s*$/, "")), "the position text itself is unchanged");
});

test("session: a model answer is told the material is from an earlier session, in the per-question block only", async () => {
  const c2026 = spy(), c2027 = spy();
  await asks("What happened to the school meals bill?", "2026-11-15", c2026);
  await asks("What happened to the school meals bill?", "2027-02-01", c2027);
  const [a, b] = [c2026.seen[0], c2027.seen[0]];
  assert.doesNotMatch(a.system[1].text, /SESSION NOTICE/);
  assert.match(b.system[1].text, /SESSION NOTICE: the material covers the 2026 legislative session only/);
  assert.equal(a.system[0].text, b.system[0].text, "the cached block does not change with the date");
});

test("session: the cached rules name the covered session and the one after it", () => {
  const sys = buildSystem(index.core, index.graphics, { covered: 2026 });
  assert.match(sys, /The newest session your material covers is 2026, and it has ended\./);
  assert.match(sys, /if it falls in 2027 or later/);
  const next = buildSystem(index.core, index.graphics, { covered: 2027 });
  assert.match(next, /covers is 2027/);
  assert.match(next, /falls in 2028 or later/);
  assert.doesNotMatch(buildExcerpts([], "2026-11-15", {}), /SESSION NOTICE/);
});
