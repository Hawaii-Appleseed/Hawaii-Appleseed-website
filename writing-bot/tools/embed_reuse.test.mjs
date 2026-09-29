// Model-free tests for embed_reuse.mjs, using fake vectors.
//   node writing-bot/tools/embed_reuse.test.mjs     (exits non-zero on failure)

import { createHash } from "node:crypto";
import { cacheKey, parsePrev, reuseOrEmbed, textHash } from "./embed_reuse.mjs";

const DIM = 4;
const KEY = {
  model: "m",
  dtype: "q8",
  dim: DIM,
  max_tokens: 256,
  transformersjs_version: "3.7.5",
};

let failures = 0;
function check(name, cond, detail = "") {
  if (cond) console.log(`  ok   ${name}`);
  else {
    failures++;
    console.error(`  FAIL ${name} ${detail}`);
  }
}

// Deterministic fake vector for (text, generation): the generation lets a test
// tell an old vector from a freshly embedded one for the same text.
function fake(text, gen) {
  const h = createHash("sha256").update(`${gen}:${text}`).digest();
  return Float32Array.from({ length: DIM }, (_, i) => h[i] / 255);
}
function fakeMatrix(texts, gen) {
  const o = new Float32Array(texts.length * DIM);
  texts.forEach((t, i) => o.set(fake(t, gen), i * DIM));
  return o;
}
function counter(gen = "new") {
  const f = async (texts) => {
    f.calls++;
    f.texts.push(...texts);
    return fakeMatrix(texts, gen);
  };
  f.calls = 0;
  f.texts = [];
  return f;
}
// Build a previous bundle (raw file contents) from texts, generation "old".
function bundle(texts, keyOverride = {}, tweak = {}) {
  const bin = Buffer.from(fakeMatrix(texts, "old").buffer);
  const meta = {
    ...KEY,
    ...keyOverride,
    count: texts.length,
    sha256: createHash("sha256").update(bin).digest("hex"),
  };
  return {
    metaText: JSON.stringify(meta),
    chunksText: JSON.stringify(texts.map((text, i) => ({ id: `c${i}`, text }))),
    binBuf: bin,
    ...tweak,
  };
}
function row(out, i) {
  return Array.from(out.subarray(i * DIM, (i + 1) * DIM));
}
const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const isOld = (out, i, t) => same(row(out, i), Array.from(fake(t, "old")));
const isNew = (out, i, t) => same(row(out, i), Array.from(fake(t, "new")));

async function run(texts, raw, { force = false, key = KEY } = {}) {
  const { prev, reason } = parsePrev(raw, key);
  const embedFn = counter();
  const res = await reuseOrEmbed({ texts, key, prev, force, embedFn, reason });
  return { res, embedFn, reason };
}

const A = ["alpha", "bravo", "charlie", "delta"];

console.log("all unchanged:");
{
  const { res, embedFn } = await run(A, bundle(A));
  check("zero embed calls", embedFn.calls === 0);
  check("all reused", res.reused === 4 && res.embedded === 0);
  check("every row is the old vector", A.every((t, i) => isOld(res.out, i, t)));
}

console.log("one changed chunk:");
{
  const T = ["alpha", "bravo EDITED", "charlie", "delta"];
  const { res, embedFn } = await run(T, bundle(A));
  check("one embed call with only the changed text", embedFn.calls === 1 && same(embedFn.texts, ["bravo EDITED"]));
  check("changed row is new", isNew(res.out, 1, "bravo EDITED"));
  check("others keep old vectors", [0, 2, 3].every((i) => isOld(res.out, i, T[i])));
}

console.log("one new chunk (appended and inserted):");
{
  const T = ["alpha", "NEW", "bravo", "charlie", "delta", "NEW2"];
  const { res, embedFn } = await run(T, bundle(A));
  check("embeds exactly the two new texts", same(embedFn.texts, ["NEW", "NEW2"]) && embedFn.calls === 1);
  check("new rows placed in output order", isNew(res.out, 1, "NEW") && isNew(res.out, 5, "NEW2"));
  check("old rows shifted to their new positions", isOld(res.out, 0, "alpha") && isOld(res.out, 2, "bravo") && isOld(res.out, 4, "delta"));
  check("count and length", res.out.length === 6 * DIM && res.reused === 4 && res.embedded === 2);
}

console.log("removed chunk:");
{
  const T = ["alpha", "charlie", "delta"];
  const { res, embedFn } = await run(T, bundle(A));
  check("zero embed calls", embedFn.calls === 0);
  check("remaining rows are the right old vectors", T.every((t, i) => isOld(res.out, i, t)));
  check("output has 3 rows", res.out.length === 3 * DIM);
}

console.log("reordered chunks:");
{
  const T = ["delta", "alpha", "charlie", "bravo"];
  const { res, embedFn } = await run(T, bundle(A));
  check("zero embed calls", embedFn.calls === 0);
  check("vectors follow their text, not their position", T.every((t, i) => isOld(res.out, i, t)));
}

console.log("duplicate texts:");
{
  const T = ["alpha", "dup", "dup", "dup"];
  const { res, embedFn } = await run(T, bundle(A));
  check("duplicate new text embedded once", same(embedFn.texts, ["dup"]));
  check("all copies filled", [1, 2, 3].every((i) => isNew(res.out, i, "dup")));
}

console.log("cache-key mismatch forces a full re-embed:");
for (const [field, val] of [
  ["model", "other"],
  ["dtype", "fp32"],
  ["max_tokens", 512],
  ["transformersjs_version", "3.8.0"],
  ["dim", 8],
]) {
  const raw = bundle(A, { [field]: val });
  const { res, embedFn, reason } = await run(A, raw);
  check(
    `${field} change`,
    embedFn.calls === 1 && embedFn.texts.length === 4 && res.reused === 0 && /cache key mismatch/.test(reason ?? ""),
    JSON.stringify({ calls: embedFn.calls, reason })
  );
}
{
  // Previous meta written before max_tokens existed (the format on main today).
  const raw = bundle(A);
  const meta = JSON.parse(raw.metaText);
  delete meta.max_tokens;
  const { res, embedFn } = await run(A, { ...raw, metaText: JSON.stringify(meta) });
  check("legacy meta without max_tokens", embedFn.texts.length === 4 && res.reused === 0);
}
check("cacheKey covers all five fields", cacheKey(KEY).split("|").length === 5);

console.log("forced run:");
{
  const { prev } = parsePrev(bundle(A), KEY);
  check("previous bundle itself is valid", prev !== null);
  const embedFn = counter();
  const res = await reuseOrEmbed({ texts: A, key: KEY, prev, force: true, embedFn });
  check("full embed despite valid previous", embedFn.texts.length === 4 && res.reused === 0);
  check("all rows are new", A.every((t, i) => isNew(res.out, i, t)));
  check("reason says forced", res.reason === "forced run");
}

console.log("missing / corrupt previous bundle falls back to full embed:");
{
  const good = bundle(A);
  const badBin = Buffer.from(good.binBuf);
  badBin[0] ^= 0xff;
  const cases = {
    "all missing (null)": { metaText: null, chunksText: null, binBuf: null },
    "meta missing": { ...good, metaText: null },
    "chunks missing": { ...good, chunksText: null },
    "bin missing": { ...good, binBuf: null },
    "meta not JSON": { ...good, metaText: "{oops" },
    "chunks not JSON": { ...good, chunksText: "<html>" },
    "chunks not an array": { ...good, chunksText: "{}" },
    "bin truncated": { ...good, binBuf: good.binBuf.subarray(0, 20) },
    "bin bytes flipped (sha mismatch)": { ...good, binBuf: badBin },
    "count disagrees with chunks": { ...good, chunksText: JSON.stringify(A.slice(1).map((text) => ({ text }))) },
    "chunk without text": { ...good, chunksText: JSON.stringify(A.map(() => ({}))) },
  };
  for (const [name, raw] of Object.entries(cases)) {
    let threw = false;
    let r;
    try {
      r = await run(A, raw);
    } catch {
      threw = true;
    }
    check(
      name,
      !threw && r.embedFn.texts.length === 4 && r.res.reused === 0 && A.every((t, i) => isNew(r.res.out, i, t)),
      threw ? "threw" : ""
    );
  }
}

console.log("misc:");
{
  check("textHash is sha256 of utf-8", textHash("é") === createHash("sha256").update("é", "utf-8").digest("hex"));
  const bad = { async embedFn() { return new Float32Array(1); } };
  let threw = false;
  try {
    await reuseOrEmbed({ texts: A, key: KEY, prev: null, force: false, embedFn: bad.embedFn });
  } catch {
    threw = true;
  }
  check("wrong-size embedder output is an error, not silent corruption", threw);
  // Odd Buffer byteOffset (as from a pooled Buffer) must not break decoding.
  const raw = bundle(A);
  const padded = Buffer.alloc(raw.binBuf.length + 1);
  raw.binBuf.copy(padded, 1);
  const { res, embedFn } = await run(A, { ...raw, binBuf: padded.subarray(1) });
  check("unaligned bin buffer still reused", embedFn.calls === 0 && A.every((t, i) => isOld(res.out, i, t)));
}

if (failures) {
  console.error(`\n${failures} failure(s)`);
  process.exit(1);
}
console.log("\nall embed_reuse tests passed");
