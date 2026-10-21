// Hard stop for requests for legal help. The answer to those is always "no", and it is
// always this exact text, never model-written. This deterministic gate catches the
// clear cases before any model call; the system prompt tells the model to reply
// [[LEGAL]] for the rest, and the handler swaps that for the same text.

export const LEGAL_REPLY =
  "I can't help with legal questions or give legal advice, and Hawaiʻi Appleseed can't take on " +
  "anyone's case through this chat. If you need legal help, please contact a licensed attorney " +
  "or a legal aid organization. I'm glad to answer questions about Hawaiʻi Appleseed's work, " +
  "research, and policy positions.";

export const LEGAL_SENTINEL = "[[LEGAL]]";

const norm = (s) => s.toLowerCase().replace(/[‘’ʻ`]/g, "'").replace(/\s+/g, " ");

// A question about policy ("does Appleseed support legal aid funding?") is not a request for
// legal help even when it uses the same words, so these cues switch the soft patterns off.
const POLICY_CUE =
  /\b(appleseed|position|support|oppos|bill|legislat|lawmaker|policy|policies|proposal|advocat|testimony|publication|report|research|act \d+|hb ?\d+|sb ?\d+)\b/;

// Clear, personal requests: matched whatever else the message says.
const HARD = [
  /\brepresent\s+(me|us|my|our)\b/,
  /\bbe\s+(my|our)\s+(lawyer|attorney|counsel)\b/,
  /\btake\s+(on\s+)?(my|our)\s+(case|claim|lawsuit|matter)\b/,
  /\b(need|want|looking\s+for|find|hire|get|call)\s+(me\s+)?(a|an|some|the)?\s*(good\s+|free\s+|cheap\s+)?(lawyer|attorney)\b/,
  /\b(need|want|give\s+me|get)\s+(some\s+|any\s+)?legal\s+(advice|help|assistance|aid|representation)\b/,
  /\bcan\s+(you|someone|anyone)\s+(help|advise)\s+me\s+(with|on)\s+(my|a|an)\s+(legal|case|lawsuit|eviction|court)/,
  /\b(can|could|should|may|do)\s+(i|we)\s+(sue|appeal|press\s+charges|file\s+(a\s+)?(suit|lawsuit|complaint|claim|appeal|charges?))\b/,
  /\bsue\s+(my|our|the|them|him|her)\b/,
  /\bwhat\s+(are|is)\s+my\s+(legal\s+)?(rights|options|chances|recourse)\b/,
  /\bam\s+i\s+(legally|allowed|entitled|required|obligated)\b/,
  /\b(i|we)\s+(got|received|have|was\s+given|were\s+given|just\s+got)\s+(an?\s+)?(eviction|court|summons|subpoena|citation|notice\s+to\s+quit|demand\s+letter)/,
  /\b(i|we)\s+(am|are|was|were|got|have\s+been|just\s+got)\s+(being\s+|getting\s+)?(evicted|sued|fired|arrested|served|laid\s+off|discriminated)/,
  /\bmy\s+(landlord|employer|boss|manager|ex|ex-husband|ex-wife)\s+(is|are|has|have|won't|wont|refuses?|threatened|keeps?|just)\b/,
  /\bhow\s+do\s+(i|we)\s+(fight|contest|dispute|challenge|respond\s+to)\s+(this|my|the|an?)\s+(eviction|ticket|citation|charge|notice|lawsuit|case)/,
];

// Softer wording, matched only when the message shows no policy interest.
const SOFT = [
  /\blegal\s+(advice|help|assistance|aid|representation|services?|counsel)\b/,
  /\b(lawyer|attorney)\b/,
  /\b(my|our)\s+(case|lawsuit|eviction|tenancy|lease|landlord|deposit|wages?\s+owed|unpaid\s+wages?)\b/,
];

export function isLegalHelpRequest(text) {
  const t = norm(text);
  if (HARD.some((r) => r.test(t))) return true;
  if (POLICY_CUE.test(t)) return false;
  return SOFT.some((r) => r.test(t));
}
