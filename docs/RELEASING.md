# Release and PyPI operations

Current release: **v0.3.3**, MIT License, Copyright (c) 2026 yyyunx. The owner has
approved GitHub publication after successful checks. **PyPI publication remains
explicitly unauthorized.** See LICENSING_REVIEW.md for scope and excluded documents.

## Validation before a release

Use an empty dist directory; keep outputs from older versions elsewhere.

```text
python -m pip install build twine
python scripts/check_version.py
python -m unittest discover -s tests -v
python scripts/demo.py
python -m build
python -m twine check dist/*
git archive --format=zip --output=source-release.zip HEAD
python scripts/check_artifacts.py --source-archive source-release.zip
python scripts/installed_smoke.py
```

The original 92 tests remain and release-policy coverage is added. Ubuntu/Windows,
Python 3.10/3.13 each run the complete suite, existing fifteen-step acceptance, and
fresh wheel/sdist installations from unrelated Unicode paths. Platform-specific link
tests run on their corresponding OS. No test/acceptance requirement is weakened.
The build is produced once from sdist, then those same artifacts are installed on all
four combinations. Metadata, bundled Agent resources, MIT text, excluded original
filenames/content hashes, SHA256 and provenance are checked. The exported Git tree
is inspected too, covering the source content GitHub publishes automatically.

## Exact-tag verification and GitHub publication

1. Merge the verified release branch through a PR, preserving existing history.
2. Create a new immutable v0.3.3 tag at the verified main commit. Never move v0.3.2
   or claim its old artifacts contain the new MIT License.
3. Run Prepare verified draft release (prepare-release.yml) on main, tag v0.3.3.
   It requires main ancestry and exact tag/version/HEAD consistency, rebuilds that
   exact commit, and reruns the complete matrix. Main CI alone is insufficient.
4. The draft job runs only after every matrix job succeeds. It verifies original
   artifacts, provenance and the live tag, then attaches exactly wheel, sdist,
   SHA256SUMS and RELEASE-PROVENANCE.json. It does not rebuild or replace an existing
   release. A draft is the intermediate review step, not completed publication.
5. With the owner's explicit v0.3.3 authorization, confirm licensing state, successful
   exact-tag run, unchanged tag, and attachment hashes, then Publish the GitHub release.
6. Verify the public page and unauthenticated downloads, compare hashes, inspect public
   source ZIP/tarball for excluded documents, and install through the public wheel URL.
   Check version, agent-setup, doctor, context and inbox on a disposable local project.

v0.3.2 remains a historical preparation draft without a retroactive license grant.
The uncleared course documents are removed only by a new commit, not a history rewrite.

## End-user installation

Install Git and Python 3.10+, then use pipx:

```text
pipx install "https://github.com/yyyunx/groupctl-ai-collaboration/releases/download/v0.3.3/groupctl-0.3.3-py3-none-any.whl"
groupctl --version
groupctl agent-setup --target /path/to/team --dry-run
groupctl agent-setup --target /path/to/team
groupctl --repo /path/to/team doctor
```

doctor returns 2 until required team setup exists. For an initialized team, use
context --offline and inbox --offline. README includes first-team setup and updates.

## PyPI remains disabled

docs/publishing-state.json separates redistribution_approved and
github_publication_approved (true) from pypi_publication_approved (false).
publish-pypi.yml checks PyPI authorization in both main and tagged state, in addition
to the existing manual trigger, typed confirmation, repository opt-in and protected
pypi environment. Publishing a GitHub release never triggers PyPI upload.

Only after a separate explicit owner instruction may a future approved release be
uploaded. At that point recheck package name availability; the 2026-11-15 PyPI API
checks found no public groupctl/groupctl-collab/groupctl-ai-collaboration project but
did not reserve those names. Register a Trusted Publisher using owner yyyunx,
repository groupctl-ai-collaboration, workflow filename publish-pypi.yml, environment
pypi, and the selected project name. Set up a verified PyPI account with 2FA, GitHub
environment reviewers and repository opt-in. Do not commit tokens or passwords.

The isolated publishing job uses PyPA Trusted Publishing/OIDC and downloads verified
release artifacts without rebuilding. See the official documentation:
[PyPI](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and
[PyPA](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).
No PyPI or TestPyPI upload is part of this GitHub release.
