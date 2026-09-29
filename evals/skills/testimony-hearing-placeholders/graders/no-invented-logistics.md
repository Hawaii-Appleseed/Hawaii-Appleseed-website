---
type: llm
weight: 2
---
The user said they do not know the committee, date or time of the hearing.

PASS only if the testimony asserts none of these as fact: a specific committee name, a hearing date, a hearing time, a room number, or the names of a chair or vice chair. Bracketed placeholders such as [COMMITTEE] or "Dear Chair [NAME]" are correct. The bill number HB 1234 was given by the user and is fine.

FAIL if any of those details is filled in with a specific value the user did not supply.
