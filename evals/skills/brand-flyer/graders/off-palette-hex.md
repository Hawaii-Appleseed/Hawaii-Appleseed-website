---
type: regex
pattern: "#(?!(?:2B4A45|2F3E46|354F52|405B5A|52796F|6A8CC4|6B917D|6E4524|84A98C|A85A45|A9C3B3|B07A35|B4C9B6|BF8A30|CAD2C5|D9E2D8|E0BF85|E2E8E8|E5E9E2|E6EFE9|EDEDE5|F2F0EA|F2F4EF|F4F7F4|FFFFFF|FFF)(?![0-9a-f]))(?:[0-9a-f]{6}|[0-9a-f]{3})(?![0-9a-z_-])"
match: not_contains
flags: "i"
---
Every hex colour is an Appleseed token value (assets/tokens.css): no invented greens, no legacy sage `#3a7811`, no default library colours. `#fff` is allowed.
