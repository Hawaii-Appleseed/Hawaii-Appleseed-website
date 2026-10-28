# Generates the three 2027 priority page files (capital_gains / tax_credits / conveyance_tax _squarespace.html).
# Run: python3 tax-fairness/tools/build_priority_pages.py   Then paste each output file into its page's Code Block.
import sys
import os
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

OTHERS = {
 "cg": ("/capital-gains", "Tax Wealth Like Work"),
 "cr": ("/tax-credits-2", "Keep Working Families&rsquo; Tax Credits"),
 "cv": ("/conveyance-tax", "Reform the Conveyance Tax"),
}

def page(key, n, head_comment, title, ask, lede, stats, sections, cta_h, cta_p):
    others = [f'<a href="{OTHERS[k][0]}">{OTHERS[k][1]}</a>' for k in ("cg","cr","cv") if k != key]
    st = "".join(f'<div class="tfc-pp-stat"><div class="tfc-pp-stat-num">{a}</div><p class="tfc-pp-stat-label">{b}</p></div>' for a,b in stats)
    body = "\n".join(f'    <section class="tfc-pp-section">\n{s}\n    </section>\n' for s in sections)
    return f"""<!-- {head_comment} -->

{CSS}

<div class="tfc-pp">

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

    <p class="tfc-pp-more">Our other 2027 priorities: {" and ".join(others)}. <a href="/2027-priorities">See all three</a>.</p>

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
  "Share of the tax break today, which is essentially the share of new tax if gains were taxed like wages. Hawai&#699;i households ranked by taxable income, tax year 2027.",
  hb("Top 1%","income over $661,000",89.6,"89.6%",True,"Top 1%: 89.6%")
  + hb("Next 4%","$373,000&ndash;$660,000",9.4,"9.4%",False,"Next 4%: 9.4%")
  + hb("Next 15%","$204,000&ndash;$373,000",0.9,"0.9%",False,"Next 15%: 0.9%")
  + hb("Bottom 80%","income under $204,000",0.04,"&lt;0.1%",False,"Bottom 80%: under 0.1%"),
  "Source: Hawai&#699;i Appleseed tax model (Census-Forecaster), Act 24 baseline, tax year 2027, residents only, with behavioral response.")
CG_FIG2 = fig("Where the new tax would fall",
  "Taxing capital gains like ordinary income, by household income group, tax year 2027.",
  table(["Household group","Average new tax per household","Households paying more","Total new revenue"],
   [["Top 1%<small>over $661,000</small>","$20,060","99%","$98.9M"],
    ["Next 4%<small>$373,000&ndash;$660,000</small>","$524","86%","$10.3M"],
    ["Next 15%<small>$204,000&ndash;$373,000</small>","$14","24%","$1.0M"],
    ["Next 20%<small>$130,000&ndash;$204,000</small>","under $1","8%","&lt;$0.1M"],
    ["Bottom 60%<small>under $130,000</small>","$0","0%","$0"]],
   hi=0, total=["All households","","","$110M"]),
  "Averages are across every household in the group, including those who owe nothing more. Income is taxable income. Source: same model as above.")

# ---------- Capital gains ----------
cg = page("cg", 3,
 """Capital Gains page (/capital-gains) - the page's Code Block. Paste everything in this file into that block.
     Replaces the 2019-data "Closing the Capital Gains Loophole" page. Same palette/Site Styles hooks as
     priorities_2027_squarespace.html. Figures: 7.25% alternative rate (HRS 235-51(f)) vs Act 24's 13% top
     bracket (was 11%, so the gap went 3.75 -> 5.75 points). "$110M+" = Census-Forecaster
     forecast_cg_rate_options.py, option "ordinary", Act 24, TY2027, residents only, with behavioral
     response; ~90% from the top 1% (distribution_ty2027_act24.csv).""",
 "Tax Wealth Like Work",
 "Tax capital gains at the same rates as ordinary income.",
 "Hawai&#699;i taxes a nurse&rsquo;s paycheck at higher rates than a investor&rsquo;s profit from selling stock or land. We want to close that gap.".replace("a investor","an investor"),
 [("Over $100M","estimated new revenue each year"),("90%","of it from the top 1 percent of households"),("5.75 pts","gap between the top wage rate and the capital gains rate, up from 3.75")],
 [
  sec("The loophole", """        <p>A nurse or a hotel worker pays Hawai&#699;i&rsquo;s regular income tax rates on every paycheck. But profits from selling stocks, land, and other investments are capped at <strong>7.25 percent</strong>, even for the highest-income households, whose wages are now taxed at up to <strong>13 percent</strong>.</p>
        <ul class="tfc-pp-bars" aria-label="Top rates compared">
            <li><span>Top rate on wages</span><i class="tfc-pp-bar" style="width:100%"></i><b>13%</b></li>
            <li><span>Capital gains rate</span><i class="tfc-pp-bar alt" style="width:55.8%"></i><b>7.25%</b></li>
        </ul>
        <p>Act 24 (2026) raised the top rate on wages but left the capital gains rate alone, so the gap between work and wealth grew from 3.75 to 5.75 percentage points.</p>"""),
  sec("What we are asking for", """        <p>Tax capital gains at the same rates as ordinary income, so income from owning is taxed like income from working.</p>"""),
  sec("What it would do", """        <ul>
            <li>Raise <strong>over $100 million a year</strong>.</li>
            <li>Collect about <strong>90 percent</strong> of it from the top 1 percent of households. Most local families would pay nothing more.</li>
        </ul>""") + "\n    </section>\n" + CG_FIG1 + CG_FIG2 + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Estimate: Hawai&#699;i Appleseed tax model, tax year 2027, Hawai&#699;i residents only, accounting for fewer gains being realized at a higher rate.</p>',
 ],
 "Help us close the gap", "Sign up and we&rsquo;ll tell you when this bill is moving and when to submit testimony.")


CR_FIG1 = fig("The lowest-income families lose the most",
  "Average loss per household in 2028 if the credits expire, by household income group. Three in four households in the lowest-income fifth would be affected, losing $460 on average.",
  hb("Lowest 20%","income under $44,700",100,"$347",True,"Lowest 20%: $347 average, 75% of households lose")
  + hb("Second 20%","$44,700&ndash;$83,200",54.9,"$191",False,"Second 20%: $191")
  + hb("Middle 20%","$83,300&ndash;$130,400",25.9,"$90",False,"Middle 20%: $90")
  + hb("Fourth 20%","$130,400&ndash;$203,800",20.2,"$70",False,"Fourth 20%: $70")
  + hb("Top 20%","over $203,900",22.2,"$77",False,"Top 20%: $77"),
  "Average across all households in each group, including those who do not claim the credits. Source: Hawai&#699;i Appleseed tax model, tax year 2028.")
CR_FIG2 = fig("Single parents take the biggest hit",
  "Loss in 2028 if the credits expire, by family type.",
  table(["Family type","Households","Households losing","Average loss per household","Total loss"],
   [["Single parent","63,900","64%","$524","$33.5M"],
    ["Couple with children","110,300","35%","$260","$28.7M"],
    ["Single, no children","185,200","36%","$45","$8.4M"],
    ["Couple, no children","133,800","25%","$45","$6.0M"]],
   hi=0, total=["All households","493,000","","","$76M"], cls="hide2"),
  "Source: same model as above.")

# ---------- Credits ----------
cr = page("cr", 2,
 """Tax Credits page (/tax-credits-2) - the Code Block in the page's first section. Paste everything in this
     file into that block; the page's newsletter section stays hidden (its form had no storage; the panel
     at the end sends people to /subscribe). Rewritten for the 2027 priority: extend Act 163's expiring
     EITC and food/excise credits. Act 163 (2023) is repealed 12/31/2027 (L 2023, c 163, s 5); HB 2306
     (2026) did not pass. $76M / 2,100 people / 500 children = forecast_working_family_credits.py, TY2028
     (SB3125_CD1_FORECAST.md, Oct 8 2026 anchor). 78,000 = DOTAX TY2024 EITC report. The CTC ($650,
     ages 0-18) and RxKids note carries over from the previous version of this page.""",
 "Keep Working Families&rsquo; Tax Credits",
 "Extend the earned income and food/excise tax credits before they expire.",
 "Two credits that help Hawai&#699;i families afford groceries and other basics are set to shrink after 2027 unless the Legislature acts.",
 [("$76M","that working families would lose in 2028 if the credits expire"),("About 2,100","more people, including about 500 keiki, would fall into poverty"),("78,000","households claim the state EITC each year")],
 [
  sec("What is at stake", """        <p>In 2023, Act 163 doubled two of Hawai&#699;i&rsquo;s most important credits for working families: the state <strong>Earned Income Tax Credit</strong> (to 40 percent of the federal credit) and the refundable <strong>food/excise tax credit</strong>, which helps offset the general excise tax on groceries and other basics.</p>
        <p>Those expansions end after the 2027 tax year.</p>"""),
  sec("The timeline", """        <ol class="tfc-pp-steps">
            <li><b>2023</b>Act 163 doubles the EITC and the food/excise credit.</li>
            <li><b>2026</b>The Legislature does not extend them (HB 2306 did not pass).</li>
            <li><b>December 31, 2027</b>The expansions are repealed.</li>
            <li class="end"><b>2028</b>First tax year without them: an estimated $76 million less for working families.</li>
        </ol>"""),
  sec("What we are asking for", """        <p>Extend both credits at their current levels, so families do not take a pay cut from the tax code in 2028.</p>""") + "\n    </section>\n" + CR_FIG1 + CR_FIG2 + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Estimates: Hawai&#699;i Appleseed tax model, tax year 2028; EITC claims from the Department of Taxation, tax year 2024. The poverty estimates have wide margins of error.</p>',
  sec("Also on our agenda", """        <p>We also support a refundable state Child Tax Credit of $650 per child aged 0&ndash;18, and RxKids, which would give cash payments to mothers in the first months of a child&rsquo;s life. We will post updates here as those proposals move.</p>"""),
 ],
 "Help us keep these credits", "Sign up and we&rsquo;ll tell you when these bills are moving and when to submit testimony.")


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
 "Reform the Conveyance Tax to Fund Hawaiian Homes",
 "Modernize the tax on property sales and dedicate its revenue to the Department of Hawaiian Home Lands.",
 "Those who profit most from our islands should also invest the most in their future.",
 [("$271M","estimated total conveyance tax revenue in FY2027 in a House committee&rsquo;s estimate"),("$303M","estimated by FY2031"),("$60M","a year for Hawaiian Home Lands, at most")],
 [
  sec("Where the conveyance tax stands", """        <p>The conveyance tax is paid when real estate changes hands. Its rates were last changed in 2009, and property values in Hawai&#699;i have risen considerably since then. Today its revenue goes to the general fund, the Land Conservation Fund and the Rental Housing Revolving Fund. It does not currently include funding for the Department of Hawaiian Home Lands (DHHL).</p>
        <p>DHHL&rsquo;s waitlist for a homestead had 29,589 applicants as of November 2025.</p>"""),
  sec("Where the money goes today", """        <p>The law splits conveyance tax collections three ways. The Rental Housing Revolving Fund gets 50 percent, up to $38 million a year. The Land Conservation Fund gets 10 percent, up to $5.1 million a year. The general fund gets the rest. Hawaiian Home Lands is not currently part of the split.</p>
        <p>Because both funds are capped, once collections pass about $76 million a year, every added dollar goes to the general fund.</p>""") + "\n    </section>\n" + CV_ALLOC + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Rates and allocation: Hawai&#699;i Revised Statutes sections 247-2 and 247-7.</p>',
  sec("Why the tax should be marginal", """        <p>Today the conveyance tax has price tiers, and the rate for a sale&rsquo;s tier applies to the entire price. When a sale crosses into the next tier, the higher rate applies to every dollar, not just the dollars above the line. That creates cliffs: an owner-occupied home that sells for $4,000,000 owes $8,005 more in tax than one that sells for $3,999,000. It also gives sellers a reason to price a home just under each line.</p>
        <p>A <strong>marginal</strong> tax works like income tax brackets: each rate applies only to the slice of the price inside its band, so the tax rises smoothly as the price does.</p>
        <p>That is what lets the tax ask much more of the most expensive sales while charging typical buyers less. Under the Legislature&rsquo;s April 2026 draft, buyers who live in the home would owe less than today on every sale up to about $2.25 million, and other residential buyers on every sale up to about $2.07 million.</p>""") + "\n    </section>\n" + CV_CLIFF + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Draft: SB 3028 SD2 HD2 (April 8, 2026), which died in conference.</p>',
  sec("What we are asking for", """        <ul>
            <li><strong>Switch to marginal rates</strong>, so each rate applies only to the part of the price in its band and there are no cliffs.</li>
            <li><strong>Ask more of high-value and investment property sales</strong>, while protecting local families buying a home to live in.</li>
            <li><strong>Dedicate the new revenue to DHHL</strong>, so the trust can build homes and infrastructure for its beneficiaries.</li>
        </ul>"""),
  sec("What it could raise", """        <p>A House committee estimated what the conveyance tax would bring in if SB 3028 used the rates of HB 2049 HD3: <strong>$271 million in total in FY2027, rising to $303 million by FY2031</strong>. That is all conveyance tax revenue, not just the increase. It would fill every special fund to its cap, including <strong>$60 million a year for DHHL</strong>, and send the rest to the general fund.</p>
        <p>SB 3028 SD2 HD2, the last draft before the bill died in conference, would send 30 percent of collections, up to $60 million a year, to Hawaiian Home Lands, along with dedicated funding for rental housing, urban development, and land conservation.</p>""") + "\n    </section>\n" + CV_FIG + CV_FIG2 + CV_FIG3 + '    <section class="tfc-pp-section">\n        <p class="tfc-pp-source">Estimate: House committee report, SB 3028 SD2 HD1 with the rates of HB 2049 HD3 (2026), FY2027&ndash;FY2031; applies to residential property.</p>',
 ],
 "Help us fund Hawaiian homes", "Sign up and we&rsquo;ll tell you when this bill is moving and when to submit testimony.")

open(OUT+"capital_gains_squarespace.html","w").write(cg)
HIDE = """/* The newsletter section: its form has no storage, so sign-ups were lost. */
body:not(.sqs-is-page-editing) section[data-section-id="691b795a3409972cbc5443fa"] { display: none !important; }
"""
cr = cr.replace("</style>", HIDE + "</style>", 1)
open(OUT+"tax_credits_squarespace.html","w").write(cr)
open(OUT+"conveyance_tax_squarespace.html","w").write(cv)
