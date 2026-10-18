# Manuals

* `BLACKBOX_AI_Agent_Execution_Manual_v4.md` - authoritative implementation spec for coding agents.
* `BLACKBOX_Team_Manual_v4.md` - human-side plan: scope, sequencing, evidence, recovery.

The earlier "DEEP_REVISED" manuals are superseded by v4 and deliberately not included. Differences that
matter: v4 returns 6 ForkResults per simulated transaction (normal + stress per scenario), uses the frozen
`EventContext`, and adds trace/diagnostics requirements.
