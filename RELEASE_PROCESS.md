# Release Process

This document describes the complete release workflow for opc-replay.

## Quick Start: Automated Release

**For most releases, use the automated release script:**

```bash
./scripts/prepare_release.sh
```

The script handles version bumping, changelog updates, validation checks, git operations, and prompts for human review at key checkpoints. See [Automated Release Process](#automated-release-process) below for details.

**For manual releases or troubleshooting, see [Manual Release Process](#manual-release-process).**

---

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Incompatible API changes
- **MINOR** (0.X.0): New functionality, backwards-compatible
- **PATCH** (0.0.X): Bug fixes, backwards-compatible

**Current Status**: Version 0.9.0+ indicates feature-complete beta approaching stable 1.0.0 release.

## Release Roles

Releases are created and managed by project maintainers only. Contributors should focus on pull requests with tested, documented changes.

## Pre-Release Checklist

Before starting a release, ensure:

- [ ] All desired features/fixes are merged to `main` branch via Pull Requests
- [ ] All CI checks pass on `main` (tests, linting, format, build, version-check)
- [ ] Documentation is up-to-date (README.md, docstrings, examples)
- [ ] CHANGELOG.md has entries in `[Unreleased]` section
- [ ] Local validation passes: `./scripts/run_ci_locally.sh`
- [ ] Breaking changes are documented and justified
- [ ] Migration guide added (for major/minor with breaking changes)

---

## Automated Release Process

### Overview

The `./scripts/prepare_release.sh` script automates most of the release workflow while providing validation checkpoints for human review.

### What the Script Does

1. **Version Selection** - Prompts for release type (major/minor/patch/custom)
2. **Pre-Release Validation** - Runs all CI checks locally (tests, linting, build)
3. **Version Updates** - Updates `pyproject.toml` and `opc_replay/__init__.py`
4. **Changelog Generation** - Moves `[Unreleased]` items to versioned section with date
5. **Review Pause** - Shows diff and allows manual edits before committing
6. **Git Commit** - Creates commit: `Release vX.Y.Z`
7. **Git Tag** - Creates annotated tag: `vX.Y.Z`
8. **Push Confirmation** - Asks before pushing (triggers GitHub workflows)
9. **Optional: GitHub Release** - If `gh` CLI is available, offers to auto-create release with changelog
10. **Post-Release Bump** - Prompts for next dev version (e.g., `X.(Y+1).0-dev`)
11. **Dev Version Commit** - Commits and optionally pushes dev version

### Prerequisites

**Required:**
- Git configured and authenticated
- Clean working directory (no uncommitted changes)
- All desired changes merged to current branch

**Optional (but recommended):**
- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated
  - Enables automatic GitHub Release creation
  - Install: `brew install gh` / `apt install gh` / `winget install GitHub.cli`
  - Authenticate: `gh auth login`
  - Without `gh`, you'll need to create the release manually via GitHub UI

### Using the Script

**1. Start the Release:**

```bash
./scripts/prepare_release.sh
```

**2. Follow Interactive Prompts:**

- **Select version type**: Choose 1-4 for major/minor/patch/custom
- **Confirm version**: Review the calculated version number
- **Wait for validation**: Script runs all tests and checks
- **Review changes**: Examine the diff, especially CHANGELOG.md
- **Edit if needed**: Press Enter after any manual edits
- **Confirm commit**: Approve creating the release commit
- **Confirm tag**: Approve creating the git tag
- **Confirm push**: Approve pushing to GitHub (triggers CI)
- **Select next dev version**: Choose development version for next cycle
- **Confirm dev bump**: Approve committing the dev version

**3. Create GitHub Release:**

*If using automated script with gh CLI:*
- The script will offer to create the release automatically after pushing the tag
- It extracts the changelog section and creates the release with proper title and notes
- Publishing triggers the PyPI upload workflow automatically

*If creating manually:*

After the script pushes the tag:
1. Go to GitHub → Releases → "Draft a new release"
2. Select the tag (e.g., `v0.11.0`)
3. Copy the changelog entry for this version as the description
4. Title: `Release v0.11.0`
5. Click "Publish release" (triggers PyPI upload)

*Or via gh CLI:*
```bash
gh release create v0.11.0 --title "Release v0.11.0" --notes-file <(sed -n '/## \[0.11.0\]/,/## \[/p' CHANGELOG.md | head -n -1)
```

**4. Verify Publication:**

```bash
# Check PyPI
open https://pypi.org/project/opc-replay/

# Test installation
pip install opc-replay==X.Y.Z

# Verify CLI commands
opc-replay --help
opc-client --help
opc-inject --help
```

### Validation Checkpoints

The script pauses for human validation at these points:

1. **After version selection** - Confirm the calculated version
2. **After changelog generation** - Review and edit CHANGELOG.md if needed
3. **Before creating commit** - Confirm commit creation
4. **Before creating tag** - Confirm tag creation
5. **Before pushing** - Confirm push to GitHub (triggers workflows)
6. **After release** - Select and confirm next dev version

### Hotfix Releases

For urgent fixes that can't wait for the next regular release:

**1. Create hotfix branch from release tag:**

```bash
git checkout -b hotfix/0.10.1 v0.10.0
```

**2. Apply fixes:**

```bash
# Cherry-pick commits or make fixes directly
git cherry-pick <commit-hash>
# Or: Make fixes and commit
git add .
git commit -m "Fix critical bug"

# Update CHANGELOG.md manually
```

**3. Run release script:**

```bash
./scripts/prepare_release.sh
```

- Select option 4 (custom version)
- Enter the patch version (e.g., `0.10.1`)
- Follow normal release process

**4. Merge back to main:**

```bash
git checkout main
git merge hotfix/0.10.1
# Resolve any conflicts (especially version files and CHANGELOG)
git push origin main
```

**5. Complete release:**

- Create GitHub Release from the hotfix tag
- Verify PyPI publication
- Test installation

---

## Manual Release Process

Use this process if the automated script fails or for special circumstances.

### 1. Update Version Numbers

Edit both version files to match:

**pyproject.toml:**
```toml
[project]
name = "opc-replay"
version = "0.10.0"  # <- Update this line
```

**opc_replay/__init__.py:**
```python
__version__ = "0.10.0"  # <- Update this line
```

**Convention**: Use format `MAJOR.MINOR.PATCH` without `-dev` or `-rc` suffixes.

**Verify consistency:**
```bash
./scripts/check_version_sync.sh
```

### 2. Update CHANGELOG.md

Move items from `[Unreleased]` section to a new versioned section:

```markdown
## [Unreleased]

### Added

### Changed

### Fixed

## [0.10.0] - 2026-03-20

### Added
- New feature X
- New feature Y

### Changed
- Improvement Z

### Fixed
- Bug fix A
```

Add version comparison link at the bottom:

```markdown
[Unreleased]: https://github.com/mieslep/opc-replay/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/mieslep/opc-replay/releases/tag/v0.10.0
[0.9.0]: https://github.com/mieslep/opc-replay/releases/tag/v0.9.0
```

**Date Format**: Use ISO 8601 format (YYYY-MM-DD)

### 3. Commit Version Bump

Create a dedicated commit for the version bump:

```bash
git add pyproject.toml opc_replay/__init__.py CHANGELOG.md
git commit -m "Release vX.Y.Z"
git push origin main
```

**Important**: Wait for CI to pass on this commit before proceeding.

### 4. Test with TestPyPI (Recommended)

Before releasing to production PyPI, validate with TestPyPI:

1. **Trigger TestPyPI workflow** (manual dispatch):
   ```bash
   # Via GitHub web UI: Actions -> Publish to TestPyPI -> Run workflow
   # Or with gh CLI:
   gh workflow run publish-test.yml
   ```

2. **Wait for workflow completion** and verify success

3. **Test installation from TestPyPI**:
   ```bash
   # Create fresh virtual environment
   python -m venv test-env
   source test-env/bin/activate  # or: test-env\Scripts\activate on Windows
   
   # Install from TestPyPI
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ opc-replay==0.10.0
   
   # Verify commands work
   opc-replay --help
   opc-client --help
   opc-inject --help
   
   # Clean up
   deactivate
   rm -rf test-env
   ```

4. **If issues found**: Fix, update version to `0.10.1`, and repeat from step 1

### 5. Create Git Tag

Tag the release commit:

```bash
git tag -a v0.10.0 -m "Release v0.10.0"
git push origin v0.10.0
```

**Format**: Always prefix version with `v` (e.g., `v0.10.0`, `v1.0.0`)

**Trigger**: This push triggers the [pre-release-check.yml](.github/workflows/pre-release-check.yml) workflow which validates:
- Version in `pyproject.toml` matches tag (without `v` prefix)
- `CHANGELOG.md` contains entry for this version
- All required checks pass

**Action**: Monitor the pre-release check workflow and fix any validation errors before proceeding.

### 6. Create GitHub Release

Create the release from the tag:

**Option A: GitHub Web UI**
1. Go to https://github.com/mieslep/opc-replay/releases/new
2. Select tag: `v0.10.0`
3. Release title: `v0.10.0`
4. Description: Copy from `CHANGELOG.md` for this version
5. Check "Set as the latest release" (if applicable)
6. Click "Publish release"

**Option B: GitHub CLI**
```bash
# Extract changelog for this version
VERSION="0.10.0"
NOTES=$(sed -n "/## \[${VERSION}\]/,/## \[/p" CHANGELOG.md | head -n -1)

# Create release
gh release create "v${VERSION}" \
  --title "v${VERSION}" \
  --notes "${NOTES}"
```

**Trigger**: Publishing the release triggers [publish.yml](.github/workflows/publish.yml) which:
- Builds the package (wheel + sdist)
- Publishes to PyPI via Trusted Publishing
- Artifacts are automatically available on PyPI

### 7. Verify PyPI Publication

1. **Check PyPI page**: https://pypi.org/project/opc-replay/
   - Verify version `0.10.0` appears
   - Check metadata (description, links, classifiers)
   - Review README rendering

2. **Test installation**:
   ```bash
   # Fresh virtual environment
   python -m venv verify-env
   source verify-env/bin/activate
   
   # Install from PyPI (wait ~1 minute for propagation)
   pip install opc-replay==0.10.0
   
   # Verify installation
   opc-replay --version  # Should show 0.10.0
   opc-replay --help
   
   # Clean up
   deactivate
   rm -rf verify-env
   ```

3. **Monitor GitHub Actions**: Verify [publish.yml workflow](https://github.com/mieslep/opc-replay/actions/workflows/publish.yml) completed successfully

### 8. Post-Release Tasks

- [ ] Update project status (if needed)
- [ ] Announce release (GitHub Discussions, mailing list, social media, etc.)
- [ ] Close related GitHub issues/milestones
- [ ] Update documentation website (if applicable)
- [ ] Consider blog post for major releases

### 9. Bump to Next Development Version

After releasing `X.Y.Z`, prepare for the next development cycle:

**1. Update version files:**

```bash
# Example: After releasing 0.10.0, bump to 0.11.0-dev
```

**pyproject.toml:**
```toml
version = "0.11.0-dev"  # Next minor version with -dev suffix
```

**opc_replay/__init__.py:**
```python
__version__ = "0.11.0-dev"
```

**2. Update CHANGELOG.md:**

Ensure there's an `[Unreleased]` section at the top:

```markdown
## [Unreleased]

### Added

### Changed

### Fixed

## [0.10.0] - 2026-03-20
...
```

**3. Commit and push:**

```bash
git add pyproject.toml opc_replay/__init__.py CHANGELOG.md
git commit -m "Bump version to 0.11.0-dev"
git push origin main
```

**Version Selection for Next Dev:**
- After regular release: Bump minor version (0.10.0 → 0.11.0-dev)
- After hotfix: Keep minor, bump patch (0.10.1 → 0.10.2-dev) if more hotfixes expected
- After hotfix: Or bump minor (0.10.1 → 0.11.0-dev) if returning to feature development

---

## Rollback Procedures

If critical issues are discovered after release:

### Option 1: Yank Release (Serious Issues)

If the release has critical bugs or security issues:

1. **Yank from PyPI**:
   ```bash
   # Requires PyPI credentials
   pip install twine
   twine upload --skip-existing --repository pypi dist/*  # Won't work, use PyPI web UI
   ```
   
   Or via PyPI web UI:
   - Go to https://pypi.org/manage/project/opc-replay/release/0.10.0/
   - Click "Options" -> "Yank release"
   - Provide reason (shown to users)

2. **Mark release as pre-release on GitHub**:
   - Edit GitHub release
   - Check "Set as a pre-release"
   - Add warning to description

3. **Issue hotfix**: Create patch version (0.10.1) with fix and release immediately

### Option 2: Patch Release (Minor Issues)

For non-critical issues:

1. Create fix on `main`
2. Bump to patch version (e.g., 0.10.0 -> 0.10.1)
3. Follow normal release process
4. Document issue in CHANGELOG under `### Fixed`

## PyPI Trusted Publishing Setup

**One-time setup required before first release.**

### Production PyPI

1. Visit: https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill out form:
   - **PyPI Project Name**: `opc-replay`
   - **Owner**: `mieslep` (your GitHub username or org)
   - **Repository name**: `opc-replay`
   - **Workflow name**: `publish.yml`
   - **Environment name**: (leave blank)
4. Click "Add"

**Note**: After first successful publish, "pending publisher" becomes active trusted publisher.

### TestPyPI (Optional but Recommended)

Same process at https://test.pypi.org/manage/account/publishing/ with:
- **Workflow name**: `publish-test.yml`

## Branch Protection Setup

**One-time setup for repository.**

Go to: https://github.com/mieslep/opc-replay/settings/branches

### Protection Rule for `main`

1. Click "Add branch protection rule"
2. Branch name pattern: `main`
3. Enable:
   - ✓ Require a pull request before merging
     - Required approvals: 0 (or 1 for team review)
   - ✓ Require status checks to pass before merging
     - ✓ Require branches to be up to date before merging
     - Status checks required:
       - `test (ubuntu-latest, 3.13)`
       - `test (windows-latest, 3.13)`
       - `test (macos-latest, 3.13)`
       - `lint`
       - `build`
   - ✓ Require conversation resolution before merging
   - ✓ Include administrators (enforce rules for everyone)
4. Click "Create"

**Effect**: Direct pushes to `main` are blocked; all changes must go through pull requests with passing CI.

## Troubleshooting

### Pre-Release Check Fails

**Version mismatch error**:
```
[ERROR] Version mismatch!
Git tag version: 0.10.0
pyproject.toml version: 0.9.0
```

**Fix**: Update `pyproject.toml` version to match tag, create new commit, delete and recreate tag:
```bash
# Fix version in pyproject.toml
git add pyproject.toml
git commit -m "Fix version number"
git push origin main

# Delete old tag (local and remote)
git tag -d v0.10.0
git push origin :refs/tags/v0.10.0

# Create new tag on updated commit
git tag -a v0.10.0 -m "Release v0.10.0"
git push origin v0.10.0
```

**CHANGELOG missing version**:
```
[ERROR] CHANGELOG.md does not contain entry for version 0.10.0
```

**Fix**: Add version section to CHANGELOG.md, commit, delete/recreate tag as above.

### PyPI Publish Fails

**Trusted publishing not configured**:
```
Error: Trusted publisher configuration is required
```

**Fix**: Complete PyPI Trusted Publishing setup (see section above), then re-trigger workflow or create new release.

**Version already exists on PyPI**:
```
Error: File already exists
```

**Fix**: PyPI does not allow re-uploading same version. Bump to next patch version (e.g., 0.10.0 -> 0.10.1).

### Build Failures

**Import errors in tests**:

1. Ensure virtual environment is clean: `rm -rf .venv && uv sync`
2. Run local CI: `./scripts/run_ci_locally.sh`
3. Fix issues before tagging

## Resources

- [Keep a Changelog](https://keepachangelog.com/)
- [Semantic Versioning](https://semver.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
