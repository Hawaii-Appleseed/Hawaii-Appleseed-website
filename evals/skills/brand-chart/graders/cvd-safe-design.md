---
type: llm
---
Judge the matplotlib script as a chart a colour-blind reader can use.

PASS if all of these hold: series colours come from Hawaiʻi Appleseed's chart palette (Deep Teal #52796F, Charcoal #2F3E46, Ochre #BF8A30, Harbor blue #6A8CC4, in that order), not the matplotlib default cycle or a rainbow/viridis map; series are distinguishable without colour alone, i.e. there are direct labels, value labels, or a clearly positioned legend; gridlines are light/hairline or absent; no 3-D or gradient effects. FAIL if any fails.
