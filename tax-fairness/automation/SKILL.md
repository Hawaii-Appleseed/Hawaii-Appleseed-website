---
name: tax-fairness-notes
description: Process the Zoom meeting-assets email after a Tax Fairness Coalition meeting — pull the summary and next steps, diff them against the coalition notes doc, and stage a notes update, a #tax-fairness Slack post, and a coalition email draft. Use when a "Meeting assets for Tax Fairness Coalition are ready!" email arrives, or when asked to write up / follow up on a Tax Fairness Coalition meeting.
---

# Tax Fairness Coalition meeting write-up

Turns the Zoom AI recap into three staged outputs. **Nothing is ever sent or posted
automatically.** Every outward-facing artifact is staged for Devin to review and send.

## Hard rules

1. **Never send the coalition email.** Create a Gmail *draft* only. The list
   (`hawaii-tax-fairness@googlegroups.com`) is the whole coalition — a bad Zoom
   summary reaching it is unrecoverable.
2. **Never post to Slack.** Print the post for approval.
3. **Never overwrite existing notes.** Only *append* what is genuinely missing.
   Devin often writes the notes himself during or right after the meeting, and his
   omissions are frequently deliberate.
4. **Check for prior work first** (step 0). Skipping this produces duplicate emails.
5. The Zoom recap is AI-generated and gets names, numbers, and attributions wrong.
   Treat it as a source to verify, not ground truth. Flag anything that contradicts
   the notes rather than silently overwriting.

## Key identifiers

| Thing | Value |
|---|---|
| Notes doc | `1eQpkFh1GB0MswSyUuHscYRTx8f3Cy1IqylBW6DIZ8hg` |
| Notes doc tab | `t.xu3k0yc1qkmq` (meeting notes tab; the doc has several) |
| Coalition list | `hawaii-tax-fairness@googlegroups.com` |
| Slack channel | `#tax-fairness` |
| Gmail account | `devin@hibudget.org` (Chrome profile is already signed in) |
| Zoom room | `https://us02web.zoom.us/j/82917129894` |

## Meeting cadence (verified against Calendar 2026-08-27)

- **Tax Fairness Coalition** — full coalition, **biweekly Thursdays 9:00–10:30am HST**.
  Confirmed instances: Aug 13, Aug 27, Sept 10, 2026. This is the only event that
  should trigger this skill.
- Off-week Thursdays carry working-group meetings, which are **not** triggers:
  **Tax Fairness Comms Working Group** 9–10am and **Tax Policy Meeting** 2–3pm
  (e.g. Sept 3).

Meetings often end before the scheduled 10:30, and the Zoom assets email lands
roughly 10 minutes after the true end — on Aug 27 the meeting ran 9:00–~10:00 and
the email arrived at 10:07am.

Use **Claude in Chrome** (`mcp__claude-in-chrome__*`) for all of this — it has the
logged-in Google session. Load the tools in one `ToolSearch` call:

```
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__javascript_tool
```

## Step 0 — Check what Devin already did

Before anything else, establish whether this meeting has already been written up.
Skipping this step is the single most likely way to cause real damage.

- Search Gmail for `subject:"Tax Fairness"` messages sent today by Devin. If an
  update already went to the coalition list, **do not stage another email** — say
  so and move on to the notes diff.
- Read `#tax-fairness` and check for a recap posted since the meeting ended:

  ```bash
  python3 ~/.claude/skills/tax-fairness-notes/slack.py read --limit 15
  ```

  If Devin already posted the next steps, **do not stage another post.**
- Read the notes doc (step 2). If a section for today's date already exists, switch
  from "write the section" to "diff and propose additions."

On 2026-08-27 all three were already done manually within 90 minutes of the meeting
ending — Slack at 10:38am, email at 11:30am, notes written during the meeting. Assume
this is the normal case, not the exception.

Also scan the channel for developments that **postdate the meeting** and are absent
from both the Zoom recap and the notes. On 2026-08-27 a 12:03pm post reported that
the Tax Review Commission chair had called and invited the coalition to their Sept. 1
meeting — a time-sensitive item no other source captured. Surface these; they are
often more valuable than anything in the recap.

## Step 1 — Pull the Zoom email

Search Gmail: `https://mail.google.com/mail/u/0/#search/Meeting+assets+for+Tax+Fairness+Coalition`

Sort by date and open the most recent one — there are many, going back years, and
Gmail's "most relevant" ordering does not reliably put the newest first. Confirm the
date before using it.

Click the row, then `get_page_text`. Gmail renders normally, so page text works.
Long recaps end with `[Message clipped] View entire message` — click that link and
re-read if the Next Steps section looks truncated.

Extract:
- **Quick recap** (one paragraph)
- **Next steps**, grouped by owner and by "Collaboration" (working-group) items
- **Summary** — the per-topic sections, which carry the specifics (dollar figures,
  who said what) that the next-steps list drops

Strip the `https://tasks.zoom.us?...` URLs appended to every action item.

## Step 2 — Read the notes doc

**Do not use `/edit`** — Google Docs renders to canvas and `get_page_text` returns
only chrome, no body text. **Do not `fetch()` the export endpoint** — CSP blocks it.

Use the mobile view, which renders real HTML:

```
https://docs.google.com/document/d/1eQpkFh1GB0MswSyUuHscYRTx8f3Cy1IqylBW6DIZ8hg/mobilebasic?tab=t.xu3k0yc1qkmq
```

Then `get_page_text`. Output is ~50KB and will be persisted to a file — read the
relevant slice with `python3` rather than pulling it all into context.

Meeting sections are reverse-chronological, headed by date (`Aug. 27`, `August 13`).
The current meeting is the first one after the standing header (Working Groups and
Roles / Quick links).

## Step 3 — Diff

Compare the Zoom recap against the existing section for this meeting. Classify each
Zoom item as:

- **Present** — already in the notes, no action
- **Partially present** — notes have the topic but miss an owner, a number, a
  deadline, or a caveat. These are the highest-value additions.
- **Missing** — absent entirely

Pay particular attention to, because these are what the notes routinely drop:
- **Dollar figures and cost analyses**
- **Owners** on action items the notes leave unassigned
- **Decisions about process** (e.g. consensus vs. voting)
- **Dissent and caveats** — someone objecting to framing, or "no consensus reached"
- **Newly formed committees or groups**

Present the diff as a table. Ask which items to add. Do **not** apply edits to the
doc unsolicited — it is a live shared coalition document.

### Date sanity check

Two checks, in order:

1. **Internal consistency** — every weekday-plus-date pair must agree
   (`date -j -f "%Y-%m-%d" 2026-09-07 "+%A"`).
2. **Against the calendar** — look up the working-group meetings on Google Calendar
   and confirm the next-steps dates match the real events.

Working-group meeting dates in this doc have been wrong before. On Aug 27 the notes
and the sent coalition email both said the WG meetings were "Thursday 9/7"; 9/7/2026
is a Monday, and Calendar showed both meetings on **Thursday Sept 3** (Comms 9am,
Policy 2pm). Flag mismatches prominently — this reached the whole list before it was
caught.

## Step 4 — Stage the Slack post

Slack goes through `slack.py` in this skill's directory, using Devin's existing
`xoxp` user token. **Do not use the bundled `plugin:engineering:slack` MCP server** —
it is an inline plugin that only exists inside the Claude Code app, it is
unauthenticated, and it cannot be authorized from a terminal `/mcp` session.

First, read the channel so the post isn't a duplicate:

```bash
python3 ~/.claude/skills/tax-fairness-notes/slack.py read --limit 30
```

If Devin (or anyone) already posted a recap since the meeting ended, say so and do
not stage another.

Then draft. `#tax-fairness` is internal, so it can be tighter and more informal than
the email — lead with the next steps, skip the narrative recap. Print it in a fenced
block.

Granted scopes as of 2026-08-27: `channels:read`, `channels:history`, `users:read`,
`chat:write`. Posting works. (`groups:read` is still absent, so private channels
can't be enumerated — irrelevant for `#tax-fairness`, which is public.)

**Always `preview` before `post`.** An ephemeral message shows Devin the exact
rendering — bullets, bold, link unfurling — visible only to him and never written to
channel history:

```bash
python3 ~/.claude/skills/tax-fairness-notes/slack.py preview --text "..."
```

This is the right way to get approval on Slack formatting: he sees the real thing
rather than a fenced block, and a rejected draft leaves no trace. Preview is safe to
run unattended; it is not a post.

Posting requires explicit approval in chat, and the script enforces it:

```bash
python3 ~/.claude/skills/tax-fairness-notes/slack.py post \
  --text "..." --i-have-approval
```

Without `--i-have-approval` the script refuses. Do not pass that flag unless Devin
has approved the exact text in this conversation. A scheduled run must never pass it.

Channel `#tax-fairness` resolves to `C09RJS3FTFY` — public, `is_shared: true` (a
Slack Connect channel), 20 members, bot already a member.

### If the token is missing

`slack.py` looks in `$SLACK_USER_TOKEN`, then `~/.openclaw/secrets.env`, then
`~/.slack_user_token`. The canonical copy lives on **madison**, which as of
2026-08-27 had been offline for 33 days — so the laptop fallback
`~/.slack_user_token` is the working path. Required scopes (already granted on the
existing app): `channels:read groups:read channels:history groups:history chat:write
users:read`.

Report the missing token and continue with the rest of the write-up; do not treat it
as fatal.

## Step 5 — Stage the coalition email draft

Match Devin's established format exactly. His actual sent message:

> Subject: **Updates from today's Tax Fairness meeting**
>
> Hi everyone,
>
> Here are the next steps from today's meeting. You can find links to the coalition
> charter, op-ed, and survey results in the notes document.
>
> - Reach out to Rep. Iwamoto re: GET on empty homes (Devin)
> - Reach out to Rep. Hussey on the renewable energy tax credit (Devin or Will W.)
> - Provide feedback on coalition charter and op-ed
> - Stay tuned for invitations to the workshop on renewable energy and equity
> - Working groups
>   - Policy working group will continue to hone the list of priorities before
>     presenting to the coalition (next meeting Thursday 9/7 at 2 pm)
>   - Communications working group will discuss messaging guide adjustments
> - Plan a campaign launch event for the week of December 7
>
> Mahalo,
> Devin

Notes on the style:
- Short. Next steps only — no recap paragraph, no attendee list, no discussion detail.
- Owner in parentheses after the item, only when a person is named.
- Working groups nested under a "Working groups" line, each with its next meeting time.
- "Mahalo, Devin" sign-off; the Appleseed signature block appends automatically.
- Plain phrasing, no exhortation. Don't editorialize or add urgency the meeting didn't have.

Create it as a **draft** in Gmail. Do not click Send. Confirm the draft exists and
give Devin the link.

### Composing the draft without mangling the signature

Devin's signature is pre-inserted into the body, and naive approaches all corrupt it
(verified 2026-08-27, three separate failures):

- Clicking body coordinates → text lands mid-signature
  (`Pronouns: he/him/his` + body text spliced together)
- Clicking the `Message Body` **ref** → same problem; the ref targets the whole
  contenteditable, so the caret lands inside the signature
- `cmd+Up` to jump to the top → moves focus out of the body entirely, text is lost
- Inserting before `.gmail_signature` → lands *after* the `--` separator, which
  lives outside that element

What works: insert a fresh `div` as the body's **first child** and place the caret
there, then type normally.

```javascript
const subj = document.querySelector('input[name="subjectbox"]');
const body = document.querySelector('div[aria-label="Message Body"]');
const setter = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype, 'value').set;
setter.call(subj, 'Updates from today\'s Tax Fairness meeting');
subj.dispatchEvent(new Event('input', {bubbles: true}));

const p = document.createElement('div');
p.appendChild(document.createElement('br'));
body.insertBefore(p, body.firstChild);   // FIRST CHILD, not before .gmail_signature
body.focus();
const r = document.createRange();
r.setStart(p, 0); r.collapse(true);
const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
```

Then use `computer` `type` for the body text. Always screenshot afterward to confirm
the signature is intact below a `--` separator. To throw away a bad attempt, press
`cmd+shift+d` (discard) — do **not** leave half-built drafts behind.

## Step 6 — Report

State clearly:
- What was already done before the skill ran
- Which notes additions are proposed (and apply only those approved)
- That the Slack post is unposted and the email is an unsent draft
- Any contradictions between the Zoom recap and the notes, unresolved
