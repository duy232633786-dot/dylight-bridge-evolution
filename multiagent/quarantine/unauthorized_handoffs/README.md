# Quarantined non-canonical handoffs

`RND-b471879e-01.antigravity.r001.unauthorized.json` was written directly by
the provider during a bounded worker invocation at 2026-08-21 16:32 local
time. The orchestrator had not called `lab submit`, the provider result was
`ERROR`, and the record claimed G0 using invented span, load and material
inputs. Its SHA-256 is
`953bbc5aa0dfbcf51388de22cf14062eaf21804ceff24ec8ebc341a029bef82b`.

The bytes are preserved for audit, but the file is outside canonical
`multiagent/handoffs/` and must never be used as evidence or mirrored as an
approved handoff. A corrected artifact may only enter the canonical flow via
`lab submit` followed by an independent review.
