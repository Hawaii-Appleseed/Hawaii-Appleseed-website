import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleChat } from "../src/handler.js";
import { handoffFor, takeStaffMarker } from "../src/handoff.js";

const index = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
const never = { messages: { create: async () => assert.fail("the model must not run for this question") } };
const says = (text) => ({ messages: { create: async () => ({ stop_reason: "end_turn", content: [{ type: "text", text }], usage: {} }) } });
const ask = (q, client = never, env = {}) => handleChat({ messages: [{ role: "user", content: q }], index, client, env });

test("handoff: the contact details come from the Contact the office section, one source", () => {
  assert.deepEqual(Object.keys(index.contact).sort(), ["email", "page", "phone", "tel"]);
  assert.match(index.contact.email, /^[\w.+-]+@hiappleseed\.org$/);
  assert.match(index.contact.phone, /^\(\d{3}\) \d{3}-\d{4}$/);
  assert.equal(index.contact.tel, "+1" + index.contact.phone.replace(/\D/g, ""));
  assert.match(index.contact.page, /^https:\/\/hiappleseed\.org\/contact$/);
  const sec = index.core.find((c) => c.title === "Contact the office");
  assert.ok(sec.text.includes(index.contact.email) && sec.text.includes(index.contact.phone));
});

test("handoff: the [[staff]] marker is taken out wherever it sits, and a half-typed one too", () => {
  assert.deepEqual(takeStaffMarker("I don't have that. [C3]\n[[staff]]"), { text: "I don't have that. [C3]", asked: true });
  assert.deepEqual(takeStaffMarker("Text [[ Staff ]] more"), { text: "Text  more", asked: true });
  assert.deepEqual(takeStaffMarker("Text\n[[staff"), { text: "Text", asked: true });
  assert.deepEqual(takeStaffMarker("A full answer."), { text: "A full answer.", asked: false });
});

test("handoff: offered when the model asks, when the answer plainly has nothing, and on the fixed no-position reply; never on legal help", () => {
  const h = (o) => handoffFor(index, o);
  assert.deepEqual(h({ asked: true, answer: "x" }), index.contact);
  assert.ok(h({ answer: "I don't have that information in the material I have. The office can say." }));
  assert.ok(h({ answer: "Hawaiʻi Appleseed has no stated position on that in the material I have." }));
  assert.ok(h({ answer: "I can’t confirm the final status of that bill." }), "curly apostrophes count");
  assert.ok(h({ cannedId: "no-position" }));
  assert.equal(h({ answer: "Hawaiʻi Appleseed supports a state paid family leave program. [C1]" }), null);
  assert.equal(h({ cannedId: "contact" }), null, "a ready-made answer is not a dead end");
  assert.equal(h({ asked: true, legal: true }), null);
  assert.equal(handoffFor({}, { asked: true }), null, "no contact block, no button");
});

test("handoff: the handler offers it on the deferral, strips the marker, and never on a position, a ready-made answer or legal help", async () => {
  let r = await ask("What is your position on cryptocurrency?");
  assert.equal(r.body.flags.canned, "no-position");
  assert.deepEqual(r.body.handoff, index.contact);
  r = await ask("What's your stance on the conveyance tax?");
  assert.equal(r.body.handoff, null);
  r = await ask("What is your mission?");
  assert.equal(r.body.handoff, null);
  r = await ask("I need a lawyer for my eviction");
  assert.equal(r.body.handoff, null);
  r = await ask("Is the office open on Saturdays?", says("Office hours are not listed on the website, so I can't say. The office can tell you [C1].\n[[staff]]"));
  assert.deepEqual(r.body.handoff, index.contact);
  assert.doesNotMatch(r.body.answer, /staff\]\]|\[\[/);
  r = await ask("What is the conveyance tax?", says("The conveyance tax is paid when property changes hands. [C1]"));
  assert.equal(r.body.handoff, null);
});
