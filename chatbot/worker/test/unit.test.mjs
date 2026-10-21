import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { cleanMessages, finalize, handleChat } from "../src/handler.js";
import { isLegalHelpRequest, LEGAL_REPLY } from "../src/legal.js";
import { queryFor, search } from "../src/retrieve.js";
import { tokenize } from "../src/tokenize.js";

const here = new URL(".", import.meta.url);
const vectors = JSON.parse(readFileSync(new URL("../../tokenizer_vectors.json", here), "utf8"));
const index = JSON.parse(readFileSync(new URL("../src/index.json", here), "utf8"));

test("tokenizer matches the Python build tokenizer on every shared vector", () => {
  for (const v of vectors) assert.deepEqual(tokenize(v.in), v.out, v.in);
});

test("legal gate: personal requests for legal help are refused", () => {
  for (const q of [
    "I'm being evicted, what are my rights?",
    "Can you represent me in court?",
    "I need a lawyer for my landlord dispute",
    "Can I sue my employer for unpaid wages?",
    "my landlord won't return my security deposit",
    "I got an eviction notice yesterday",
    "Can you give me legal advice?",
    "Do you offer free legal aid for tenants like me?",
    "how do I fight this eviction",
    "Should I appeal my SNAP denial? I need a lawyer",
    "I was fired last week and I think it was illegal, can you help with my case",
    "What are my legal options?",
  ]) assert.equal(isLegalHelpRequest(q), true, q);
});

test("legal gate: policy questions about legal topics still go to the model", () => {
  for (const q of [
    "Does Hawaiʻi Appleseed support a right to legal counsel for tenants in eviction?",
    "What is Appleseed's position on just-cause eviction?",
    "Do you support funding for legal aid?",
    "What did the Legislature do on tenant protections in 2026?",
    "Tell me about the lawsuit over Front Street in Lahaina",
    "Who founded Lawyers for Equal Justice?",
    "What does HB1776 do?",
    "How do you research eviction trends?",
    "Where is your office?",
    "How can I donate?",
  ]) assert.equal(isLegalHelpRequest(q), false, q);
});

test("cleanMessages enforces alternating roles, ending on user, and size caps", () => {
  assert.equal(cleanMessages([]), null);
  assert.equal(cleanMessages([{ role: "assistant", content: "hi" }]), null);
  assert.equal(cleanMessages([{ role: "user", content: "x".repeat(801) }]), null);
  assert.equal(cleanMessages([{ role: "system", content: "x" }]), null);
  assert.equal(cleanMessages([{ role: "user", content: "a" }, { role: "user", content: "b" }]), null);
  assert.deepEqual(cleanMessages([{ role: "user", content: "  hello   there " }]), [{ role: "user", content: "hello there" }]);
});

test("finalize renumbers citations in order, drops unknown ids, strips raw URLs", () => {
  const core = [{ id: "C3", title: "Issue areas", url: "https://hiappleseed.org/issues", text: "" }];
  const hits = [
    { t: "Policy in Perspective 2026", u: "https://hiappleseed.org/publications/policy-perspective-2026" },
    { t: "Testimony", u: null },
  ];
  const { answer, sources } = finalize(
    "It passed [2]. See https://evil.example/x for more [C3] and [1] and [C99] and [2].",
    core,
    hits,
  );
  assert.equal(answer.includes("evil.example"), false);
  assert.equal(answer.includes("C99"), false);
  assert.match(answer, /\[1\] and \[2\]/);
  assert.deepEqual(sources.map((s) => s.url), [
    "https://hiappleseed.org/issues",
    "https://hiappleseed.org/publications/policy-perspective-2026",
  ]);
});

test("retrieval: topical queries find the right documents", () => {
  const top = (q) => search(index, q).map((h) => h.t.toLowerCase()).join(" | ");
  assert.match(top("universal free school meals HB1779"), /school meal|meals/);
  assert.match(top("conveyance tax DHHL"), /conveyance/);
  assert.match(top("SNAP certification period ESAP"), /snap/);
  assert.equal(search(index, "the of and").length, 0);
});

test("retrieval: a short follow-up reuses the previous question", () => {
  const q = queryFor([
    { role: "user", content: "What is Appleseed's position on the conveyance tax?" },
    { role: "assistant", content: "..." },
    { role: "user", content: "and DHHL?" },
  ]);
  assert.match(q, /conveyance/);
});

const fake = (text, extra = {}) => ({
  messages: { create: async () => ({ stop_reason: "end_turn", usage: {}, content: [{ type: "text", text }], ...extra }) },
});
const ask = (q, client, env) => handleChat({ messages: [{ role: "user", content: q }], index, client, env });

test("handler: the legal gate answers without calling the model", async () => {
  const client = { messages: { create: async () => assert.fail("model must not be called") } };
  const r = await ask("I'm being evicted, can you represent me?", client);
  assert.equal(r.body.answer, LEGAL_REPLY);
  assert.equal(r.body.flags.legal, true);
});

test("handler: a [[LEGAL]] reply from the model becomes the canned text", async () => {
  const r = await ask("Is my lease valid?", fake("[[LEGAL]]"));
  assert.equal(r.body.answer, LEGAL_REPLY);
});

test("handler: refusal and upstream failure give friendly fallbacks, not blanks", async () => {
  const r1 = await ask("What does Appleseed do?", fake("", { stop_reason: "refusal", content: [] }));
  assert.equal(r1.body.flags.refusal, true);
  const boom = { messages: { create: async () => { throw Object.assign(new Error("x"), { status: 400 }); } } };
  const r2 = await ask("What does Appleseed do?", boom);
  assert.equal(r2.status, 502);
  assert.match(r2.body.answer, /unavailable/);
});

test("handler: request carries cached rules block, excerpts block, and the model setting", async () => {
  let seen;
  const client = { messages: { create: async (p) => { seen = p; return { stop_reason: "end_turn", usage: {}, content: [{ type: "text", text: "ok" }] }; } } };
  await ask("What is the conveyance tax?", client, { MODEL: "claude-haiku-5-5" });
  assert.equal(seen.model, "claude-haiku-5-5");
  assert.equal(seen.system[0].cache_control.type, "ephemeral");
  assert.equal(seen.system[1].cache_control, undefined);
  assert.match(seen.system[0].text, /\[\[LEGAL\]\]/);
  assert.match(seen.system[1].text, /EXCERPTS/);
  assert.equal("temperature" in seen, false);
});

const coreId = (title) => index.core.find((s) => s.title === title).id;

test("research: a cited position section brings its curated reports, with year and PDF", async () => {
  const id = coreId("Conveyance tax modernization");
  const r = await ask("What is your position on the conveyance tax?", fake(`Hawaiʻi Appleseed strongly supports modernizing it [${id}].`));
  assert.deepEqual(r.body.sources.map((s) => s.url), ["https://hiappleseed.org/taxes-budget"]);
  const slugs = r.body.related.map((x) => x.url.split("/").pop());
  assert.ok(slugs.includes("preserving-hawaii"), slugs.join());
  const pres = r.body.related.find((x) => x.url.endsWith("/preserving-hawaii"));
  assert.equal(pres.year, 2024);
  assert.match(pres.pdf, /^https:\/\//);
  assert.ok(r.body.related.length <= 3);
});

test("research: a cited publication excerpt is a source with year and PDF, and is not repeated as related", async () => {
  const hits = search(index, queryFor([{ role: "user", content: "What is Keiki Ride Free?" }]));
  const n = hits.findIndex((h) => h.u?.endsWith("/keiki-ride-free")) + 1;
  assert.ok(n > 0, "retrieval should surface the Keiki Ride Free report");
  const r = await ask("What is Keiki Ride Free?", fake(`It is a fare-free transit proposal for youth [${n}].`));
  const src = r.body.sources.find((s) => s.url.endsWith("/keiki-ride-free"));
  assert.equal(src.year, 2026);
  assert.ok(src.pdf);
  assert.equal(r.body.related.some((x) => x.url.endsWith("/keiki-ride-free")), false);
});

test("research: no related reports for a question that cites no research", async () => {
  const r = await ask("Who is the executive director?", fake(`Will White is the executive director [${coreId("Staff")}].`));
  assert.deepEqual(r.body.related, []);
  const poem = await ask("Write me a poem", fake("I can only answer questions about Hawaiʻi Appleseed."));
  assert.deepEqual(poem.body.related, []);
});

test("research: legal and refusal replies carry no research links", async () => {
  const r = await ask("I'm being evicted, can you represent me?", fake("x"));
  assert.deepEqual(r.body.related, []);
});

test("legal reply names the Bar Association referral and carries its link", async () => {
  const r = await ask("I need a lawyer", fake("x"));
  assert.equal(r.body.flags.legal, true);
  assert.match(r.body.answer, /not a direct service provider/);
  assert.match(r.body.answer, /\[1\]/);
  assert.equal(r.body.sources[0].url, "https://hsba.org/HSBA_2020/Public/Legal_Assistance.aspx");
  const viaModel = await ask("Is my lease valid?", fake("[[LEGAL]]"));
  assert.deepEqual(viaModel.body.sources, r.body.sources);
});

test("practical sections are in the prompt with their own links, so citing them links the right page", () => {
  const want = {
    "Sign up for the newsletter and action alerts": "https://hiappleseed.org/subscribe",
    "Contact your legislator": "https://hiappleseed.quorum.us/",
    "Contact the office": "https://hiappleseed.org/contact",
    "Jobs, requests for proposals, volunteering": "https://hiappleseed.org/opportunities",
    "Legal help and referrals": "https://hsba.org/HSBA_2020/Public/Legal_Assistance.aspx",
  };
  for (const [title, url] of Object.entries(want)) {
    const s = index.core.find((c) => c.title === title);
    assert.ok(s, title);
    assert.equal(s.url, url);
  }
  const contact = index.core.find((c) => c.title === "Contact the office").text;
  assert.match(contact, /\(808\) 587-7605/);
  assert.match(contact, /info@hiappleseed\.org/);
});
