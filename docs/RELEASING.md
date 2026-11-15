# Release and PyPI operations

Current version: **0.3.2, preparation only**. No PyPI upload is authorized. Licensing
is unresolved; see [the source/rights inventory](LICENSING_REVIEW.md). No license
expression or third-party grant has been invented. Draft assets are for owner review.

## Local validation

```text
python -m pip install build twine
python scripts/check_version.py
python -m unittest discover -s tests -v
python scripts/demo.py
python -m build
python -m twine check dist/*
python scripts/check_artifacts.py
python scripts/installed_smoke.py
```

Start with an empty dist directory (move old outputs outside dist, do not mix versions).
`python -m build` builds the sdist and then the wheel from that sdist. The inspection
checks archive resources/metadata and emits SHA256SUMS and RELEASE-PROVENANCE.json.
The smoke test installs **each** archive into its own new venv, with no source
PYTHONPATH, and uses CLI executables from unrelated/Unicode directories. It verifies
version/installed metadata, all Agent bundles, read-only preview, idempotence and
conflict preservation, then initializes a disposable local Git team and runs doctor,
context and inbox. It never contacts GitHub or an AI API. Installing build dependencies
for the sdist can access the Python package index.

Ordinary CI uses the reusable `verify-distribution.yml`: full suite (78 existing
tests preserved plus packaging/setup coverage), existing fifteen-step acceptance,
and both artifact installations on Ubuntu/Windows, Python 3.10/3.13. No assertions
or acceptance requirements were weakened. Platform-specific symlink/junction tests
run on their matching OS. Build results are retained as the `groupctl-dist` artifact.

## Exact-tag draft release

1. Merge the verified preparation branch through a reviewed PR using normal Git history.
2. Inspect the resulting main SHA; create and push the **new** tag `v0.3.2` at that SHA.
   Never move/recreate a published or previously validated tag to hide a changed commit.
3. From main, manually run **Prepare verified draft release** (`prepare-release.yml`),
   input `tag: v0.3.2`. This resolves the existing tag, requires main ancestry, checks
   tag/package/docs consistency, builds exactly that commit, and reruns the full matrix.
4. The draft job depends on **all** matrix jobs, verifies the original checksums and
   provenance, checks the live tag again, and creates a GitHub **draft only** with wheel,
   sdist, SHA256SUMS and provenance. It does not use a different main CI build, rebuild
   in the draft job, or overwrite any existing release.
5. Inspect that run, exact SHA, notes and assets. Formal Publish requires explicit
   owner approval and resolved rights; it is not performed by this workflow.

The v0.3.2 tag contains `redistribution_approved: false`. A later licensing/metadata
change must be committed and validated as a new immutable release version; the current
draft cannot be sent to PyPI merely by toggling a repository variable or publishing it
on GitHub. Preserve this preparation tag and its evidence. Never claim old artifacts
contain a newly selected license.

## PyPI name research

On 2026-11-15 the official JSON API returned HTTP **404** for
[`groupctl`](https://pypi.org/pypi/groupctl/json),
[`groupctl-collab`](https://pypi.org/pypi/groupctl-collab/json), and
[`groupctl-ai-collaboration`](https://pypi.org/pypi/groupctl-ai-collaboration/json).
No public project was found under those names. 404 does not guarantee registration:
reserved/prohibited/normalized names and later registrations may still prevent it.
Keep `name = "groupctl"` for now; recheck immediately before registering a publisher.
If unavailable, prefer `groupctl-ai-collaboration` (matches this repository) or
`groupctl-collab`; inspect the competing project to avoid confusion, then update package
metadata, archive checks, installation examples and publisher consistently. The console
script remains `groupctl`. Do not upload an empty placeholder to reserve a name.

## Settings the owner must complete after rights approval

Use [PyPI's Trusted Publisher setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
and [PyPA's GitHub Actions guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).

1. Resolve all items in LICENSING_REVIEW.md and explicitly approve the selected license
   and production publication. Commit accurate metadata/notices and set
   `docs/publishing-state.json` to true only with actual rights evidence; review/build
   a new version/tag including those changes.
2. Create/sign in to a PyPI account, verify email, enable 2FA and save recovery codes
   securely. Account ownership and rights confirmation remain human actions.
3. In [PyPI account publishing](https://pypi.org/manage/account/publishing/), create a
   pending publisher for a new project (or add it under the existing owned project's
   Publishing settings):

   | Field | Value |
   |---|---|
   | PyPI project | groupctl (recheck availability) |
   | GitHub owner | yyyunx |
   | Repository | groupctl-ai-collaboration |
   | Workflow filename | publish-pypi.yml |
   | Environment | pypi |

4. In GitHub Settings → Environments create **pypi**, require reviewer approval and
   restrict deployments to main. Choose a reviewer who can actually approve the run;
   do not enable a self-review prohibition if it leaves nobody eligible. Configure
   tag protection/rulesets to restrict release-tag mutation as appropriate.
5. Only when ready, add repository Actions variable **PYPI_PUBLISH_ENABLED=true**.
   Leave it absent/false throughout preparation. Do not add PyPI tokens/passwords.
6. After the approved version's exact-tag draft pipeline succeeds and the human
   authorizes publishing that concrete release, Publish it on GitHub. Then manually
   run **Publish approved release to PyPI** on main with the exact tag and confirmation
   `PUBLISH vX.Y.Z`, and approve the pypi environment deployment.

The independent publish workflow has no push/release automatic trigger. It checks
both main and tagged licensing gates, exact tag/main ancestry, published release,
archive checksums/version/provenance and a successful prepare-release run. It downloads
those verified assets without rebuilding. Only the isolated publishing job gets
`id-token: write`; it uses PyPA's `gh-action-pypi-publish` with default attestations
and no long-lived API key, password or repository credential in source.
This follows [PyPI's recommended publishing action](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

TestPyPI is optional: it requires a separate account and publisher/environment.
It is not silently enabled by this repository, and uploading there also requires
owner authorization and cleared redistribution rights.

## End-user checks after an authorized publication

From an unrelated directory with Git installed:

```text
pipx install groupctl
groupctl --version
groupctl agent-setup --target /path/to/team --dry-run
groupctl agent-setup --target /path/to/team
groupctl --repo /path/to/team doctor
```

Before PyPI publication, install the authorized GitHub wheel URL or downloaded wheel
instead. Both names and versions must match the release being reviewed. For a configured
team also run `context --offline` and `inbox --offline`; doctor returns 2 until required
project setup exists. Never report that these production installs work before publishing.
