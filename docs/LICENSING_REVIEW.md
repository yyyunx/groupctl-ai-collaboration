# Source and contributor rights review — 2026-11-15

**Status: unresolved; no license is granted by this review.** The owner explicitly
requested technical preparation and a private draft review, with no MIT declaration
and no PyPI upload. `docs/publishing-state.json` therefore remains false. Package
metadata intentionally omits a license expression. Public visibility, an author
name in Git, and a passing similarity check do not establish redistribution rights.

## Evidence examined

- Main base: [0c74f164dceedd6c994b52eeaad6d24b00065c04](https://github.com/yyyunx/groupctl-ai-collaboration/commit/0c74f164dceedd6c994b52eeaad6d24b00065c04).
- Root implementation: [f36cc8c18fac68c5a3aeee05469aaee713b3a267](https://github.com/yyyunx/groupctl-ai-collaboration/commit/f36cc8c18fac68c5a3aeee05469aaee713b3a267).
  It introduced both the Python implementation and eight assignment specifications;
  no earlier source history is available in this repository.
- All 17 commits reachable from that main base are attributed to yyyunx. The
  student-A/B/C names found by `git shortlog --all` occur on the isolated
  `synthesis/verification/20261113T085235-766544` simulation branches, not main's
  ancestry. `scripts/demo.py` creates those fixture identities and the recorded
  `github-demo-summary.json` identifies that simulation. These names alone are
  not evidence of independent student contributions to the shipped implementation.
  Git attribution still does not identify every original author or AI input source.
- Prior [synthesis report](SYNTHESIS_REPORT.md) and [implementation summary](IMPLEMENTATION_SUMMARY.md),
  source/test changes in commits 3291414 and 40e8d70, packaged Agent instructions,
  README, original `spec/`, examples, evidence logs, and current imports.
- Both original reference clones retained in the workspace, read at the exact
  commits cited by the synthesis report. No reference repositories were merged
  into main's history.

## Code versus design concepts

| Source | Fixed snapshot | Observations |
|---|---|---|
| [Group 1](https://github.com/ATOMIC-138/group-collaboration-system/tree/8713dd786b552d6d64f4f7123cb64c9d3b013c2c) | 8713dd786b552d6d64f4f7123cb64c9d3b013c2c | Report identifies agent entry points, portable skills, understandable status, next-action suggestions and modularization as design references. Runtime uses this project's existing groupctl structure. No identical Python file or qualifying long code block found by the comparison. Eight assignment specification files are byte-identical (see below). |
| [Group 2](https://github.com/chiahonglin1124-cyber/group-collaboration/tree/30da54a549fce80cbdbabc24bd355f16d3c68fe4) | 30da54a549fce80cbdbabc24bd355f16d3c68fe4 | Report identifies event-contract and CLI usability testing ideas. Actual fixtures/commands differ; comparison found no identical file or qualifying long code block. |

The available evidence is consistent with **concept reference and separate
implementation**, rather than a direct import of either group's Python code.
That is an engineering finding within the comparison scope, not certification
of independent authorship. Renamed, translated, paraphrased or substantially
modified copying, unavailable sources and private AI context cannot be ruled out.
Neither fixed reference snapshot contains a LICENSE/LICENCE/COPYING/NOTICE file;
their public source must not be treated as implicitly licensed for reuse.

The reproducible [comparison inventory](provenance/source-comparison.json) records
exact hashes and any matching line spans, without republishing reference code.
`scripts/audit_sources.py` compares all tracked .py/.md/.toml/.ps1 files at the
base, excluding generated `.group` and `evidence`, against 29 Group 1 files and
11 Group 2 files. It checks exact bytes and contiguous nonblank lines after
whitespace normalization (at least 6 lines and 240 characters). No qualifying
non-identical block was found. This heuristic is not a plagiarism or legal test.

## Items the owner must resolve

1. **Eight `spec/*.md` assignment documents:** they are byte-identical to Group 1's
   `specs/*.md` and were already present in this project's first commit. This is
   direct shared document content, not merely a similar idea. The history cannot
   determine whether both groups received the same instructor materials or one
   copied the other. Confirm the actual author/instructor and permission for public
   repository and sdist redistribution. They remain unchanged; the wheel does not
   include `spec`, but the sdist and repository do. If permission is unavailable,
   decide an authorized distribution exclusion or independently written replacement
   for publication without silently editing the original assignment.
2. **Base Group 3 implementation and documentation:** confirm who wrote supplied
   material in f36cc8c, any real teammates' contributions, and rights to the AI-assisted
   source and prompts/materials used. Repository author metadata alone is insufficient.
3. **Adaptation records:** confirm no unrecorded copying from reference groups or
   other repositories. If later found, obtain the original rights holder's permission,
   preserve required notices and choose compatible terms, or replace that material.
   Asking the reference groups about their own code does not establish their rights
   over a shared instructor specification.
4. **Evidence and teaching materials:** existing logs/reports contain fixture names,
   repository references and generated results; no imported reference implementation
   was found in shipped runtime. Confirm any externally supplied assignment text,
   third-party prose or real personal data is allowed in public documentation/sdist.
5. **License decision:** after resolving the above, choose terms with the actual
   rights holders, add only accurate notices/metadata, document approval evidence,
   and review the exact newly built artifacts. Until then, do not describe the
   project as MIT, open-source licensed, or redistribution-cleared.

Runtime imports are Python standard library only; the wheel does not vendor third-party
Python dependencies. Build tools and GitHub Actions are fetched separately. This
reduces dependency redistribution scope but does not settle source/document rights.

## Reproducing the inventory

With the two reference checkouts available locally:

```text
python scripts/audit_sources.py --base 0c74f164dceedd6c994b52eeaad6d24b00065c04 --reference group1=/path/group1@8713dd786b552d6d64f4f7123cb64c9d3b013c2c --reference group2=/path/group2@30da54a549fce80cbdbabc24bd355f16d3c68fe4 --output docs/provenance/source-comparison.json
git log main --format="%h %an <%ae>"
git log --all --author=student --oneline
```

The review is limited to available history and these named sources. It does not
claim to have searched all possible code or established ownership.
