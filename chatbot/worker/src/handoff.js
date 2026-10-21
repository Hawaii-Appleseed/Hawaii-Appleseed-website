// "Ask a person". When the assistant cannot answer, the page offers a button that opens a prefilled email to the office
// (a mailto: link the visitor sends from their own mail app) next to the phone number and Contact page. The assistant never
// contacts anyone, and the question goes nowhere unless the visitor sends that email: the Worker only says WHETHER to offer it
// and with which contact details (index.contact, built from the "Contact the office" section of practical.md).
//
// Offered when: the model ends its answer with [[staff]] (the prompt asks it to whenever it says it lacks the information, the
// question is about the visitor's own situation, or a staff member would have to decide), or the answer plainly says it has
// no information or no stated position, or a ready-made reply is the fixed "no published position" one. Never on a legal-help
// reply: the answer there is the bar association's list, and the office does not take cases.

const MARKER = /\[\[\s*staff\s*\]\]/gi;
const STRAY = /\[\[\s*staff[^\]\n]*\]{0,2}/gi; // a marker that did not parse

// The wording the rules tell the model to use when it has nothing: "I don't have that information", "no stated position".
const NO_ANSWER = new RegExp(
  "\\b(i (do not|don't|cannot|can't|could not|couldn't) (have|find|say|tell|confirm|answer)|" +
    "i have not (checked|found)|no stated position|has not published a position|" +
    "not (covered|listed|described|stated) (in|on|by)|" +
    "(isn't|is not|aren't|are not|wasn't|was not) (in|covered|listed|described)( in)? (the|my|this)? ?(material|sources|excerpts|information|publications))\\b",
  "i",
);

/** Take the [[staff]] marker out of the model's text. */
export function takeStaffMarker(text) {
  let asked = false;
  const clean = text
    .replace(MARKER, () => { asked = true; return ""; })
    .replace(STRAY, () => { asked = true; return ""; })
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { text: clean, asked };
}

/** Why a person is being offered under this answer ("marker", "deferral", "wording"), or null. */
export function handoffCause(index, { asked = false, answer = "", cannedId = null, legal = false } = {}) {
  if (legal || !index.contact) return null;
  const plain = answer.replace(/[‘’ʻ`]/g, "'");
  if (asked) return "marker";
  if (cannedId === "no-position") return "deferral";
  return NO_ANSWER.test(plain) ? "wording" : null;
}

/** The contact details to offer under this answer, or null. */
export function handoffFor(index, opts = {}) {
  return handoffCause(index, opts) ? { ...index.contact } : null;
}
