---
type: regex
pattern: "^[\\s#*>\\d.)-]*\\**(Background|Analysis|Findings)\\**\\s*($|[—–:-])"
flags: "im"
match: not_contains
---
No generic "Background", "Analysis" or "Findings" headings; middle sections are named for the subject.
