# Portable Agent Collaboration Instructions

Detailed procedures are maintained in [.agents/skills/group-collaboration/references/commands.md](.agents/skills/group-collaboration/references/commands.md).
Read them before handling SYNC, PUB, INT, REV, TEST, STATUS or FINAL.

The discoverable skill is [.agents/skills/group-collaboration/SKILL.md](.agents/skills/group-collaboration/SKILL.md).
This file remains a compatible entry point for existing users and agents.

- Use groupctl for Git facts, event validation and isolated tests; use agent/human judgment for semantic compatibility.
- Preserve dirty work, immutable evidence, and exact tested commits.
- Never interpret a Demo's simulated decisions as actual human review.
- Real FINAL requires candidate-bound human confirmation; a noninteractive --confirm flag alone is insufficient.
