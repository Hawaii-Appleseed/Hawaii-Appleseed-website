// Headless Node unit tests for the static port's model-free retrieval core.
// Asserts bit-for-bit parity with Python on: tokenizer, query expansion, pure-
// bill detection, BM25 public search, and group_sections. Run:
//   node content-search/test/run_all.mjs
// Exits non-zero on any mismatch (used as a CI gate before deploy).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { tokenize, expandQuery, isPureBillQuery, billTokens } from "../js/tokenize.js";
import { BM25 } from "../js/bm25.js";
import { groupSections } from "../js/sentences.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA = resolve(__dirname, "..", "data");
const j = (p) => JSON.parse(readFileSync(resolve(DATA, p), "utf-8"));
const jt = (p) => JSON.parse(readFileSync(resolve(__dirname, p), "utf-8"));

let failures = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`  ✓ ${name}`);
  } else {
    failures++;
    console.error(`  ✗ ${name} ${detail}`);
  }
}
function arrEq(a, b) {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

// ---- 1. tokenizer fixture ---------------------------------------------------
console.log("tokenizer fixture:");
{
  const fx = j("tokenizer_fixture.json");
  let tokOk = true, expOk = true, pureOk = true, billOk = true;
  for (const [s, expected] of Object.entries(fx.tokenize)) {
    if (!arrEq(tokenize(s), expected)) { tokOk = false; console.error(`    tokenize(${JSON.stringify(s)}) -> ${JSON.stringify(tokenize(s))} != ${JSON.stringify(expected)}`); }
  }
  for (const [s, expected] of Object.entries(fx.expand_query)) {
    if (expandQuery(s) !== expected) { expOk = false; console.error(`    expand(${JSON.stringify(s)}) -> ${JSON.stringify(expandQuery(s))} != ${JSON.stringify(expected)}`); }
  }
  for (const [s, expected] of Object.entries(fx.is_pure_bill)) {
    if (isPureBillQuery(s) !== expected) { pureOk = false; console.error(`    isPureBill(${JSON.stringify(s)}) -> ${isPureBillQuery(s)} != ${expected}`); }
  }
  for (const [s, expected] of Object.entries(fx.bill_tokens)) {
    if (!arrEq([...billTokens(s)].sort(), expected)) { billOk = false; console.error(`    billTokens(${JSON.stringify(s)}) mismatch`); }
  }
  check("tokenize", tokOk);
  check("expand_query", expOk);
  check("is_pure_bill", pureOk);
  check("bill_tokens", billOk);
}

// ---- 2. BM25 public search --------------------------------------------------
console.log("BM25 public search:");
{
  const chunks = j("chunks.json");
  const bm25 = new BM25(j("bm25.json"));
  const fx = jt("fixtures.json");
  const idOf = (i) => chunks[i].id;
  let allOk = true;
  for (const [q, expectedIds] of Object.entries(fx.bm25)) {
    const idxs = bm25.search(tokenize(q), 100, () => true);
    const got = idxs.map(idOf);
    // Python dumped up to 100; compare the overlapping prefix length.
    const k = Math.min(got.length, expectedIds.length);
    const ok = arrEq(got.slice(0, k), expectedIds.slice(0, k)) && got.length === expectedIds.length;
    if (!ok) {
      allOk = false;
      console.error(`    "${q}": got ${got.length} ids, expected ${expectedIds.length}`);
      for (let i = 0; i < k; i++) if (got[i] !== expectedIds[i]) { console.error(`      first diff @${i}: ${got[i]} != ${expectedIds[i]}`); break; }
    }
  }
  check("bm25 search ids match Python", allOk);
}

// ---- 3. group_sections ------------------------------------------------------
console.log("group_sections:");
{
  const chunks = j("chunks.json");
  const byId = new Map(chunks.map((c) => [c.id, c]));
  const fx = jt("fixtures.json");
  let allOk = true;
  for (const cse of fx.group_sections) {
    const hits = cse.input_ids.map((id) => {
      const c = byId.get(id);
      return { text: c.text, meta: { source: c.source, chunk: c.chunk } };
    });
    const grouped = groupSections(hits, 30);
    const got = grouped.map((g) => ({
      source: g.meta.source,
      n_sections: g.n_sections,
      primary_chunk: g.meta.chunk,
      extra_chunks: g.extra_sections.map((s) => s.chunk),
    }));
    const ok = JSON.stringify(got) === JSON.stringify(cse.expected);
    if (!ok) {
      allOk = false;
      console.error(`    "${cse.query}": grouping mismatch (got ${got.length}, exp ${cse.expected.length})`);
      for (let i = 0; i < Math.min(got.length, cse.expected.length); i++) {
        if (JSON.stringify(got[i]) !== JSON.stringify(cse.expected[i])) {
          console.error(`      @${i} got ${JSON.stringify(got[i])}`);
          console.error(`           exp ${JSON.stringify(cse.expected[i])}`);
          break;
        }
      }
    }
  }
  check("group_sections matches Python", allOk);
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
