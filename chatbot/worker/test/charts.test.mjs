import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { chartProblem, checkChart, numbers, resolver, takeChart } from "../src/charts.js";
import { handleChat } from "../src/handler.js";
import { buildSystem } from "../src/prompt.js";

const index = JSON.parse(readFileSync(new URL("../src/index.json", import.meta.url), "utf8"));
const sec = (title) => index.core.find((c) => c.title === title);
const CONV = sec("Conveyance tax modernization");
const resolve = resolver(index.core, [{ x: "In 2024 the report found that a 5 percent tax would raise about $305.67 million a year.", u: "https://hiappleseed.org/publications/empty-homes-tax-honolulu", t: "Homes Without Residents" }], index.pubs);
const bars = (rows, extra = {}) => ({ type: "bars", title: "Prison budget and Hawaiian Home Lands", unit: "annual budget, in millions of dollars", rows, ...extra });
const row = (label, value, display, quote, ref = CONV.id) => ({ label, value, display, quote, ref });
const good = () => bars([
  row("Prison budget", 300, "$300 million", "a $300 million prison budget"),
  row("Hawaiian Home Lands (DHHL)", 185, "$185 million", "$185 million for DHHL"),
]);
const never = { messages: { create: async () => assert.fail("the model must not run") } };
const says = (text) => ({ messages: { create: async () => ({ stop_reason: "end_turn", content: [{ type: "text", text }], usage: {} }) } });
const ask = (q, text, env = {}) => handleChat({ messages: [{ role: "user", content: q }], index, client: says(text), env });

test("charts: numbers() reads digits, commas, decimals and spelled-out tens", () => {
  assert.deepEqual([...numbers("Sixty-six percent of $5.68 billion, May 21, 2026 and $1,000,000")].sort(), ["1000000", "2026", "21", "5.68", "66"]);
});

test("charts: a chart whose every figure is quoted from the text it names is accepted, with its source", () => {
  const c = checkChart(good(), resolve);
  assert.equal(c.type, "bars");
  assert.equal(c.generated, true);
  assert.deepEqual(c.rows.map((r) => [r.value, r.display]), [[300, "$300 million"], [185, "$185 million"]]);
  assert.equal(c.sources[0].url, CONV.url);
  assert.ok(c.rows.every((r) => r.quote));
  assert.ok(!JSON.stringify(c).includes("_kind"));
});

test("charts: an excerpt can be the source, named by its number", () => {
  const hit = { x: "In 2024 the report found that a 5 percent tax would raise about $305.67 million a year, and a 3 percent tax about $183.4 million.", u: "https://hiappleseed.org/publications/empty-homes-tax-honolulu", t: "Homes Without Residents" };
  const c = checkChart(bars([
    row("5 percent tax", 305.67, "$305.67 million", "a 5 percent tax would raise about $305.67 million a year", "1"),
    row("3 percent tax", 183.4, "$183.4 million", "a 3 percent tax about $183.4 million", "1"),
  ]), resolver(index.core, [hit], index.pubs));
  assert.ok(c);
  assert.deepEqual(c.sources.map((s) => s.title), ["Homes Without Residents"]);
});

test("charts: bars only compare numbers the source puts side by side", () => {
  const A = { x: "In 2024 prisons cost $300 million while DHHL got $185 million. Elsewhere, housing needs are large.", u: "https://hiappleseed.org/a", t: "Report A" };
  const B = { x: "DHHL's budget sits at $185 million this year.", u: "https://hiappleseed.org/b", t: "Report B" };
  const r = resolver(index.core, [A, B], {});
  const unit = { unit: "annual budget, in millions of dollars" };
  const two = (q2, ref2) => bars([row("Prisons", 300, "$300 million", "prisons cost $300 million", "1"), row("DHHL", 185, "$185 million", q2, ref2)], unit);
  // different reports, and no sentence holds both numbers: a $300 million and a $185 million that never met
  const C = { x: "Prisons cost $300 million in 2019.", u: "https://hiappleseed.org/c", t: "Report C" };
  assert.equal(chartProblem(two("DHHL's budget sits at $185 million", "2"), resolver(index.core, [C, B], {})), "different_sources");
  // different refs, but one report's own sentence carries both numbers: the source pairs them
  assert.equal(chartProblem(two("DHHL's budget sits at $185 million", "2"), r), null);
  // the same ref
  assert.equal(chartProblem(two("DHHL got $185 million", "1"), r), null);
});

test("charts: bars from one section but far apart, without a unit, or with a label the quote never uses are refused", () => {
  const filler = "Housing remains a concern for many families across the islands. ".repeat(20);
  const D = { x: `Prisons cost $300 million. ${filler}DHHL got $185 million.`, u: "https://hiappleseed.org/d", t: "Report D" };
  const r = resolver(index.core, [D], {});
  const unit = { unit: "annual budget, in millions of dollars" };
  const mk = (extra = {}, labels = ["Prisons", "DHHL"], q = ["Prisons cost $300 million", "DHHL got $185 million"]) =>
    bars([row(labels[0], 300, "$300 million", q[0], "1"), row(labels[1], 185, "$185 million", q[1], "1")], { ...unit, ...extra });
  assert.equal(chartProblem(mk(), r), "far_apart", "one paragraph is fine, a page apart is not");
  const near = resolver(index.core, [{ ...D, x: "Prisons cost $300 million and DHHL got $185 million." }], {});
  assert.equal(chartProblem(mk(), near), null);
  assert.equal(chartProblem(mk({ unit: undefined }), near), "no_unit");
  assert.equal(chartProblem(mk({}, ["Housing", "DHHL"]), near), "label_not_in_quote");
  const spelled = resolver(index.core, [{ ...D, x: "The Department of Hawaiian Home Lands (DHHL) got $185 million while prisons cost $300 million." }], {});
  assert.equal(chartProblem(mk({}, ["Prisons", "Hawaiian Home Lands"], ["prisons cost $300 million", "DHHL) got $185 million"]), spelled), null, "a label may spell out an acronym that the text just before the quote spells out");
  assert.equal(chartProblem(mk({}, ["Prison spending", "DHHL"]), near), null, "any distinctive word of the label in its own quote is enough");
  const six = bars(Array.from({ length: 7 }, (_, i) => row(`Item ${i}`, 300, "$300 million", "Prisons cost $300 million", "1")), unit);
  assert.equal(chartProblem(six, near), "rows");
});

test("charts: any figure the text does not carry sinks the chart", () => {
  const cases = {
    "invented number": (s) => (s.rows[0].display = "$320 million", s.rows[0].value = 320),
    "quote is not in the section": (s) => (s.rows[0].quote = "a $300 million jail budget"),
    "quote too short to prove anything": (s) => (s.rows[0].quote = "$300"),
    "ref points nowhere": (s) => (s.rows[0].ref = "C9999"),
    "ref is an excerpt that does not exist": (s) => (s.rows[0].ref = "7"),
    "value is not the displayed number": (s) => (s.rows[0].value = 30),
    "scale dropped": (s) => (s.rows[0].display = "$300"),
    "scale changed": (s) => (s.rows[0].display = "$300 billion"),
    "number only in the label": (s) => (s.rows[1].label = "DHHL in 2031"),
    "number only in the title": (s) => (s.title = "The 2031 prison budget"),
    "negative value": (s) => (s.rows[0].value = -300),
    "markup in a label": (s) => (s.rows[0].label = "<img src=x onerror=alert(1)>"),
    "one row": (s) => s.rows.pop(),
    "duplicate labels": (s) => (s.rows[1].label = "Prison budget"),
    "unknown type": (s) => (s.type = "pie"),
    "no title": (s) => delete s.title,
  };
  for (const [why, tamper] of Object.entries(cases)) {
    const s = good();
    tamper(s);
    assert.equal(checkChart(s, resolve), null, why);
  }
});

test("charts: a number inside a year is not the number (20 million, in a quote that also says 2017)", () => {
  const hist = sec("Milestones and wins");
  const eitc = bars([
    { label: "2017", value: 20, display: "$20 million", quote: "2017: Hawaiʻi's first state Earned Income Tax Credit, worth $20 million in tax relief each year", ref: hist.id },
    { label: "2022", value: 40, display: "$40 million", quote: "It was expanded in 2022 to $40 million a year", ref: hist.id },
  ], { title: "Hawaiʻi state EITC tax relief each year", unit: "annual tax relief, in millions of dollars" });
  assert.equal(checkChart(eitc, resolve) ? "ok" : "rejected", "ok");
  eitc.rows[0].display = "$20"; // the scale really is dropped now
  assert.equal(checkChart(eitc, resolve), null);
});

test("charts: bars must compare like with like", () => {
  const mixedKind = bars([
    row("Conservation share", 5, "5 percent", "conservation (5 percent)"),
    row("DHHL budget", 185, "$185 million", "$185 million for DHHL"),
  ]);
  assert.equal(checkChart(mixedKind, resolve), null, "percent beside dollars");
  const mixedScale = bars([
    row("HDOT", 5.68, "$5.68 billion", "HDOT's $5.68 billion", sec("Transit equity and fare-free transit").id),
    row("DHHL budget", 185, "$185 million", "$185 million for DHHL"),
  ]);
  assert.equal(checkChart(mixedScale, resolve), null, "billions beside millions");
});

test("charts: quotes survive quote marks, okina, dashes and case, and stats and timelines are checked too", () => {
  const aff = sec("Empty homes tax (Honolulu)");
  const stats = { type: "stats", title: "Empty homes in Honolulu", items: [{ value: "35,000", label: "units sit empty", quote: "ABOUT 35,000 UNITS SIT EMPTY across Honolulu", ref: aff.id }] };
  assert.equal(checkChart(stats, resolve).items[0].value, "35,000");
  stats.items[0].value = "53,000";
  assert.equal(checkChart(stats, resolve), null);
  const hist = sec("Milestones and wins");
  const tl = { type: "timeline", title: "Milestones", rows: [
    { when: "2019", what: "Helped establish DA BUX", quote: "2019: Helped establish DA BUX", ref: hist.id },
    { when: "2017", what: "Hawaiʻi's first state EITC", quote: "2017: Hawaiʻi's first state Earned Income Tax Credit", ref: hist.id },
  ] };
  assert.deepEqual(checkChart(tl, resolve).rows.map((r) => r.when), ["2017", "2019"], "sorted by year");
  tl.rows[0].when = "2020";
  assert.equal(checkChart(tl, resolve), null, "a year the quote does not have");
});

test("charts: markers are taken out of the answer, bad JSON and cut-off markers draw nothing, and the first good chart wins", () => {
  const ok = JSON.stringify(good());
  let r = takeChart(`Prisons cost more. [C1]\n[[chart: ${ok}]]`, resolve);
  assert.equal(r.text, "Prisons cost more. [C1]");
  assert.ok(r.chart);
  r = takeChart(`Text.\n[[chart: {"type":"bars", nope}]]`, resolve);
  assert.deepEqual([r.text, r.chart], ["Text.", null]);
  r = takeChart(`Text.\n[[chart: ${ok.slice(0, 60)}`, resolve);
  assert.deepEqual([r.text, r.chart], ["Text.", null]);
  r = takeChart(`A [[chart: {"type":"pie"}]] B\n[[chart: ${ok}]]`, resolve);
  assert.ok(r.chart && !/chart/.test(r.text));
});

test("charts: handler shows a drawn chart only when no vetted graphic fits, and the switch turns it off", async () => {
  const text = `The prison budget is larger than the Hawaiian Home Lands budget. [C${CONV.id.slice(1)}]\n[[chart: ${JSON.stringify(good())}]]`;
  let r = await ask("How does the prison budget compare with Hawaiian Home Lands funding?", text);
  assert.equal(r.body.graphics.length, 1);
  assert.equal(r.body.graphics[0].generated, true);
  assert.doesNotMatch(r.body.answer, /chart|\[\[/);
  // a vetted graphic that fits wins: the model's own chart is dropped
  r = await ask("Show me a chart of the empty homes tax revenue", text.replace("prison", "empty homes"));
  assert.deepEqual(r.body.graphics.map((g) => g.id), ["eht-revenue"]);
  // switched off: no chart, marker still stripped, and the prompt does not mention charts it may draw
  r = await ask("How does the prison budget compare with Hawaiian Home Lands funding?", text, { DYNAMIC_GRAPHICS: "0" });
  assert.deepEqual(r.body.graphics, []);
  assert.doesNotMatch(r.body.answer, /chart|\[\[/);
  assert.match(buildSystem(index.core, index.graphics), /CHARTS YOU DRAW/);
  assert.doesNotMatch(buildSystem(index.core, index.graphics, { draw: false }), /CHARTS YOU DRAW/);
});

test("charts: legal and ready-made answers never carry a drawn chart", async () => {
  const r = await handleChat({ messages: [{ role: "user", content: "What is your mission?" }], index, client: never });
  assert.ok(!r.body.graphics.some((g) => g.generated));
});
