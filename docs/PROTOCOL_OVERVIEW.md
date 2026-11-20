# Implemented collaboration protocol 0.1

This overview is written for the groupctl implementation and is distributed under
the project's MIT License. It does not reproduce the original course assignment.

Each teammate works in a separate Git clone and uses an individual person ID.
The project's `.group/group.json` selects the accepted branch, assignment and
verification commands. A personal branch holds proposed changes; pushing it does
not automatically accept the proposal into the accepted branch.

groupctl publishes separate JSON event files describing contributions, reviews,
test evidence, integrations, questions, answers, blockers and finalization. Existing
public events must remain unchanged. Synchronization discovers events across remote
branches, so another teammate can recover the shared state without private chat.

Use `doctor` to diagnose setup, then `context` and `inbox` to inspect the current
state. `pub` checks a contribution before publishing it; `inspect` and `review`
support an assessment of its exact commit. `integrate` starts a merge and
`integrate-finish` records its verification and an explicit semantic assessment.
Conflicts require deliberate resolution. `recover` describes incomplete operations
and offers explicit retries that preserve existing evidence and Git history.

Verification commands run without shell concatenation in disposable worktrees.
Evidence identifies the tested commit. Missing tests, skipped-only suites and
unavailable dependencies do not become passing results. A successful Git merge or
test command does not establish semantic compatibility; agents and people still
need to inspect the intended combined behavior.

Finalization has two stages: prepare a concrete candidate on the accepted branch,
then publish only after genuine human confirmation bound to that candidate and
its report. Simulation fixtures label their judgments and confirmations as such.
Installing groupctl or its Agent Skills grants no automatic approval of a project's
final result and requires no AI API key.

For precise fields and executable cases, read `groupctl/events.py`, CLI `--help`,
the tests, and `.agents/skills/group-collaboration/references/commands.md`.
