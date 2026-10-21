// "Ask a person". When the assistant cannot answer, the page offers a button that opens a prefilled email to the office
// (a mailto: link the visitor sends from their own mail app) next to the phone number and Contact page. The assistant never
// contacts anyone, and the question goes nowhere unless the visitor sends that email: the Worker only says WHETHER to offer it
// and with which contact details (index.contact, built from the "Contact the office" section of practical.md).
//
// Offered when: the model ends its answer with [[staff]] (the prompt asks it to whenever it says it lacks the information, the
// question is about the visitor's own situation, or a staff member would have to decide; when it names the people to talk to it
// writes [[staff: id, id]] with ids from the "Who to talk to" section, and the page offers an email to each), or the answer plainly says it has
// no information or no stated position, or a ready-made reply is the fixed "no published position" one. Never on a legal-help
// reply: the answer there is the bar association's list, and the office does not take cases.

const MARKER = /\[\[\s*staff(?:\s*:\s*([a-z0-9][a-z0-9\s,-]*))?\s*\]\]/gi; // [[staff]] or [[staff: arjuna-heim, kamakani-albano]]
const MAX_PEOPLE = 2;
const STRAY = /\[\[\s*staff[^\]\n]*\]{0,2}/gi; // a marker that did not parse

// The wording the rules tell the model to use when it has nothing: "I don't have that information", "no stated position".
const NO_ANSWER = new RegExp(
  "\\b(i (do not|don't|cannot|can't|could not|couldn't) (have|find|say|tell|confirm|answer)|" +
    "i have not (checked|found)|no stated position|has not published a position|" +
    "not (covered|listed|described|stated) (in|on|by)|" +
    "(isn't|is not|aren't|are not|wasn't|was not) (in|covered|listed|described)( in)? (the|my|this)? ?(material|sources|excerpts|information|publications))\\b",
  "i",
);

/** Take the [[staff]] marker out of the model's text; `ids` are the people it named (checked against the index later). */
export function takeStaffMarker(text) {
  let asked = false;
  const ids = [];
  const clean = text
    .replace(MARKER, (_, list) => {
      asked = true;
      for (const id of (list ?? "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean)) if (!ids.includes(id)) ids.push(id);
      return "";
    })
    .replace(STRAY, () => { asked = true; return ""; })
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { text: clean, asked, ids };
}

/** Why a person is being offered under this answer ("marker", "deferral", "wording"), or null. */
export function handoffCause(index, { asked = false, answer = "", cannedId = null, legal = false } = {}) {
  if (legal || !index.contact) return null;
  const plain = answer.replace(/[‘’ʻ`]/g, "'");
  if (asked) return "marker";
  if (cannedId === "no-position") return "deferral";
  return NO_ANSWER.test(plain) ? "wording" : null;
}

/** The staff the model named that really are staff (at most two, in the order named): { id, name, title, email }. A made-up id
 *  names no one, and an index with no staff list (a public build before the routing is approved) names no one either. */
export function peopleFor(index, ids = []) {
  const by = new Map((index.staff?.people ?? []).map((p) => [p.id, p]));
  return ids.filter((id) => by.has(id)).slice(0, MAX_PEOPLE).map((id) => { const { name, title, email } = by.get(id); return { id, name, title, email }; });
}

/** The contact details to offer under this answer (the office, and the named staff if any), or null. */
export function handoffFor(index, opts = {}) {
  if (!handoffCause(index, opts)) return null;
  const people = peopleFor(index, opts.ids);
  return { ...index.contact, ...(people.length ? { people } : {}) };
}
