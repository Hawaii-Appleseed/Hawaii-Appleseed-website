---
type: regex
pattern: "font-family\\s*:[^;\\\"}]*\\b(?:serif|Georgia|Times|Fraunces|Garamond|Merriweather)\\b(?![\\w-])(?<!sans-serif)"
match: not_contains
flags: "i"
---
No serif font anywhere in the font stacks (sans-serif fallbacks are fine).
