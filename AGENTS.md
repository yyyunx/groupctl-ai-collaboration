# Group 3 development and collaboration

This repository provides the `groupctl` Python package. Preserve its package,
existing CLI command names and protocol 0.1. Do not edit the original `spec/`
assignment documents to accommodate an implementation.

For a managed target containing `.group/group.json`, read
`AGENT_COLLABORATION.md` and `.agents/skills/group-collaboration/SKILL.md` before
handling SYNC / PUB / INT / REV / TEST / STATUS / FINAL.
The user may authorize a development branch such as `synthesis/groupctl-final`;
do not confuse tool development with personal work inside a managed project.

Validate changes with `python -m unittest discover -s tests -v` and run
`python scripts/demo.py` for the full three-clone acceptance scenario.
Use `python` for Python 3.10+; the Windows launcher also accepts GROUPCTL_PYTHON.
Tests create disposable local Git remotes. Keep them and generated demo output
out of commits; retain concise execution evidence when requested.

Publish only checked files, preserve others' work and Git history, and never
claim test, push or human-confirmation success without evidence.
