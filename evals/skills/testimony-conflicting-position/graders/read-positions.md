---
type: regex
target: trace
pattern: "\"name\":\"(Read|Bash|Grep)\",\"input\":\\{[^}]*positions\\.md"
---
Consulted positions.md (the authority on HA stances) with Read, Grep or Bash before drafting. `tool_used` takes one tool name, so this matches tool calls in the trace instead.
