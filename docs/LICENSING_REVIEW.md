# Source and contributor rights review — 2026-11-20

**v0.3.3 distribution status: approved for MIT-licensed GitHub publication.**
On 2026-11-20, yyyunx explicitly confirmed ownership of the project's code and their
own writing, selected MIT, and authorized changes and GitHub publication after
successful checks. That confirmation applies to the owner's material; it does not
establish ownership of third-party course specifications. PyPI publication is not
authorized. The machine-readable record is [publishing-state.json](publishing-state.json).

The standard root [LICENSE](../LICENSE) covers the current project code, independently
authored documentation, tests and Agent Skills, Copyright (c) 2026 yyyunx. Metadata
declares SPDX MIT and includes LICENSE in wheel and sdist. Build tools and GitHub
Actions are obtained separately; the runtime has only standard-library imports and
vendors no third-party dependency. No additional third-party implementation, asset or
document requiring a separate grant was found within the reviewed distribution scope.
This finding and the owner's attestation do not claim a universal authorship audit.

## Excluded materials and unchanged history

The eight `spec/00_...md` through `spec/07_...md` course documents have unconfirmed
redistribution rights. They were already present in the first commit and are identical
to Group 1's copies; their actual author/instructor cannot be established from Git.
They are **not relicensed as MIT**. For v0.3.3 they are removed from the current Git
tree, so GitHub's source ZIP/tarball also exclude them. MANIFEST.in additionally prunes
the spec directory from Python distributions. An independently written overview in
docs/PROTOCOL_OVERVIEW.md describes the implemented behavior without copying them.

The inventory below and docs/provenance/source-comparison.json retain paths and hashes,
not the documents' text. Archive checks reject the eight original names and matching
content hashes even under renamed paths. CI inspects wheel, sdist and an export of
the tagged Git tree; publication also verifies the public GitHub source archives.

Existing Git history and the v0.3.2 annotated tag/object, draft and artifacts are
unchanged. The historical documents remain subject to their original rights; this
MIT addition neither grants third-party rights nor represents old artifacts as newly
licensed. Historical synthesis reports below describe their earlier snapshots.

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

## Release disposition

- Owner code and own documentation: ownership confirmed and MIT explicitly selected
  by yyyunx in the release request on 2026-11-20.
- Eight course specifications: rights remain unconfirmed; excluded from all v0.3.3
  release content. No instructor or reference-group ownership is asserted.
- Reference groups' implementation: the available comparison and inspected fixtures
  support concept reference with separate implementation; no imported implementation
  was found. No reference-group license is being granted by this project.
- Evidence/logs: project-authored reports and generated fixtures are retained. The
  comparison inventory contains hashes and filenames rather than reference source.
- GitHub v0.3.3 publication: explicitly authorized after complete verification.
- PyPI/TestPyPI: not authorized and not uploaded; a separate state flag is false.

No unresolved rights item is included in the v0.3.3 distribution scope. Any newly
discovered third-party content requires review before a subsequent release.

## Reproducing the inventory

With the two reference checkouts available locally:

```text
python scripts/audit_sources.py --base 0c74f164dceedd6c994b52eeaad6d24b00065c04 --reference group1=/path/group1@8713dd786b552d6d64f4f7123cb64c9d3b013c2c --reference group2=/path/group2@30da54a549fce80cbdbabc24bd355f16d3c68fe4 --output docs/provenance/source-comparison.json
git log main --format="%h %an <%ae>"
git log --all --author=student --oneline
```

The review is limited to available history and these named sources. It does not
claim to have searched all possible code or established ownership.
