---
type: regex
pattern: "slide_layouts\\[\\s*[02]\\s*\\]|\\b[A-Z_]*(?:TITLE|SECTION|CLOSING)[A-Z_]*\\s*=\\s*[02]\\b|title slide|section header"
flags: "i"
---
Title and closing slides use the template's dark layouts (0 Title Slide, 2 Section Header), by index or by name.
