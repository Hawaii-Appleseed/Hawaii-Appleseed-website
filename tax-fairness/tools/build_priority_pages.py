# Generates the three 2027 priority page files (capital_gains / tax_credits / conveyance_tax _squarespace.html).
# Run: python3 tax-fairness/tools/build_priority_pages.py   Then paste each output file into its page's Code Block.
import sys
import os
import re
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..") + os.sep

CSS = """<style>
.tfc-pp {
    --tfc-navy: #253551;
    --tfc-blue: #3c73b9;
    --tfc-muted: #4a5568;
    --tfc-line: #dfe3ea;
    --tfc-soft: #f5f7fa;
    container-type: inline-size;
    width: 100%;
    margin: 0 0 40px;
    font-family: var(--body-font-font-family), sans-serif;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--tfc-navy);
}
.tfc-pp *, .tfc-pp *::before, .tfc-pp *::after { box-sizing: border-box; }
.tfc-pp h1, .tfc-pp h2, .tfc-pp h3 {
    font-family: var(--heading-font-font-family), sans-serif;
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    color: var(--tfc-navy);
}
.tfc-pp a.tfc-btn { display: inline-block; text-decoration: none; }
.tfc-pp-eyebrow {
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    background: var(--tfc-blue); color: #fff; font-size: .72rem; font-weight: 700;
    line-height: 1.4; letter-spacing: .06em; text-transform: uppercase;
}
.tfc-pp-hero { margin: 0 0 40px; padding: 0 0 36px; border-bottom: 1px solid var(--tfc-line); }
.tfc-pp .tfc-pp-title { max-width: 26ch; font-size: 3.2rem; line-height: 1.08; margin: 16px 0 18px; }
.tfc-pp-ask { max-width: 64rem; margin: 0 0 14px; font-size: 1.3rem; line-height: 1.4; font-weight: 600; }
.tfc-pp-lede { max-width: 64rem; margin: 0; font-size: 1.05rem; color: var(--tfc-muted); }

.tfc-pp-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin: 0 0 56px; }
.tfc-pp-stat { padding: 24px 24px 22px; border: 1px solid var(--tfc-line); border-top: 4px solid var(--tfc-blue); border-radius: 10px; background: #fff; box-shadow: 0 1px 2px rgba(37, 53, 81, .06), 0 6px 18px rgba(37, 53, 81, .05); }
.tfc-pp-stat-num {
    font-family: var(--heading-font-font-family), sans-serif; font-weight: 700;
    font-size: 2.5rem; line-height: 1.05; color: var(--tfc-navy);
}
.tfc-pp-stat-label { margin: 8px 0 0; font-size: .95rem; color: var(--tfc-muted); }

.tfc-pp-section { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 9fr); column-gap: 48px; margin: 0 0 44px; }
.tfc-pp-section > * { grid-column: 2; max-width: 56rem; }
.tfc-pp-section > h2 { grid-column: 1; }
.tfc-pp .tfc-pp-section h2 { max-width: none; font-size: 1.55rem; line-height: 1.2; margin: 0; padding-top: 4px; border-top: 3px solid var(--tfc-blue); padding-top: 14px; align-self: start; }
.tfc-pp-section p { margin: 0 0 14px; font-size: 1.05rem; }
.tfc-pp-section ul { margin: 0 0 14px; padding: 0 0 0 20px; list-style: disc; }
.tfc-pp-section li { margin: 0 0 8px; font-size: 1.05rem; }
.tfc-pp-source { font-size: .85rem !important; color: var(--tfc-muted); }

.tfc-pp-bars { margin: 0 0 16px; padding: 0; list-style: none; }
.tfc-pp-bars li { display: grid; grid-template-columns: 170px minmax(0, 1fr) 56px; align-items: center; gap: 12px; margin: 0 0 10px; font-size: .95rem; }
.tfc-pp-bar { height: 22px; border-radius: 5px; background: var(--tfc-navy); }
.tfc-pp-bar.alt { background: var(--tfc-blue); }
.tfc-pp-bars b { text-align: right; }

.tfc-pp-fig { margin: 0 0 28px; padding: 30px 34px; border: 1px solid var(--tfc-line); border-radius: 12px; background: #fff; box-shadow: 0 1px 2px rgba(37, 53, 81, .06), 0 8px 24px rgba(37, 53, 81, .06); }
.tfc-pp .tfc-pp-fig h3 { margin: 0 0 4px; font-size: 1.15rem; line-height: 1.3; font-weight: 700; }
.tfc-pp-fig-sub { max-width: 64rem; margin: 0 0 24px; font-size: .92rem; color: var(--tfc-muted); }
.tfc-pp-fig-note { margin: 18px 0 0; padding-top: 12px; border-top: 1px solid var(--tfc-line); font-size: .82rem; color: var(--tfc-muted); }
.tfc-pp-hb { display: grid; grid-template-columns: 200px minmax(0, 1fr) 64px; align-items: center; gap: 12px; margin: 0 0 12px; }
.tfc-pp-hb-lbl { font-size: .95rem; line-height: 1.3; }
.tfc-pp-hb-lbl small { display: block; font-size: .8rem; color: var(--tfc-muted); }
.tfc-pp-track { height: 28px; border-radius: 6px; overflow: hidden; background: var(--tfc-soft); }
.tfc-pp-track i { display: block; height: 100%; min-width: 3px; border-radius: 6px; background: var(--tfc-navy); opacity: .55; }
.tfc-pp-hb.hi .tfc-pp-track i { background: var(--tfc-blue); opacity: 1; }
.tfc-pp-hb b { text-align: right; font-size: .98rem; }
.tfc-pp-tablewrap { overflow-x: auto; }
.tfc-pp-table { width: 100%; border-collapse: collapse; font-size: .95rem; }
.tfc-pp-table th { padding: 8px 10px; border-bottom: 2px solid var(--tfc-navy); text-align: right; font-size: .8rem; font-weight: 700; line-height: 1.3; color: var(--tfc-muted); }
.tfc-pp-table td { padding: 10px; border-bottom: 1px solid var(--tfc-line); text-align: right; font-variant-numeric: tabular-nums; }
.tfc-pp-table th:first-child, .tfc-pp-table td:first-child { padding-left: 0; text-align: left; }
.tfc-pp-table th small { display: block; font-weight: 400; }
.tfc-pp-table td:first-child small { display: block; font-size: .8rem; color: var(--tfc-muted); }
.tfc-pp-table tr.hi td { font-weight: 700; color: var(--tfc-navy); background: var(--tfc-soft); }
.tfc-pp-table tr.tot td { border-bottom: 0; font-weight: 700; }
.tfc-pp-stack { display: grid; grid-template-columns: 70px minmax(0, 1fr) 64px; align-items: center; gap: 12px; margin: 0 0 12px; }
.tfc-pp-stack-bar { display: flex; gap: 2px; height: 34px; }
.tfc-pp-stack-bar i { display: block; height: 100%; border-radius: 3px; background: var(--tfc-navy); opacity: .55; }
.tfc-pp-stack-bar i.hi { background: var(--tfc-blue); opacity: 1; }
.tfc-pp-stack-bar i.mid { background: #c3cad6; opacity: 1; }
.tfc-pp-legend span.mid { background: #c3cad6; opacity: 1; }
.tfc-pp-legend { display: flex; flex-wrap: wrap; gap: 6px 20px; margin: 4px 0 0; padding: 0; list-style: none; font-size: .88rem; }
.tfc-pp-legend span { display: inline-block; width: 12px; height: 12px; margin-right: 6px; border-radius: 2px; background: var(--tfc-navy); opacity: .55; vertical-align: -1px; }
.tfc-pp-legend span.hi { background: var(--tfc-blue); opacity: 1; }
@container (max-width: 420px) {
    .tfc-pp-table { font-size: .8rem; }
    .tfc-pp-table th { font-size: .7rem; padding-left: 3px; padding-right: 3px; }
    .tfc-pp-table td { padding: 8px 3px; }
    .tfc-pp-fig { padding: 20px 12px; }
}
.tfc-pp-steps { margin: 0 0 14px; padding: 0; list-style: none; border-left: 3px solid var(--tfc-line); }
.tfc-pp-steps li { position: relative; margin: 0; padding: 0 0 16px 20px; font-size: 1.02rem; }
.tfc-pp-steps li::before { content: ""; position: absolute; left: -9px; top: 7px; width: 15px; height: 15px; border-radius: 50%; background: #fff; border: 3px solid var(--tfc-blue); }
.tfc-pp-steps li.end::before { background: var(--tfc-navy); border-color: var(--tfc-navy); }
.tfc-pp-steps b { display: block; color: var(--tfc-navy); }

.tfc-pp-cta {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
    gap: 20px 32px; margin: 56px 0 0; padding: 40px 44px; border-radius: 12px;
    background: var(--tfc-navy); color: #fff;
}
.tfc-pp .tfc-pp-cta h2 { margin: 0 0 4px; font-size: 1.6rem; line-height: 1.2; color: #fff; }
.tfc-pp-cta p { margin: 0; color: rgba(255, 255, 255, .85); }
.tfc-pp-cta-links { display: flex; flex-wrap: wrap; gap: 12px; }
.tfc-pp-more { margin: 32px 0 0; padding: 20px 0 0; border-top: 1px solid var(--tfc-line); font-size: .98rem; color: var(--tfc-muted); }
.tfc-pp-more a { color: #2f62a3; }

body:not(.sqs-is-page-editing) .fluid-engine:has(> .fe-block .tfc-pp) { grid-template-rows: auto !important; }
body:not(.sqs-is-page-editing) .fe-block:has(.tfc-pp) { grid-row: 1 / 2 !important; }
@media (min-width: 768px) { body:not(.sqs-is-page-editing) .fe-block:has(.tfc-pp) { grid-column: 2 / 26 !important; } }
@media (max-width: 767px) { body:not(.sqs-is-page-editing) .fe-block:has(.tfc-pp) { grid-column: 2 / 10 !important; } }

@container (max-width: 760px) {
    .tfc-pp .tfc-pp-title { max-width: none; font-size: 2.15rem; }
    .tfc-pp-ask { font-size: 1.15rem; }
    .tfc-pp-section { display: block; margin-bottom: 36px; }
    .tfc-pp-section > * { max-width: none; }
    .tfc-pp .tfc-pp-section h2 { margin-bottom: 14px; }
    .tfc-pp-stats { margin-bottom: 40px; }
    .tfc-pp-stat-num { font-size: 2.2rem; }
    .tfc-pp-stats { grid-template-columns: minmax(0, 1fr); }
    .tfc-pp-fig { padding: 22px 16px; }
    .tfc-pp-hb { grid-template-columns: minmax(0, 1fr) 56px; gap: 4px 10px; margin-bottom: 16px; }
    .tfc-pp-hb-lbl { grid-column: 1 / -1; }
    .tfc-pp-stack { grid-template-columns: minmax(0, 1fr) 56px; gap: 4px 10px; }
    .tfc-pp-stack > span:first-child { grid-column: 1 / -1; font-weight: 700; }
    .tfc-pp-table { font-size: .88rem; }
    .tfc-pp-table td:first-child small { font-size: .74rem; }
    .tfc-pp-table.hide2 th:nth-child(2), .tfc-pp-table.hide2 td:nth-child(2) { display: none; }
    .tfc-pp-table th, .tfc-pp-table td { padding-left: 6px; padding-right: 6px; }
    .tfc-pp-bars li { grid-template-columns: minmax(0, 1fr) 56px; }
    .tfc-pp-bars li span { grid-column: 1 / -1; }
    .tfc-pp-bars li .tfc-pp-bar { grid-column: 1; }
    .tfc-pp .tfc-pp-section h2 { font-size: 1.45rem; }
    .tfc-pp-cta { padding: 28px 22px; margin-top: 40px; }
}
</style>"""


# ===== "Chapters" layout: pale-sky hero flush under the header, a band per section, cards for the figures =====
# Applied to all three priority pages (root class tfc-pp-ch). Page-specific bits hang off tfc-pp-cg / -cr / -cv.
CHAPTERS = """
/* ===== Chapters layout: pale-sky hero, a band per section, cards for the figures ===== */
body:not(.sqs-is-page-editing) section.page-section:has(.tfc-pp-ch) .content-wrapper { padding-top: 0 !important; padding-bottom: 0 !important; }
.tfc-pp-ch { --tfc-deep: #16223a; --tfc-sky: #e2eefb; --tfc-pale: #eaf1fa; --tfc-amber: #f5a524; --tfc-mute: #46536b; --tfc-ink: #1c2740; margin: 0; }

/* hero: pale-sky band flush under the header; ask and intro sit beside the title */
.tfc-pp-ch .tfc-pp-hero { display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 5fr); column-gap: 80px; align-items: start; margin: 0; padding: 60px 0 180px; border: 0; background: var(--tfc-sky); box-shadow: 0 0 0 100vmax var(--tfc-sky); clip-path: inset(0 -100vmax); }
.tfc-pp-ch .tfc-pp-eyebrow { grid-column: 1 / -1; justify-self: start; margin-bottom: 6px; padding: 5px 14px; border: 1px solid var(--tfc-navy); background: var(--tfc-navy); color: #fff; font-size: .8rem; font-weight: 600; letter-spacing: .02em; text-transform: none; }
.tfc-pp-ch .tfc-pp-title { grid-column: 1; grid-row: 2 / 4; max-width: 15ch; margin: 22px 0 0; font-size: clamp(2.4rem, 5.2cqi, 4.3rem); line-height: 1.02; letter-spacing: -.012em; color: var(--tfc-deep); }
.tfc-pp-ch .tfc-pp-ask { grid-column: 2; grid-row: 2; max-width: 30ch; margin: 34px 0 14px; font-size: 1.45rem; font-weight: 600; color: var(--tfc-deep); }
.tfc-pp-ch .tfc-pp-lede { grid-column: 2; grid-row: 3; max-width: 46ch; margin: 0; font-size: 1.1rem; color: #3d4c68; }

/* stat cards overlap the hero; the last one is a deeper sky tint */
.tfc-pp-ch .tfc-pp-stats { position: relative; z-index: 2; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; margin: -104px 0 0; }
.tfc-pp-ch .tfc-pp-stat { padding: 38px 42px 36px; border: 0; border-radius: 24px; background: #fff; box-shadow: 0 26px 50px -26px rgba(37, 53, 81, .35), 0 2px 6px rgba(37, 53, 81, .08); }
.tfc-pp-ch .tfc-pp-stat-num { font-size: clamp(2.4rem, 4.4cqi, 3.6rem); line-height: 1; letter-spacing: -.025em; }
.tfc-pp-ch .tfc-pp-stat-label { max-width: 34ch; margin: 14px 0 0; font-size: 1.1rem; line-height: 1.45; color: var(--tfc-mute); }
.tfc-pp-ch .tfc-pp-stat:last-child { display: flex; flex-direction: column; justify-content: center; background: linear-gradient(160deg, #cfe3f9 0%, #b9d5f3 100%); }
.tfc-pp-ch .tfc-pp-stat:last-child .tfc-pp-stat-label { color: #2f3f5c; }

/* sections: the heading sits above its content; text and figures are cards on a 12-column grid */
.tfc-pp-ch .tfc-pp-section { display: block; margin: 0; padding: 88px 0; }
.tfc-pp-ch .tfc-pp-section > * { max-width: none; }
.tfc-pp-ch .tfc-pp-section h2 { margin: 0 0 36px; padding: 0; border: 0; font-size: clamp(2rem, 3.4cqi, 2.9rem); line-height: 1.05; font-weight: 600; letter-spacing: -.02em; color: var(--tfc-deep); }
.tfc-pp-ch .tfc-pp-section:not(.tfc-pp-part-ask) h2::after { content: ""; display: block; width: 56px; height: 6px; margin-top: 16px; border-radius: 3px; background: var(--tfc-amber); }
.tfc-pp-ch h1, .tfc-pp-ch h2, .tfc-pp-ch h3, .tfc-pp-ch .tfc-pp-facts > li strong, .tfc-pp-ch .tfc-pp-card--stat strong, .tfc-pp-ch .tfc-pp-part-ask > p { text-wrap: balance; }
.tfc-pp-ch .tfc-pp-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 24px; }
.tfc-pp-ch .tfc-pp-grid > * { grid-column: span 12; min-width: 0; }
.tfc-pp-ch .tfc-pp-w4 { grid-column: span 4; }
.tfc-pp-ch .tfc-pp-w5 { grid-column: span 5; }
.tfc-pp-ch .tfc-pp-w6 { grid-column: span 6; }
.tfc-pp-ch .tfc-pp-w7 { grid-column: span 7; }
.tfc-pp-ch .tfc-pp-w8 { grid-column: span 8; }
.tfc-pp-ch .tfc-pp-r2 { grid-row: span 2; }
.tfc-pp-ch .tfc-pp-part-tint { background: var(--tfc-pale); box-shadow: 0 0 0 100vmax var(--tfc-pale); clip-path: inset(0 -100vmax); }

/* text cards: tinted on white bands, white on pale ones */
.tfc-pp-ch .tfc-pp-card { margin: 0; padding: 36px 40px; border: 1px solid #e1eaf5; border-radius: 24px; background: #f3f7fd; font-size: 1.1rem; line-height: 1.65; color: #3d4c68; }
.tfc-pp-ch .tfc-pp-part-tint .tfc-pp-card { border-color: #d6e2f2; background: #fff; }
.tfc-pp-ch .tfc-pp-card > p { margin: 0 0 14px; font-size: inherit; line-height: inherit; text-wrap: pretty; }
.tfc-pp-ch .tfc-pp-card > p:last-child { margin-bottom: 0; }
.tfc-pp-ch .tfc-pp-card strong { color: var(--tfc-navy); }
.tfc-pp-ch .tfc-pp-card > .tfc-pp-source { margin: 22px 0 0; padding-top: 16px; border-top: 1px solid #d6e2f2; line-height: 1.55; }
.tfc-pp-ch .tfc-pp-card--lead { font-size: clamp(1.25rem, 2.1cqi, 1.5rem); line-height: 1.5; color: var(--tfc-navy); }
.tfc-pp-ch .tfc-pp-card--alert { display: flex; align-items: center; border-color: #f2d9a6; background: #fff3d9; font-size: 1.35rem; font-weight: 600; line-height: 1.35; color: var(--tfc-deep); }
.tfc-pp-ch .tfc-pp-card--stat { display: flex; flex-direction: column; justify-content: center; border-color: #b9d5f3; background: linear-gradient(160deg, #cfe3f9 0%, #b9d5f3 100%); color: #2f3f5c; }
.tfc-pp-ch .tfc-pp-card--stat strong { display: block; margin: 6px 0; font-size: clamp(1.9rem, 3.2cqi, 2.7rem); line-height: 1.05; letter-spacing: -.02em; color: var(--tfc-navy); }

/* text style: the first sentence of a text card leads in bold, and dollar amounts and percentages stand out */
.tfc-pp-ch .tfc-pp-first { font-weight: 700; color: var(--tfc-navy); }
.tfc-pp-ch .tfc-pp-num { font-weight: 700; color: #2f62a3; white-space: nowrap; }

/* a short row of facts (three cards) */
.tfc-pp-ch .tfc-pp-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; margin: 0; padding: 0; list-style: none; }
.tfc-pp-ch .tfc-pp-facts > li { margin: 0; padding: 34px 36px; border: 1px solid #d6e2f2; border-radius: 24px; background: #fff; font-size: 1.1rem; line-height: 1.55; color: #3d4c68; }
.tfc-pp-ch .tfc-pp-facts > li strong { display: block; margin: 8px 0; font-size: clamp(1.8rem, 3cqi, 2.4rem); line-height: 1.1; letter-spacing: -.015em; font-weight: 700; color: var(--tfc-navy); }

/* ask: brand-blue band; the label sits above one big statement, or above a row of cards */
.tfc-pp-ch .tfc-pp-part-ask { background: var(--tfc-blue); box-shadow: 0 0 0 100vmax var(--tfc-blue); clip-path: inset(0 -100vmax); }
.tfc-pp-ch .tfc-pp-part-ask h2 { display: flex; align-items: center; gap: 14px; margin: 0 0 24px; font-size: 1.15rem; font-weight: 600; letter-spacing: 0; color: #fff; }
.tfc-pp-ch .tfc-pp-part-ask h2::before { content: ""; width: 28px; height: 4px; border-radius: 2px; background: var(--tfc-amber); }
.tfc-pp-ch .tfc-pp-part-ask > p { max-width: 34ch; margin: 0; font-size: clamp(1.8rem, 3.6cqi, 2.8rem); line-height: 1.2; font-weight: 400; letter-spacing: -.012em; color: #fff; }
.tfc-pp-ch .tfc-pp-asks { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; margin: 0; padding: 0; list-style: none; }
.tfc-pp-ch .tfc-pp-asks > li { margin: 0; padding: 32px 34px; border-top: 5px solid var(--tfc-amber); border-radius: 24px; background: #fff; font-size: 1.1rem; line-height: 1.55; color: #3d4c68; }
.tfc-pp-ch .tfc-pp-asks > li strong { color: var(--tfc-navy); font-weight: 600; }

/* figures: cards (a figure inside a section keeps its own text styles, not the section's paragraph and list styles) */
.tfc-pp-ch .tfc-pp-section .tfc-pp-fig-sub { max-width: 64rem; margin: 0 0 24px; font-size: .95rem; line-height: 1.6; color: var(--tfc-mute); }
.tfc-pp-ch .tfc-pp-section .tfc-pp-fig-note { margin: 18px 0 0; padding-top: 12px; font-size: .82rem; line-height: 1.6; color: var(--tfc-mute); }
.tfc-pp-ch .tfc-pp-section .tfc-pp-legend { margin: 4px 0 0; padding: 0; list-style: none; font-size: .88rem; }
.tfc-pp-ch .tfc-pp-section .tfc-pp-legend li { margin: 0; font-size: .88rem; }
.tfc-pp-ch .tfc-pp-fig { display: flex; flex-direction: column; align-self: start; }
.tfc-pp-ch .tfc-pp-fig > .tfc-pp-fig-note { margin-top: auto; }
.tfc-pp-ch .tfc-pp-fig > :nth-last-child(2) { margin-bottom: 18px; }
.tfc-pp-ch .tfc-pp-figs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px; padding: 104px 0 28px; }
.tfc-pp-ch .tfc-pp-fig { margin: 0; padding: 38px 42px; border: 1px solid #dbe4f0; border-radius: 24px; background: #fff; box-shadow: none; }
.tfc-pp-ch .tfc-pp-fig h3 { margin: 0 0 6px; font-size: 1.5rem; line-height: 1.3; font-weight: 600; letter-spacing: -.01em; }
.tfc-pp-ch .tfc-pp-fig-sub { font-size: .95rem; }
.tfc-pp-ch .tfc-pp-track { height: 22px; border-radius: 999px; background: #edf2f9; }
.tfc-pp-ch .tfc-pp-track i { border-radius: 999px; opacity: 1; background: #b6cbe8; }
.tfc-pp-ch .tfc-pp-hb.hi .tfc-pp-track i { background: linear-gradient(90deg, #3c73b9, #5f98da); }
.tfc-pp-ch .tfc-pp-table th { border-bottom: 1.5px solid var(--tfc-navy); }
.tfc-pp-ch .tfc-pp-table tr.hi td { background: #f1f6fc; }
.tfc-pp-ch .tfc-pp-part-src { display: block; padding: 8px 0 64px; }
.tfc-pp-ch .tfc-pp-part-src > .tfc-pp-source { max-width: 56rem; margin: 0 0 14px; }

/* agenda, call to action, links to the other priorities */
.tfc-pp-ch .tfc-pp-part-agenda { padding: 24px 0 72px; }
.tfc-pp-ch .tfc-pp-part-agenda h2 { font-size: 1.9rem; }
.tfc-pp-ch .tfc-pp-cta { margin: 16px 0 0; padding: 68px; border-radius: 28px; background: linear-gradient(120deg, #3c73b9 0%, #2f62a3 100%); }
.tfc-pp-ch .tfc-pp-cta h2 { font-size: 2.3rem; line-height: 1.1; letter-spacing: -.012em; }
.tfc-pp-ch .tfc-pp-cta p { font-size: 1.1rem; color: #fff; }
.tfc-pp-ch .tfc-pp-cta a.tfc-btn.sqs-button-element--primary { border-color: var(--tfc-amber) !important; border-radius: 999px !important; background: var(--tfc-amber) !important; color: var(--tfc-deep) !important; }
.tfc-pp-ch .tfc-pp-cta a.tfc-btn.sqs-button-element--secondary { border: 1.5px solid rgba(255, 255, 255, .55) !important; border-radius: 999px !important; background: transparent !important; color: #fff !important; }
.tfc-pp-ch .tfc-pp-more { margin: 0; padding: 64px 0 88px; border: 0; }
.tfc-pp-ch .tfc-pp-more-title { margin: 0 0 18px; font-size: 1.1rem; font-weight: 600; color: var(--tfc-mute); }
.tfc-pp-ch .tfc-pp-more-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.tfc-pp-ch .tfc-pp-more-card { display: block; padding: 26px 30px; border: 1px solid #dbe4f0; border-radius: 20px; background: #f3f7fd; color: var(--tfc-navy); text-decoration: none; }
.tfc-pp-ch .tfc-pp-more-card:hover { border-color: var(--tfc-blue); background: #fff; }
.tfc-pp-ch .tfc-pp-more-card:focus-visible, .tfc-pp-ch .tfc-pp-more-all:focus-visible { outline: 3px solid var(--tfc-blue); outline-offset: 3px; }
.tfc-pp-ch .tfc-pp-more-card span { display: block; margin-bottom: 6px; font-size: .85rem; color: var(--tfc-mute); }
.tfc-pp-ch .tfc-pp-more-card b { display: block; font-size: 1.25rem; font-weight: 600; line-height: 1.3; }
.tfc-pp-ch .tfc-pp-more-all { display: inline-block; margin-top: 20px; font-weight: 600; color: #2f62a3; }

/* narrower containers */
@container (max-width: 1100px) {
    .tfc-pp-ch .tfc-pp-figs { grid-template-columns: minmax(0, 1fr); }
    .tfc-pp-ch:not(.tfc-pp-cr) .tfc-pp-stat { padding: 32px 30px 30px; }
    .tfc-pp-ch .tfc-pp-card { padding: 30px 32px; }
}
@container (max-width: 900px) {
    .tfc-pp-ch .tfc-pp-hero { grid-template-columns: minmax(0, 1fr); padding: 48px 0 150px; }
    .tfc-pp-ch .tfc-pp-title, .tfc-pp-ch .tfc-pp-ask, .tfc-pp-ch .tfc-pp-lede { grid-column: 1; grid-row: auto; }
    .tfc-pp-ch .tfc-pp-title { margin: 20px 0 0; }
    .tfc-pp-ch .tfc-pp-ask { max-width: 36ch; margin: 22px 0 12px; }
    .tfc-pp-ch .tfc-pp-lede { max-width: 56ch; }
    .tfc-pp-ch .tfc-pp-stats { margin-top: -96px; }
    .tfc-pp-ch:not(.tfc-pp-cr) .tfc-pp-stats { grid-template-columns: minmax(0, 1fr); gap: 16px; }
    .tfc-pp-ch .tfc-pp-section { padding: 64px 0; }
    .tfc-pp-ch .tfc-pp-section h2 { margin-bottom: 26px; font-size: 1.9rem; }
    .tfc-pp-ch .tfc-pp-grid { grid-template-columns: minmax(0, 1fr); gap: 18px; }
    .tfc-pp-ch .tfc-pp-grid > * { grid-column: 1 / -1; grid-row: auto; }
    .tfc-pp-ch .tfc-pp-facts, .tfc-pp-ch .tfc-pp-asks { grid-template-columns: minmax(0, 1fr); gap: 16px; }
    .tfc-pp-ch .tfc-pp-part-ask h2 { margin-bottom: 18px; font-size: 1.1rem; }
    .tfc-pp-ch .tfc-pp-figs { padding-top: 64px; }
    .tfc-pp-ch .tfc-pp-part-agenda { padding: 8px 0 56px; }
    .tfc-pp-ch .tfc-pp-cta { padding: 48px 40px; }
    .tfc-pp-ch .tfc-pp-more-cards { grid-template-columns: minmax(0, 1fr); gap: 14px; }
}
@container (max-width: 760px) {
    .tfc-pp-ch .tfc-pp-fig { padding: 28px 22px; border-radius: 20px; }
}
@container (max-width: 560px) {
    .tfc-pp-ch .tfc-pp-hero { padding: 36px 0 128px; }
    .tfc-pp-ch .tfc-pp-title { font-size: 2.3rem; }
    .tfc-pp-ch .tfc-pp-ask { font-size: 1.2rem; }
    .tfc-pp-ch .tfc-pp-lede { font-size: 1rem; }
    .tfc-pp-ch .tfc-pp-stats { margin-top: -88px; }
    .tfc-pp-ch .tfc-pp-stat { padding: 26px 24px; border-radius: 20px; }
    .tfc-pp-ch .tfc-pp-stat-label { font-size: 1rem; }
    .tfc-pp-ch .tfc-pp-section { padding: 56px 0; }
    .tfc-pp-ch .tfc-pp-section h2 { font-size: 1.7rem; }
    .tfc-pp-ch .tfc-pp-section:not(.tfc-pp-part-ask) h2::after { width: 44px; height: 5px; margin-top: 12px; }
    .tfc-pp-ch .tfc-pp-card { padding: 26px 24px; border-radius: 20px; }
    .tfc-pp-ch .tfc-pp-part-ask h2 { font-size: 1.05rem; }
    .tfc-pp-ch .tfc-pp-card--lead { font-size: 1.1rem; }
    .tfc-pp-ch .tfc-pp-card--alert { font-size: 1.15rem; }
    .tfc-pp-ch .tfc-pp-facts > li, .tfc-pp-ch .tfc-pp-asks > li { padding: 26px 24px; border-radius: 20px; }
    .tfc-pp-ch .tfc-pp-fig { padding: 24px 16px; }
    .tfc-pp-ch .tfc-pp-fig h3 { font-size: 1.3rem; }
    .tfc-pp-ch .tfc-pp-cta { padding: 36px 24px; border-radius: 22px; }
    .tfc-pp-ch .tfc-pp-cta h2 { font-size: 1.8rem; }
    .tfc-pp-ch .tfc-pp-more { padding: 48px 0 56px; }
    .tfc-pp-ch .tfc-pp-more-card { padding: 22px 24px; }
}
"""

# Credits page only: 2 stat cards with the credit breakdown bar, the timeline, the table dots.
CR_EXTRA = """
/* ===== Credits page ===== */
.tfc-pp-cr .tfc-pp-stats { grid-template-columns: minmax(0, 7fr) minmax(0, 5fr); }
.tfc-pp-cr .tfc-pp-stat-num { font-size: clamp(2.8rem, 6.2cqi, 4.8rem); }
.tfc-pp-seg { display: flex; gap: 4px; height: 14px; margin: 30px 0 16px; }
.tfc-pp-seg i { display: block; border-radius: 999px; }
.tfc-pp-seg i:nth-child(1), .tfc-pp-seg-key li:nth-child(1) b { background: var(--tfc-navy); }
.tfc-pp-seg i:nth-child(2), .tfc-pp-seg-key li:nth-child(2) b { background: var(--tfc-blue); }
.tfc-pp-seg i:nth-child(3), .tfc-pp-seg-key li:nth-child(3) b { background: var(--tfc-amber); }
.tfc-pp-seg-key { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: 0; padding: 0; list-style: none; }
.tfc-pp-seg-key li { display: flex; align-items: center; gap: 8px; margin: 0; font-size: .92rem; color: var(--tfc-mute); }
.tfc-pp-seg-key b { flex: none; width: 10px; height: 10px; border-radius: 50%; }
.tfc-pp-seg-key em { font-style: normal; font-weight: 700; color: var(--tfc-navy); }
.tfc-pp-cr .tfc-pp-tl { padding: 20px 44px 40px; border: 1px solid #d6e2f2; border-radius: 24px; background: #fff; }
.tfc-pp-cr .tfc-pp-steps { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; border-left: 0; }
.tfc-pp-cr .tfc-pp-steps li { margin: 0; padding: 46px 40px 0 0; font-size: 1.05rem; line-height: 1.5; color: #3d4c68; }
.tfc-pp-cr .tfc-pp-steps li::before { left: 0; top: 0; width: 22px; height: 22px; border: 4px solid var(--tfc-blue); background: #fff; }
.tfc-pp-cr .tfc-pp-steps li::after { content: ""; position: absolute; top: 10px; left: 34px; right: 12px; height: 2px; background: #b3c8e6; }
.tfc-pp-cr .tfc-pp-steps li.end::after { display: none; }
.tfc-pp-cr .tfc-pp-steps li.end::before { background: var(--tfc-amber); border-color: var(--tfc-amber); box-shadow: 0 0 0 8px rgba(245, 165, 36, .3); }
.tfc-pp-cr .tfc-pp-steps b { margin-bottom: 10px; font-size: 1.7rem; line-height: 1.15; font-weight: 600; }
.tfc-pp-cr .tfc-pp-steps li.end { font-weight: 600; color: var(--tfc-ink); }
.tfc-pp-cr .tfc-pp-steps li.end b { color: #9a5a00; }
.tfc-pp-cr .tfc-pp-figs > .tfc-pp-fig:nth-child(3) { grid-column: 1 / -1; }
.tfc-pp-cr .tfc-pp-figs .tfc-pp-fig:nth-child(1) th:first-child { width: 44%; }
.tfc-pp-cr .tfc-pp-figs .tfc-pp-fig:nth-child(1) tbody tr td:first-child::before { content: ""; display: inline-block; width: 10px; height: 10px; margin-right: 10px; border-radius: 50%; }
.tfc-pp-cr .tfc-pp-figs .tfc-pp-fig:nth-child(1) tbody tr:nth-child(1) td:first-child::before { background: var(--tfc-navy); }
.tfc-pp-cr .tfc-pp-figs .tfc-pp-fig:nth-child(1) tbody tr:nth-child(2) td:first-child::before { background: var(--tfc-blue); }
.tfc-pp-cr .tfc-pp-figs .tfc-pp-fig:nth-child(1) tbody tr:nth-child(3) td:first-child::before { background: var(--tfc-amber); }
.tfc-pp-cr .tfc-pp-figs .tfc-pp-fig:nth-child(1) tbody tr.hi td { background: none; font-weight: 400; }
@container (max-width: 900px) {
    .tfc-pp-cr .tfc-pp-tl { padding: 30px 24px 26px; }
    .tfc-pp-cr .tfc-pp-steps { grid-template-columns: minmax(0, 1fr); margin-left: 11px; border-left: 3px solid #b3c8e6; }
    .tfc-pp-cr .tfc-pp-steps li { padding: 0 0 30px 32px; }
    .tfc-pp-cr .tfc-pp-steps li:last-child { padding-bottom: 0; }
    .tfc-pp-cr .tfc-pp-steps li::before { left: -12.5px; top: 2px; }
    .tfc-pp-cr .tfc-pp-steps li::after { display: none; }
    .tfc-pp-cr .tfc-pp-steps b { font-size: 1.45rem; }
}
@container (max-width: 760px) {
    .tfc-pp-cr .tfc-pp-stats { grid-template-columns: minmax(0, 1fr); gap: 16px; }
    .tfc-pp-cr .tfc-pp-stat:last-child { justify-content: flex-start; }
}
@container (max-width: 560px) {
    .tfc-pp-seg { margin: 24px 0 14px; }
}
"""

# Capital gains page only: the rate-comparison card and the figure layout.
CG_EXTRA = """
/* ===== Capital gains page ===== */
.tfc-pp-cg .tfc-pp-figs > .tfc-pp-fig:first-child { grid-column: 1 / -1; }
.tfc-pp-cg .tfc-pp-ratecard { border-color: #dbe4f0; background: #fff; }
.tfc-pp-cg .tfc-pp-ratecard h3 { margin: 0; font-size: 1.3rem; line-height: 1.3; font-weight: 600; letter-spacing: -.01em; color: var(--tfc-navy); }
.tfc-pp-cg .tfc-pp-ratecard > p { margin: 22px 0 0; padding-top: 18px; border-top: 1px solid #e1eaf5; font-size: 1rem; line-height: 1.6; color: var(--tfc-mute); }
.tfc-pp-cg .tfc-pp-bars { max-width: none; margin: 24px 0 4px; padding: 0; list-style: none; }
.tfc-pp-cg .tfc-pp-bars li { grid-template-columns: 170px minmax(0, 1fr) 64px; gap: 16px; margin: 0 0 14px; font-size: 1rem; color: var(--tfc-navy); }
.tfc-pp-cg .tfc-pp-bar { height: 26px; border-radius: 999px; }
.tfc-pp-cg .tfc-pp-bars b { font-size: 1.15rem; }
@container (max-width: 1100px) {
    .tfc-pp-cg .tfc-pp-facts { grid-template-columns: minmax(0, 1fr); gap: 16px; }
}
@container (max-width: 760px) {
    .tfc-pp-cg .tfc-pp-table.hide3 th:nth-child(3), .tfc-pp-cg .tfc-pp-table.hide3 td:nth-child(3) { display: none; }
    .tfc-pp-cg .tfc-pp-bars li { grid-template-columns: minmax(0, 1fr) 60px; gap: 6px 12px; }
    .tfc-pp-cg .tfc-pp-bars li span { grid-column: 1 / -1; }
    .tfc-pp-cg .tfc-pp-bars li .tfc-pp-bar { grid-column: 1; }
}
"""

# Conveyance page only: thicker bars, the three asks stack earlier.
CV_EXTRA = """
/* ===== Conveyance page ===== */
.tfc-pp-cv .tfc-pp-stack-bar { height: 34px; }
.tfc-pp-cv .tfc-pp-stack-bar i { border-radius: 8px; }
@container (max-width: 1100px) {
    .tfc-pp-cv .tfc-pp-asks { grid-template-columns: minmax(0, 1fr); gap: 16px; }
}
"""

def mark(html, parts):
    """Give the sections whose heading matches a part class, so the CSS does not depend on element order."""
    for name, cls in parts.items():
        old = f'<section class="tfc-pp-section">\n        <h2>{name}</h2>'
        assert html.count(old) == 1, name
        html = html.replace(old, f'<section class="tfc-pp-section {cls}">\n        <h2>{name}</h2>')
    return html

def mark_src(html, expect):
    old = '<section class="tfc-pp-section">\n        <p class="tfc-pp-source">'
    assert html.count(old) == expect, (html.count(old), expect)
    return html.replace(old, '<section class="tfc-pp-section tfc-pp-part-src">\n        <p class="tfc-pp-source">')


# ---- text hooks: no visible change on their own; the page CSS can style them
NUM_RE = re.compile(r"(\$\d[\d,]*(?:\.\d+)?(?:\s(?:million|billion))?|\d+(?:\.\d+)?\s?(?:percent\b|%)|\b\d{1,3}(?:,\d{3})+\b)")

def mark_numbers(html):
    """Wrap dollar amounts, percentages and big counts in <span class="tfc-pp-num"> (not inside <strong>, not inside tags)."""
    out, depth = [], 0
    for tok in re.split(r"(<[^>]+>)", html):
        if tok.startswith("<"):
            if tok.startswith("<strong"): depth += 1
            elif tok.startswith("</strong"): depth -= 1
            out.append(tok)
        elif depth == 0:
            out.append(NUM_RE.sub(lambda m: f'<span class="tfc-pp-num">{m.group(0)}</span>', tok))
        else:
            out.append(tok)
    return "".join(out)

def mark_first(html, limit=120):
    """Wrap a paragraph's first sentence in <span class="tfc-pp-first"> when a later sentence follows and it is short enough."""
    m = re.match(r"^(.*?\.)(\s+)(?=[A-Z$])", html, re.S)
    if not m:
        return html
    plain = re.sub(r"<[^>]+>|&[#\w]+;", "x", m.group(1))
    if len(plain) > limit:
        return html
    return f'<span class="tfc-pp-first">{m.group(1)}</span>{m.group(2)}{html[m.end():]}'

def decorate_p(p_html, first=True):
    """Apply the text hooks to one <p>...</p>."""
    m = re.match(r"^(<p[^>]*>)(.*)(</p>)$", p_html, re.S)
    assert m, p_html[:60]
    inner = m.group(2)
    if first:
        inner = mark_first(inner)
    return m.group(1) + mark_numbers(inner) + m.group(3)

def rework(html, name, fn):
    """Rebuild one section's content (everything after its h2) with fn(inner)."""
    head = f'<h2>{name}</h2>\n'
    assert html.count(head) == 1, name
    i = html.index(head) + len(head)
    j = html.index('\n    </section>', i)
    return html[:i] + fn(html[i:j]) + html[j:]

def as_cards(inner, classes):
    """Each <p> in a section becomes a card on the section's grid; classes[i] says how wide and which kind."""
    it = iter(classes)
    body = re.sub(r"<p>(.*?)</p>", lambda m: decorate_p('<p class="tfc-pp-card ' + (c := next(it)) + '">' + m.group(1) + '</p>', first=not re.search(r"alert|stat", c)), inner, flags=re.S)
    return '        <div class="tfc-pp-grid">\n' + body + '\n        </div>'

def split_section(inner, fig_classes, drop_title=None):
    """Text card on the left (its source line sits at the bottom), figures on the right."""
    first = inner.index("<figure")
    last = inner.rindex("</figure>") + len("</figure>")
    copy, figs, tail = inner[:first].strip("\n"), inner[first:last], inner[last:].strip()
    paras = re.findall(r"<p>.*?</p>", copy, re.S)
    for i, para in enumerate(paras):
        copy = copy.replace(para, decorate_p(para, first=(i == 0)), 1)
    parts = re.findall(r"<figure.*?</figure>", figs, re.S)
    assert len(parts) == len(fig_classes), (len(parts), len(fig_classes))
    out = ""
    for part, cls in zip(parts, fig_classes):
        part = part.replace('<figure class="tfc-pp-fig"', '<figure class="tfc-pp-fig ' + cls + '"', 1)
        if drop_title:
            part = part.replace(f"<h3>{drop_title}</h3>\n", "", 1)
        out += "            " + part.strip() + "\n"
    return ('        <div class="tfc-pp-grid">\n            <div class="tfc-pp-card tfc-pp-copy tfc-pp-w5">\n' + copy + "\n"
            + ("            " + tail + "\n" if tail else "") + "            </div>\n" + out + "        </div>")

def rate_section(inner):
    """Capital gains: the explanation on the left, the two rates compared in a card on the right."""
    p1, p3 = re.findall(r"<p>.*?</p>", inner, re.S)
    p1 = decorate_p(p1)
    ul = re.search(r'<ul class="tfc-pp-bars".*?</ul>', inner, re.S).group(0)
    return ('        <div class="tfc-pp-grid">\n'
            f'            <div class="tfc-pp-card tfc-pp-card--lead tfc-pp-w6">{p1}</div>\n'
            f'            <div class="tfc-pp-card tfc-pp-ratecard tfc-pp-w6"><h3>Top rates compared</h3>{ul}{p3}</div>\n'
            '        </div>')


PRIORITY_NO = {"cv": 1, "cg": 2, "cr": 3}
OTHERS = {
 "cg": ("/capital-gains", "Tax Profits Like Paychecks"),
 "cr": ("/tax-credits-2", "Preserve Working Families&rsquo; Tax Credits"),
 "cv": ("/conveyance-tax", "Increase the Tax on Luxury Homes"),
}

def page(key, n, head_comment, title, ask, lede, stats, sections, cta_h, cta_p, root_cls=""):
    others = "".join(f'<a class="tfc-pp-more-card" href="{OTHERS[k][0]}"><span>Priority {PRIORITY_NO[k]} of 3</span><b>{OTHERS[k][1]}</b></a>' for k in ("cv","cg","cr") if k != key)
    st = "".join(f'<div class="tfc-pp-stat"><div class="tfc-pp-stat-num">{a}</div><p class="tfc-pp-stat-label">{b}</p>{"".join(x)}</div>' for a,b,*x in stats)
    body = "\n".join(f'    <section class="tfc-pp-section">\n{s}\n    </section>\n' for s in sections)
    return f"""<!-- {head_comment} -->

{CSS}

<div class="tfc-pp{root_cls and " " + root_cls}">

    <header class="tfc-pp-hero">
        <span class="tfc-pp-eyebrow">2027 priority {n} of 3</span>
        <h1 class="tfc-pp-title">{title}</h1>
        <p class="tfc-pp-ask">{ask}</p>
        <p class="tfc-pp-lede">{lede}</p>
    </header>

    <div class="tfc-pp-stats">{st}</div>

{body}
    <section class="tfc-pp-cta" aria-labelledby="tfc-pp-cta-title">
        <div>
            <h2 id="tfc-pp-cta-title">{cta_h}</h2>
            <p>{cta_p}</p>
        </div>
        <div class="tfc-pp-cta-links">
            <a class="tfc-btn sqs-block-button-element--medium sqs-button-element--primary sqs-block-button-element" href="/subscribe">Sign up for updates</a>
            <a class="tfc-btn sqs-block-button-element--medium sqs-button-element--secondary sqs-block-button-element" href="/contact-your-legislator">Contact your legislator</a>
        </div>
    </section>

    <nav class="tfc-pp-more" aria-label="Our other 2027 priorities">
        <p class="tfc-pp-more-title">Our other 2027 priorities</p>
        <div class="tfc-pp-more-cards">{others}</div>
        <a class="tfc-pp-more-all" href="/2027-priorities">See all three</a>
    </nav>

</div>
"""

def sec(h, inner): return f"        <h2>{h}</h2>\n{inner}"

def hb(lbl, sub, pct, val, hi=False, tip=""):
    s = f"<small>{sub}</small>" if sub else ""
    return (f'<div class="tfc-pp-hb{" hi" if hi else ""}" title="{tip}"><span class="tfc-pp-hb-lbl">{lbl}{s}</span>'
            f'<span class="tfc-pp-track"><i style="width:{pct}%"></i></span><b>{val}</b></div>')

def fig(title, sub, inner, note=""):
    n = f'<p class="tfc-pp-fig-note">{note}</p>' if note else ""
    return (f'    <figure class="tfc-pp-fig" style="margin-left:0;margin-right:0">\n        <h3>{title}</h3>\n'
            f'        <p class="tfc-pp-fig-sub">{sub}</p>\n{inner}\n{n}\n    </figure>\n')

def table(head, rows, hi=0, total=None, cls=''):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = ""
    for i, r in enumerate(rows):
        tr += f'<tr{" class=hi" if i == hi else ""}>' + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    if total: tr += '<tr class="tot">' + "".join(f"<td>{c}</td>" for c in total) + "</tr>"
    return f'<div class="tfc-pp-tablewrap"><table class="tfc-pp-table {cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


CG_FIG1 = fig("The 7.25% rate mostly benefits the top 1 percent",
  "Share of the new tax if gains were taxed like wages. Hawai&#699;i resident households ranked by taxable income, tax year 2027.",
  hb("Top 1%","income over $656,000",92.3,"92.3%",True,"Top 1%: 92.3%")
  + hb("Next 4%","$373,000&ndash;$656,000",6.9,"6.9%",False,"Next 4%: 6.9%")
  + hb("Next 15%","$204,000&ndash;$372,000",0.8,"0.8%",False,"Next 15%: 0.8%")
  + hb("Bottom 80%","income under $204,000",0.04,"&lt;0.1%",False,"Bottom 80%: under 0.1%"),
  "Source: Hawai&#699;i Appleseed estimate, Census-Forecaster tax model, Act 24 brackets, tax year 2027, residents only, with a realization response.")
CG_FIG2 = fig("Where the new tax would fall",
  "Taxing capital gains like ordinary income, by resident household income group, tax year 2027. Nonresidents are shown in the table above.",
  table(["Household group","Average new tax per household","Households paying more","Total new revenue"],
   [["Top 1%<small>over $656,000</small>","$24,320","99%","$120.1M"],
    ["Next 4%<small>$373,000&ndash;$656,000</small>","$454","86%","$9.0M"],
    ["Next 15%<small>$204,000&ndash;$372,000</small>","$14","26%","$1.1M"],
    ["Next 20%<small>$130,000&ndash;$204,000</small>","under $1","9%","&lt;$0.1M"],
    ["Bottom 60%<small>under $130,000</small>","$0","0%","$0"]],
   hi=0, total=["All resident households","","","$130M"], cls="hide3"),
  "Averages are across every household in the group, including those who owe nothing more. Income is taxable income. Source: same model as above.")

CG_FIG0 = fig("Two ways to raise revenue from capital gains",
  "Estimated new revenue in tax year 2027 under Act 24&rsquo;s brackets, accounting for fewer gains being realized at a higher rate, in millions of dollars.",
  table(["Option","Residents","Nonresidents","Total"],
   [["Taxing gains at ordinary rates<small>range $158M&ndash;$214M</small>","$130M","$49M","$179M"],
    ["9% cap on capital gains<small>range $62M&ndash;$77M</small>","$48M","$19M","$67M"]],
   hi=0),
  "These are Hawai&#699;i Appleseed&rsquo;s own estimates from our Census-Forecaster tax model, not Department of Taxation or Legislature figures. Nonresidents are people who sell Hawai&#699;i property or hold Hawai&#699;i business interests while living elsewhere. Most of the range comes from the nonresident share, which swings with out-of-state home sales. In later years the totals are $173M (2028&ndash;2030) and $177M (2031) at ordinary rates, and $64M&ndash;$66M with a 9% cap. The figures are higher than earlier versions because the model now uses the Congressional Budget Office&rsquo;s February 2026 capital-gains forecast. Source: Hawai&#699;i Appleseed estimate, Census-Forecaster tax model.")

# ---------- Capital gains ----------
cg = page("cg", 2,
 """Capital Gains page (/capital-gains) - the page's Code Block. Paste everything in this file into that block.
     Replaces the 2019-data "Closing the Capital Gains Loophole" page. Same palette/Site Styles hooks as
     priorities_2027_squarespace.html. Figures: 7.25% alternative rate (HRS 235-51(f)) vs Act 24's 13% top
     bracket (was 11%, so the gap went 3.75 -> 5.75 points). "$110M+" = Census-Forecaster
     forecast_cg_rate_options.py, option "ordinary", Act 24, TY2027, with behavioral response.
     Nov 2026 refresh (Census-Forecaster main c6bf232, site/data/capital-gains/): ordinary $130M
     residents + $49M nonresidents = $179M (range $158M-$214M); 9% cap $48M + $19M = $67M
     (range $62M-$77M); later years ordinary $173M (2028-30), $177M (2031), cap $64-66M. Residents-only
     distribution (table/chart): $130M, top 1% = 92.3%. Higher than earlier versions because the model
     now uses CBO's Feb 2026 capital-gains forecast.""",
 "Tax Profits Like Paychecks",
 "Tax capital gains at the same rates as ordinary income.",
 "Hawai&#699;i taxes a nurse&rsquo;s paycheck at higher rates than a investor&rsquo;s profit from selling stock or land. We want to close that gap.".replace("a investor","an investor"),
 [("$179M","estimated new revenue in 2027 at ordinary rates (range $158M&ndash;$214M)"),("92%","of the revenue from residents would come from the top 1 percent of households"),("5.75 pts","gap between the top income tax rate on wages (13%) and the capital gains rate (7.25%), up from 3.75 points")],
 [
  sec("The loophole", """        <p>A nurse or a hotel worker pays Hawai&#699;i&rsquo;s regular income tax rates on every paycheck. But profits from selling stocks, land, and other investments are capped at <strong>7.25 percent</strong>, even for the highest-income households, whose wages are now taxed at up to <strong>13 percent</strong>.</p>
        <ul class="tfc-pp-bars" aria-label="Top rates compared">
            <li><span>Top rate on wages</span><i class="tfc-pp-bar" style="width:100%"></i><b>13%</b></li>
            <li><span>Capital gains rate</span><i class="tfc-pp-bar alt" style="width:55.8%"></i><b>7.25%</b></li>
        </ul>
        <p>Act 24 (2026) raised the top rate on wages but left the capital gains rate alone, so the gap between work and wealth grew from 3.75 to 5.75 percentage points.</p>"""),
  sec("What we are asking for", """        <p>Tax capital gains at the same rates as ordinary income, so income from owning is taxed like income from working.</p>"""),
  sec("What it would do", """        <ul>
            <li>Raise about <strong>$179 million in 2027</strong> ($130 million from residents and $49 million from nonresidents).</li>
            <li>Collect about <strong>92 percent</strong> of the resident revenue from the top 1 percent of households. Most local families would pay nothing more.</li>
            <li>A 9% cap on capital gains would raise about <strong>$67 million</strong> ($48 million from residents and $19 million from nonresidents).</li>
        </ul>""") + "\n    </section>\n" + '    <div class="tfc-pp-figs">\n' + CG_FIG0 + CG_FIG1 + CG_FIG2 + '    </div>\n' + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Estimate: Hawai&#699;i Appleseed estimate, Census-Forecaster tax model, tax year 2027, Act 24 brackets, accounting for fewer gains being realized at a higher rate.</p>',
 ],
 "Help us close the gap", "Sign up and we&rsquo;ll tell you when this bill is moving and when to submit testimony.",
 root_cls="tfc-pp-ch tfc-pp-cg")


CR_AMTS = [("Earned Income Tax Credit", 40.3), ("Food/excise tax credit", 33.6), ("Child and dependent care tax credit", 9.2)]
CR_SEG = ('<div class="tfc-pp-seg" aria-hidden="true">' + "".join(f'<i style="flex:{v}"></i>' for _, v in CR_AMTS) + '</div>'
          '<ul class="tfc-pp-seg-key">' + "".join(f'<li><b></b>{n} <em>${v}M</em></li>' for n, v in CR_AMTS) + '</ul>')

CR_FIG0 = fig("What each credit is worth",
  "Cost of keeping the expansions in tax year 2028, in millions of dollars.",
  table(["Credit","Households losing","Average loss per household that loses it","Total in 2028"],
   [["Earned Income Tax Credit","13%","$618",f"${CR_AMTS[0][1]}M"],
    ["Food/excise tax credit","34%","$200",f"${CR_AMTS[1][1]}M"],
    ["Child and dependent care tax credit<small>about 16,300 claimants</small>","2%","$1,031",f"${CR_AMTS[2][1]}M"]],
   hi=0, total=["All three","38%","$439","$83.2M"], cls="hide2"),
  "Source: Hawai&#699;i Appleseed estimate, Census-Forecaster tax model, tax year 2028.")
CR_FIG1 = fig("The lowest-income families lose the most",
  "Average loss per household in 2028 if the three credits expire, by household income group. Three in four households in the lowest-income fifth would be affected, losing $396 on average.",
  hb("Lowest 20%","income under $44,700",100,"$301",True,"Lowest 20%: $301 average, 76% of households lose")
  + hb("Second 20%","$44,700&ndash;$83,200",59.8,"$180",False,"Second 20%: $180")
  + hb("Middle 20%","$83,300&ndash;$130,400",40.4,"$122",False,"Middle 20%: $122")
  + hb("Fourth 20%","$130,400&ndash;$203,800",38.5,"$116",False,"Fourth 20%: $116")
  + hb("Top 20%","over $203,900",41.5,"$125",False,"Top 20%: $125"),
  "Average across all households in each group, including those who do not claim the credits. Source: Hawai&#699;i Appleseed tax model, tax year 2028.")
CR_FIG2 = fig("Single parents take the biggest hit",
  "Loss in 2028 if the three credits expire, by family type.",
  table(["Family type","Households","Households losing","Average loss per household","Total loss"],
   [["Single parent","63,900","67%","$526","$33.6M"],
    ["Couple with children","110,300","40%","$312","$34.4M"],
    ["Single, no children","185,200","37%","$48","$8.9M"],
    ["Couple, no children","133,800","25%","$47","$6.2M"]],
   hi=0, total=["All households","493,000","","","$83.2M"], cls="hide2"),
  "Source: same model as above.")

# ---------- Credits ----------
cr = page("cr", 3,
 """Tax Credits page (/tax-credits-2) - the Code Block in the page's first section. Paste everything in this
     file into that block; the page's newsletter section stays hidden (its form had no storage; the panel
     at the end sends people to /subscribe). Rewritten for the 2027 priority: extend Act 163's expiring
     EITC and food/excise credits. Act 163 (2023) is repealed 12/31/2027 (L 2023, c 163, s 5); HB 2306
     (2026) did not pass. $83.2M = EITC 40.3 + food/excise 33.6 + CDCTC 9.2, TY2028, Census-Forecaster main c6bf232
     site/data/working-family-credits/by_credit_ty2028.csv (Nov 25 2026 refresh; replaced the
     older $76M, which was EITC + food/excise only). CDCTC ~16,300 claimants (revenue_by_year.csv,
     cdcc_claimants 2028), $1,031 = average loss per household that loses it. 78,000 = DOTAX TY2024 EITC report. The poverty estimate was dropped from this page and from
     /2027-priorities on request; do not restore it without asking. The CTC ($650,
     ages 0-18) and RxKids note carries over from the previous version of this page. The child and dependent
     care credit sentence in the intro mirrors the Top Three fact sheet's page 1 bullet: no figure and no
     Act 163 claim (the Estimates report covers only the EITC and food/excise changes). "Chapters" layout
     (Nov 2026, Devin picked it from three mockups, then asked for the other two pages to match): pale-sky hero
     flush under the site header, full-width bands per section (pale-blue timeline, brand-blue ask), cards for
     the figures. Hero is pale sky (#e2eefb) with navy text; Devin picked it over navy, brand blue and a gradient. The three credit amounts
     (CR_AMTS in tools/build_priority_pages.py) feed the segmented bar and the credits table. The section's own
     top and bottom padding is removed by the CSS at the end so the hero touches the header; its background is
     white. Sections carry tfc-pp-part-* classes (added by the generator) so the CSS does not depend on order.""",
 "Preserve Working Families&rsquo; Tax Credits",
 "Extend the earned income and food/excise tax credits before they expire.",
 "Two credits that help Hawai&#699;i families afford groceries and other basics are set to shrink after 2027 unless the Legislature acts. The child and dependent care tax credit also helps working parents with the cost of childcare.",
 [("$83.2M","that working families would lose in 2028 if the three credits expire", CR_SEG),("78,000","households claim the state EITC each year")],
 [
  sec("What is at stake", """        <p>In 2023, Act 163 doubled two of Hawai&#699;i&rsquo;s most important credits for working families: the state <strong>Earned Income Tax Credit</strong> (to 40 percent of the federal credit) and the refundable <strong>food/excise tax credit</strong>, which helps offset the general excise tax on groceries and other basics.</p>
        <p>Those expansions end after the 2027 tax year.</p>
        <p>Our estimate also counts the <strong>child and dependent care tax credit</strong>. About 16,300 households claim it, and a household that would lose it would lose $1,031 on average.</p>"""),
  sec("The timeline", """        <div class="tfc-pp-tl">
            <ol class="tfc-pp-steps">
                <li><b>2023</b>Act 163 doubles the EITC and the food/excise credit.</li>
                <li><b>2026</b>The Legislature does not extend them (HB 2306 did not pass).</li>
                <li><b>December 31, 2027</b>The expansions are repealed.</li>
                <li class="end"><b>2028</b>First tax year without them: an estimated $83.2 million less for working families.</li>
            </ol>
        </div>"""),
  sec("What we are asking for", """        <p>Extend these credits at their current levels, so families do not take a pay cut from the tax code in 2028.</p>""") + "\n    </section>\n" + '    <div class="tfc-pp-figs">\n' + CR_FIG0 + CR_FIG1 + CR_FIG2 + '    </div>\n' + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Estimates: Hawai&#699;i Appleseed tax model, tax year 2028; EITC claims from the Department of Taxation, tax year 2024.</p>',
  sec("Also on our agenda", """        <p>We also support a refundable state Child Tax Credit of $650 per child aged 0&ndash;18, and RxKids, which would give cash payments to mothers in the first months of a child&rsquo;s life. We will post updates here as those proposals move.</p>"""),
 ],
 "Help us keep these credits", "Sign up and we&rsquo;ll tell you when these bills are moving and when to submit testimony.",
 root_cls="tfc-pp-ch tfc-pp-cr")

# (the Chapters CSS and section classes for all three pages are applied just before the files are written, below)


CV_ALLOC = fig("Where the money goes today",
  "How Hawai&#699;i law splits conveyance tax collections. The two special funds are capped, so the general fund gets everything above the caps.",
  table(["Fund","Share of collections","Most it can get each year"],
   [["Rental Housing Revolving Fund","50%","$38 million"],
    ["Land Conservation Fund","10%","$5.1 million"],
    ["General fund","The rest","No cap"],
    ["Hawaiian Home Lands","Not included","$0"]],
   hi=3),
  "Source: HRS 247-7 (current law). Each special fund gets its share or its cap, whichever is less.")

CV_CLIFF = fig("What a $1,000 difference in price costs",
  "Conveyance tax on an owner-occupied home that sells for $3,999,000 and for $4,000,000. Today, a higher price tier raises the rate on the entire price. Under the Legislature&rsquo;s April 2026 draft, each rate applies only to the slice of the price in its band.",
  table(["Sale price","Today<small>one rate on the entire price</small>","Proposed<small>a rate on each slice</small>"],
   [["$3,999,000","$19,995","$66,260"],
    ["$4,000,000","$28,000","$66,300"],
    ["Extra tax for the extra $1,000","$8,005","$40"]],
   hi=2),
  "Today&rsquo;s amounts follow HRS 247-2. Proposed amounts follow the SB 3028 SD2 HD2 rate schedule (April 2026) and are illustrations, not revenue estimates. Source: Hawai&#699;i Appleseed conveyance model (Census-Forecaster).")

CV_FIG = fig("Where the new revenue could go",
  "Estimated total conveyance tax revenue in a House committee&rsquo;s table for SB 3028, in millions of dollars. Under current law, Hawaiian Home Lands does not receive a share.",
  """        <div class="tfc-pp-stack"><span>FY2027</span><div class="tfc-pp-stack-bar" title="FY2027: $271M total, up to $60M for DHHL"><i class="hi" style="width:19.8%"></i><i style="width:69.6%"></i></div><b>$271M</b></div>
        <div class="tfc-pp-stack"><span>FY2031</span><div class="tfc-pp-stack-bar" title="FY2031: $303M total, up to $60M for DHHL"><i class="hi" style="width:19.8%"></i><i style="width:80.2%"></i></div><b>$303M</b></div>
        <ul class="tfc-pp-legend"><li><span class="hi"></span>Hawaiian Home Lands, up to $60M a year</li><li><span></span>Rental housing, urban development, land conservation, general fund and other uses</li></ul>""",
  "Source: House committee report, SB 3028 SD2 HD1 estimated revenue allocation (2026). The bill itself left its rates blank, so the estimate assumes the rates of HB 2049 HD3. The $60M is the table&rsquo;s figure for DHHL and matches the cap in SB 3028 SD2 HD2; the remainder is total minus $60M.")


CV_FIG2 = fig("What one sale would owe",
  "Conveyance tax on a single sale at each price, today and under the Legislature&rsquo;s April 2026 draft (SB 3028 SD2 HD2), for a buyer who lives in the home and for one who does not. The draft breaks even at about $2.2 million for owner-occupants and $2.1 million for everyone else.",
  table(["Sale price","Lives in the home<small>today &rarr; proposed</small>","Does not live in the home<small>today &rarr; proposed</small>"],
   [["$800,000","$1,600 &rarr; $1,200","$2,000 &rarr; $1,600"],
    ["$1.5 million","$4,500 &rarr; $4,050","$6,000 &rarr; $5,550"],
    ["$2 million","$10,000 &rarr; $6,300","$12,000 &rarr; $8,800"],
    ["$3 million","$15,000 &rarr; $26,300","$18,000 &rarr; $58,800"],
    ["$5 million","$35,000 &rarr; $106,300","$42,500 &rarr; $198,800"],
    ["$10 million","$100,000 &rarr; $346,300","$125,000 &rarr; $588,800"]],
   hi=-1),
  "Amounts follow the SD2 HD2 rate schedule and today&rsquo;s law (HRS 247-2) and are illustrations, not revenue estimates. The revenue estimate above assumes HB 2049 HD3&rsquo;s steeper rates. Source: Hawai&#699;i Appleseed conveyance model (Census-Forecaster).")
CV_FIG3 = fig("Most buyers would pay less or the same",
  "Share of Maui County sales that would owe less, the same, or more under the draft. Maui is the one county that publishes every recorded sale with its price and tax paid. In the model, 88 percent of the statewide increase would come from buyers who do not live in the home.",
  """        <div class="tfc-pp-stack"><span>Maui</span><div class="tfc-pp-stack-bar" title="43% pay less, 42% pay the same, 15% pay more"><i class="mid" style="width:43%"></i><i style="width:42.3%"></i><i class="hi" style="width:14.7%"></i></div><b></b></div>
        <ul class="tfc-pp-legend"><li><span class="mid"></span>Pay less, 43%</li><li><span></span>Pay the same, 42%</li><li><span class="hi"></span>Pay more, 15%</li></ul>""",
  "Source: Hawai&#699;i Appleseed conveyance model (Census-Forecaster), Maui recorded sales, first year.")

# ---------- Conveyance ----------
cv = page("cv", 1,
 """Conveyance Tax page (/conveyance-tax) - the page's Code Block. Paste everything in this file into that
     block. Replaces the SB 678-era "Raising the Conveyance Tax" page. Rates unchanged since Act 59
     (2009); revenue goes to the general fund, Land Conservation Fund and Rental Housing Revolving Fund,
     none to DHHL. $271M (FY27) -> $303M (FY31), DHHL up to $60M/yr = SB3028 SD2 HD2 "Estimated Revenue
     Allocation" table, via Arjuna (Slack, Oct 8 2026). Its FY29 total (268.3) doesn't match its rows
     (~286.3), so only the endpoints are cited. VERIFIED 2026-10-27 from the image Arjuna posted (Slack
     group DM, IMG_0190): a House committee report text, "If the rate structures were to reflect the ones
     this committee set like in HB2049 HD3 it would max out the special funds ... SB3028 SD2 HD1 Estimated
     Revenue Allocation". So $271M/$303M is TOTAL conveyance revenue under HB 2049 HD3's rates with the
     funds at their caps, a hypothetical, not SD2 HD2's own rates (the price table uses SD2 HD2's).
     DHHL 30% / $60M cap is in the SD2 HD2 text (data.capitol.hawaii.gov). Waitlist: 29,589 applicants
     as of 2025-11-30 (DHHL testimony to House Finance, 2026-01-08).
     Allocation (HRS 247-7): LCF 10% or $5.1M, RHRF 50% or $38M, rest general fund (checked on capitol.hawaii.gov
     2026-10-28). Marginal explainer: HRS 247-2 cliff schedule vs SD2 HD2 marginal bands; $3,999,000 vs $4,000,000
     owner-occupied = $19,995 / $28,000 today, $66,260 / $66,300 proposed (CONVEYANCE_TAX_SCOPE.md).""",
 "Increase the Tax on Luxury Homes",
 "Modernize the tax on property sales and dedicate its revenue to the Department of Hawaiian Home Lands.",
 "Those who profit most from our islands should also invest the most in their future.",
 [("$271M","estimated total conveyance tax revenue in FY2027 in a House committee&rsquo;s estimate"),("$303M","estimated by FY2031"),("$60M","a year for Hawaiian Home Lands, at most")],
 [
  sec("Where the conveyance tax stands", """        <p>The conveyance tax is paid when real estate changes hands. Its rates were last changed in 2009, and property values in Hawai&#699;i have risen considerably since then. Today its revenue goes to the general fund, the Land Conservation Fund and the Rental Housing Revolving Fund. It does not currently include funding for the Department of Hawaiian Home Lands (DHHL).</p>
        <p>DHHL&rsquo;s waitlist for a homestead had 29,589 applicants as of November 2025.</p>"""),
  sec("Where the money goes today", """        <p>The law splits conveyance tax collections three ways. The Rental Housing Revolving Fund gets 50 percent, up to $38 million a year. The Land Conservation Fund gets 10 percent, up to $5.1 million a year. The general fund gets the rest. Hawaiian Home Lands is not currently part of the split.</p>
        <p>Because both funds are capped, once collections pass about $76 million a year, every added dollar goes to the general fund.</p>""" + "\n" + CV_ALLOC + '        <p class="tfc-pp-source">Rates and allocation: Hawai&#699;i Revised Statutes sections 247-2 and 247-7.</p>'),
  sec("Why the tax should be marginal", """        <p>Today the conveyance tax has price tiers, and the rate for a sale&rsquo;s tier applies to the entire price. When a sale crosses into the next tier, the higher rate applies to every dollar, not just the dollars above the line. That creates cliffs: an owner-occupied home that sells for $4,000,000 owes $8,005 more in tax than one that sells for $3,999,000. It also gives sellers a reason to price a home just under each line.</p>
        <p>A <strong>marginal</strong> tax works like income tax brackets: each rate applies only to the slice of the price inside its band, so the tax rises smoothly as the price does.</p>
        <p>That is what lets the tax ask much more of the most expensive sales while charging typical buyers less. Under the Legislature&rsquo;s April 2026 draft, buyers who live in the home would owe less than today on every sale up to about $2.25 million, and other residential buyers on every sale up to about $2.07 million.</p>""" + "\n" + CV_CLIFF + '        <p class="tfc-pp-source">Draft: SB 3028 SD2 HD2 (April 8, 2026), which died in conference.</p>'),
  sec("What we are asking for", """        <ul>
            <li><strong>Switch to marginal rates</strong>, so each rate applies only to the part of the price in its band and there are no cliffs.</li>
            <li><strong>Ask more of high-value and investment property sales</strong>, while protecting local families buying a home to live in.</li>
            <li><strong>Dedicate the new revenue to DHHL</strong>, so the trust can build homes and infrastructure for its beneficiaries.</li>
        </ul>"""),
  sec("What it could raise", """        <p>A House committee estimated what the conveyance tax would bring in if SB 3028 used the rates of HB 2049 HD3: <strong>$271 million in total in FY2027, rising to $303 million by FY2031</strong>. That is all conveyance tax revenue, not just the increase. It would fill every special fund to its cap, including <strong>$60 million a year for DHHL</strong>, and send the rest to the general fund.</p>
        <p>SB 3028 SD2 HD2, the last draft before the bill died in conference, would send 30 percent of collections, up to $60 million a year, to Hawaiian Home Lands, along with dedicated funding for rental housing, urban development, and land conservation.</p>""" + "\n" + CV_FIG + CV_FIG2 + CV_FIG3 + '        <p class="tfc-pp-source">Estimate: House committee report, SB 3028 SD2 HD1 with the rates of HB 2049 HD3 (2026), FY2027&ndash;FY2031; applies to residential property.</p>'),
 ],
 "Help us fund Hawaiian homes", "Sign up and we&rsquo;ll tell you when this bill is moving and when to submit testimony.",
 root_cls="tfc-pp-ch tfc-pp-cv")

cg = rework(cg, "The loophole", rate_section)
cg = rework(cg, "What it would do", lambda x: x.replace("<ul>", '<ul class="tfc-pp-facts">', 1))
cg = mark(cg, {"The loophole": "tfc-pp-part-lead", "What we are asking for": "tfc-pp-part-ask", "What it would do": "tfc-pp-part-tint"})
cg = mark_src(cg, 1)
cg = cg.replace("</style>", CHAPTERS + CG_EXTRA + "</style>", 1)
cr = rework(cr, "What is at stake", lambda x: as_cards(x, ["tfc-pp-w7 tfc-pp-r2 tfc-pp-card--lead", "tfc-pp-w5 tfc-pp-card--alert", "tfc-pp-w5"]))
cr = rework(cr, "Also on our agenda", lambda x: as_cards(x, ["tfc-pp-w8"]))
cr = mark(cr, {"What is at stake": "tfc-pp-part-lead", "The timeline": "tfc-pp-part-tint tfc-pp-part-wide", "What we are asking for": "tfc-pp-part-ask", "Also on our agenda": "tfc-pp-part-agenda"})
cr = mark_src(cr, 1)
cr = cr.replace("</style>", CHAPTERS + CR_EXTRA + "</style>", 1)
cv = rework(cv, "Where the conveyance tax stands", lambda x: as_cards(x.replace("29,589 applicants", "<strong>29,589 applicants</strong>"), ["tfc-pp-w8 tfc-pp-card--lead", "tfc-pp-w4 tfc-pp-card--stat"]))
cv = rework(cv, "Where the money goes today", lambda x: split_section(x, ["tfc-pp-w7"], drop_title="Where the money goes today"))
cv = rework(cv, "Why the tax should be marginal", lambda x: split_section(x, ["tfc-pp-w7"]))
cv = rework(cv, "What we are asking for", lambda x: x.replace("<ul>", '<ul class="tfc-pp-asks">', 1))
cv = rework(cv, "What it could raise", lambda x: split_section(x, ["tfc-pp-w7", "tfc-pp-w7", "tfc-pp-w5"]))
cv = mark(cv, {"Where the conveyance tax stands": "tfc-pp-part-lead", "Where the money goes today": "tfc-pp-part-tint", "Why the tax should be marginal": "tfc-pp-part-plain", "What we are asking for": "tfc-pp-part-ask", "What it could raise": "tfc-pp-part-tint"})
cv = cv.replace("</style>", CHAPTERS + CV_EXTRA + "</style>", 1)
open(OUT+"capital_gains_squarespace.html","w").write(cg)
HIDE = """/* White behind this page (Devin, Nov 2026; tried warm sand first); replaces the section's grey #e0e0db. */
body:not(.sqs-is-page-editing) section.page-section:has(.tfc-pp) .section-background { background-color: #ffffff !important; }
/* The newsletter section: its form has no storage, so sign-ups were lost. */
body:not(.sqs-is-page-editing) section[data-section-id="691b795a3409972cbc5443fa"] { display: none !important; }
"""
cr = cr.replace("</style>", HIDE + "</style>", 1)
open(OUT+"tax_credits_squarespace.html","w").write(cr)
open(OUT+"conveyance_tax_squarespace.html","w").write(cv)
