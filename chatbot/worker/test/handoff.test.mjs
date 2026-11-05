import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handleChat } from "../src/handler.js";
import { handoffFor, peopleFor, takeStaffMarker } from "../src/handoff.js";

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
  assert.deepEqual(takeStaffMarker("I don't have that. [C3]\n[[staff]]"), { text: "I don't have that. [C3]", asked: true, ids: [] });
  assert.deepEqual(takeStaffMarker("Text [[ Staff ]] more"), { text: "Text  more", asked: true, ids: [] });
  assert.deepEqual(takeStaffMarker("Text\n[[staff"), { text: "Text", asked: true, ids: [] });
  assert.deepEqual(takeStaffMarker("A full answer."), { text: "A full answer.", asked: false, ids: [] });
  assert.deepEqual(takeStaffMarker("Ask them. [[staff: Arjuna-Heim , kamakani-albano]]"), { text: "Ask them.", asked: true, ids: ["arjuna-heim", "kamakani-albano"] });
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

test("handoff: the people the model names are checked against the staff list, at most two, and an unknown name names no one", async () => {
  assert.equal(index.staff.people.length, 12);
  assert.deepEqual(peopleFor(index, ["arjuna-heim", "nobody-here", "kamakani-albano", "devin-thomas"]).map((p) => p.id), ["arjuna-heim", "kamakani-albano"]);
  const p = peopleFor(index, ["devin-thomas"])[0];
  assert.deepEqual(Object.keys(p).sort(), ["email", "id", "name", "title"]);
  assert.match(p.email, /^[\w.+-]+@hiappleseed\.org$/);
  assert.deepEqual(peopleFor({ ...index, staff: null }, ["devin-thomas"]), [], "a public build before the routing is approved names no one");
  assert.deepEqual(handoffFor(index, { asked: true, ids: ["abbey-seitz"] }).people.map((x) => x.name), ["Abbey Seitz"]);
  assert.equal(handoffFor(index, { asked: true, ids: ["invented"] }).people, undefined, "still the office, with no made-up person");
  assert.equal(handoffFor(index, { asked: true, ids: ["abbey-seitz"], legal: true }), null);
});

test("handoff: a model answer that names who to talk to gets an email for each, and the handler strips the marker", async () => {
  const text = "For housing policy, Arjuna Heim directs research and housing policy, and Kamakani Albano is the housing policy analyst. [C1]\n[[staff: arjuna-heim, kamakani-albano, will-white]]";
  let r = await ask("Who's the best person to talk to about renters' rights?", says(text));
  assert.deepEqual(r.body.handoff.people.map((x) => x.id), ["arjuna-heim", "kamakani-albano"]);
  assert.doesNotMatch(r.body.answer, /\[\[|staff:/);
  assert.equal(r.body.handoff.email, index.contact.email, "the office is still offered");
  r = await ask("Who should I ask?", says("Ask the office. [[staff: not-a-person]]"));
  assert.equal(r.body.handoff.people, undefined);
  assert.ok(r.body.handoff);
});
