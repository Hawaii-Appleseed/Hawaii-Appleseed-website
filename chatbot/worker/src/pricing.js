// $ per million tokens, first-party list prices (API skill table, cached 2026-10-06; re-check before relying
// on them). A cache read is 0.1x the input price; a cache write uses the 1-hour TTL the handler asks for, 2x.
// Because tokens x ($ per million) is micro-dollars, the arithmetic below needs no unit conversion.
export const PRICES = {
  "claude-sonnet-5-5": { in: 2, out: 10 },
  "claude-haiku-5-5": { in: 0.1, out: 0.5 },
};

/** Cost of one response in micro-dollars (1,000,000 = $1). Unknown models are priced as Sonnet. */
export function microDollars(usage = {}, model) {
  const p = PRICES[model] ?? PRICES["claude-sonnet-5-5"];
  return Math.round(
    (usage.input_tokens ?? 0) * p.in +
      (usage.cache_read_input_tokens ?? 0) * p.in * 0.1 +
      (usage.cache_creation_input_tokens ?? 0) * p.in * 2 +
      (usage.output_tokens ?? 0) * p.out,
  );
}
