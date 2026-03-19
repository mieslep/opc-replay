#!/usr/bin/env bash
#
# Release Preparation Script for OPC Replay
#
# ⚠️  WARNING: This script currently assumes direct push access to main branch.
# ⚠️  If branch protection is enabled (requiring PRs), this script will fail.
# ⚠️  
# ⚠️  With branch protection, follow the manual PR-based workflow documented in:
# ⚠️  .github/copilot-instructions.md (Release Management Workflow section)
#
# This script automates the mechanical parts of the release process while
# providing validation checkpoints for human review. It handles:
# - Version selection (major/minor/patch/custom for hotfixes)
# - File updates (pyproject.toml, __init__.py, CHANGELOG.md)
# - Validation checks (tests, linting, version sync)
# - Git operations (commit, tag, push)
# - Post-release version bump to next dev version
#
# Usage: ./scripts/prepare_release.sh
#
# The script will interactively guide you through the release process.

set -e  # Exit on any error

# Color output (only if terminal supports it)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    NC=''
fi

# Helper functions
print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

prompt_yn() {
    while true; do
        read -p "$1 (y/n): " yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer y or n.";;
        esac
    done
}

# Check if gh CLI is available and authenticated
check_gh_cli() {
    if ! command -v gh &> /dev/null; then
        return 1
    fi
    
    # Check if authenticated
    if ! gh auth status &> /dev/null; then
        return 1
    fi
    
    return 0
}

# Extract changelog section for a specific version
extract_changelog_section() {
    local version=$1
    local in_section=0
    local changelog_content=""
    
    while IFS= read -r line; do
        # Start capturing when we find the version header
        if [[ $line =~ ^##\ \[$version\] ]]; then
            in_section=1
            continue
        fi
        
        # Stop capturing when we hit the next version section
        if [[ $in_section -eq 1 ]] && [[ $line =~ ^##\ \[ ]]; then
            break
        fi
        
        # Capture content while in section
        if [[ $in_section -eq 1 ]]; then
            changelog_content+="$line"$'\n'
        fi
    done < CHANGELOG.md
    
    # Trim leading/trailing whitespace
    echo "$changelog_content" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

# Check we're in the project root
if [ ! -f "pyproject.toml" ] || [ ! -f "CHANGELOG.md" ]; then
    print_error "This script must be run from the project root directory."
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    print_error "You have uncommitted changes. Please commit or stash them first."
    git status --short
    exit 1
fi

# Extract current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
print_step "Current version: $CURRENT_VERSION"

# Remove -dev suffix if present for version calculation
BASE_VERSION="${CURRENT_VERSION%-dev}"

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$BASE_VERSION"

print_header "Select Release Type"
echo "Current version: $CURRENT_VERSION"
echo ""
echo "Release type options:"
echo "  1) Major release (X+1.0.0) - Breaking changes"
echo "  2) Minor release ($MAJOR.X+1.0) - New features"
echo "  3) Patch release ($MAJOR.$MINOR.X+1) - Bug fixes"
echo "  4) Custom version - For hotfixes or special cases"
echo ""
read -p "Select release type (1-4): " RELEASE_TYPE

case $RELEASE_TYPE in
    1)
        NEW_VERSION="$((MAJOR + 1)).0.0"
        RELEASE_DESC="Major release"
        ;;
    2)
        NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
        RELEASE_DESC="Minor release"
        ;;
    3)
        NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
        RELEASE_DESC="Patch release"
        ;;
    4)
        read -p "Enter custom version (e.g., $MAJOR.$MINOR.$((PATCH + 1))): " NEW_VERSION
        RELEASE_DESC="Custom release"
        # Validate version format
        if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            print_error "Invalid version format. Must be MAJOR.MINOR.PATCH (e.g., 1.2.3)"
            exit 1
        fi
        ;;
    *)
        print_error "Invalid selection"
        exit 1
        ;;
esac

print_header "Preparing Release: v$NEW_VERSION"
echo "$RELEASE_DESC: $CURRENT_VERSION -> $NEW_VERSION"
echo ""

if ! prompt_yn "Continue with this version?"; then
    print_warning "Release preparation cancelled."
    exit 0
fi

# Run pre-release validation
print_header "Running Pre-Release Validation"

print_step "Running version consistency check..."
./scripts/check_version_sync.sh

print_step "Running tests..."
if ! uv run pytest tests/ -v --tb=short; then
    print_error "Tests failed. Fix failing tests before releasing."
    exit 1
fi
print_success "Tests passed"

print_step "Running linting..."
if ! uv run ruff check .; then
    print_error "Linting failed. Fix issues before releasing."
    exit 1
fi
print_success "Linting passed"

print_step "Checking code formatting..."
if ! uv run ruff format --check .; then
    print_error "Code formatting issues found. Run 'uv run ruff format .' to fix."
    exit 1
fi
print_success "Formatting is correct"

print_step "Building package..."
if ! uv run python -m build; then
    print_error "Package build failed."
    exit 1
fi
print_success "Package built successfully"

print_success "All validation checks passed!"

# Update version in files
print_header "Updating Version Numbers"

print_step "Updating pyproject.toml..."
sed -i "s/^version = .*/version = \"$NEW_VERSION\"/" pyproject.toml

print_step "Updating opc_replay/__init__.py..."
sed -i "s/^__version__ = .*/__version__ = \"$NEW_VERSION\"/" opc_replay/__init__.py

print_success "Version numbers updated to $NEW_VERSION"

# Update CHANGELOG.md
print_header "Updating CHANGELOG.md"

RELEASE_DATE=$(date +%Y-%m-%d)
print_step "Release date: $RELEASE_DATE"

# Create changelog section for this version
# Check if there's an [Unreleased] section with content
if grep -q "## \[Unreleased\]" CHANGELOG.md; then
    print_step "Moving [Unreleased] items to version $NEW_VERSION..."
    
    # Create temporary file with the new changelog structure
    awk -v version="$NEW_VERSION" -v date="$RELEASE_DATE" '
    /## \[Unreleased\]/ {
        print "## [Unreleased]"
        print ""
        print "## [" version "] - " date
        in_unreleased = 1
        next
    }
    /^## \[/ && in_unreleased {
        in_unreleased = 0
    }
    !in_unreleased || !/^## \[Unreleased\]/ {
        print
    }
    ' CHANGELOG.md > CHANGELOG.md.tmp
    
    mv CHANGELOG.md.tmp CHANGELOG.md
    print_success "Changelog updated"
else
    print_warning "No [Unreleased] section found. You'll need to manually add the release entry."
fi

# Update version comparison links at the bottom of CHANGELOG.md
print_step "Updating version comparison links..."
# Extract git remote URL for comparison links
GIT_REMOTE=$(git config --get remote.origin.url | sed 's/\.git$//' | sed 's/git@github.com:/https:\/\/github.com\//')

# Check if there's already a version comparison section
if grep -q "\[Unreleased\]:" CHANGELOG.md; then
    # Update the unreleased link and add new version link
    sed -i "s|\[Unreleased\]:.*|\[Unreleased\]: $GIT_REMOTE/compare/v$NEW_VERSION...HEAD\n[$NEW_VERSION]: $GIT_REMOTE/compare/v$BASE_VERSION...v$NEW_VERSION|" CHANGELOG.md
else
    print_warning "Version comparison links section not found. You may need to add it manually."
fi

print_success "Changelog preparation complete"

# Show changes for review
print_header "Review Changes"
echo "The following files have been modified:"
echo ""
git diff pyproject.toml opc_replay/__init__.py CHANGELOG.md

echo ""
print_warning "IMPORTANT: Review the changes above, especially CHANGELOG.md"
print_warning "Edit CHANGELOG.md now if needed to improve the release notes."
echo ""
read -p "Press Enter when you've finished reviewing/editing (or Ctrl+C to abort)..."

# Verify version consistency after manual edits
print_step "Re-checking version consistency after any edits..."
if ! ./scripts/check_version_sync.sh; then
    print_error "Version mismatch detected. Please fix before continuing."
    exit 1
fi

# Create release commit
print_header "Creating Release Commit"

git add pyproject.toml opc_replay/__init__.py CHANGELOG.md
COMMIT_MESSAGE="Release v$NEW_VERSION"

print_step "Commit message: $COMMIT_MESSAGE"
if ! prompt_yn "Create commit with this message?"; then
    print_warning "Release preparation cancelled. Changes are staged but not committed."
    exit 0
fi

git commit -m "$COMMIT_MESSAGE"
print_success "Release commit created"

# Create git tag
print_header "Creating Git Tag"

TAG_NAME="v$NEW_VERSION"
TAG_MESSAGE="Release version $NEW_VERSION"

print_step "Tag: $TAG_NAME"
print_step "Message: $TAG_MESSAGE"

if ! prompt_yn "Create annotated tag?"; then
    print_warning "Skipping tag creation. You can create it manually later."
else
    git tag -a "$TAG_NAME" -m "$TAG_MESSAGE"
    print_success "Tag $TAG_NAME created"
fi

# Push changes
print_header "Push Changes"

echo "The release commit and tag are ready to push."
echo ""
print_warning "Pushing the tag will trigger the pre-release-check workflow."
print_warning "After pushing, create a GitHub Release to trigger PyPI publishing."
echo ""

if prompt_yn "Push commit and tag to origin now?"; then
    git push origin HEAD
    if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
        git push origin "$TAG_NAME"
        print_success "Pushed commit and tag to origin"
        
        echo ""
        print_step "Waiting for pre-release-check workflow..."
        echo "(The workflow validates version consistency and changelog)"
        
        # Check if gh CLI is available
        if check_gh_cli; then
            echo ""
            print_step "GitHub CLI detected!"
            
            if prompt_yn "Create GitHub Release now (with auto-extracted changelog)?"; then
                print_step "Extracting changelog for v$NEW_VERSION..."
                
                # Extract changelog section
                CHANGELOG_BODY=$(extract_changelog_section "$NEW_VERSION")
                
                if [ -z "$CHANGELOG_BODY" ]; then
                    print_warning "Could not extract changelog section. Will create release without description."
                    CHANGELOG_BODY="Release version $NEW_VERSION"
                fi
                
                print_step "Creating GitHub Release..."
                if gh release create "$TAG_NAME" \
                    --title "Release v$NEW_VERSION" \
                    --notes "$CHANGELOG_BODY" \
                    --verify-tag; then
                    print_success "GitHub Release created successfully!"
                    echo ""
                    print_step "Release published! This will trigger PyPI publishing workflow."
                    echo "  - Check PyPI: https://pypi.org/project/opc-replay/"
                    echo "  - Monitor workflow: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions"
                else
                    print_error "Failed to create GitHub Release via gh CLI."
                    print_warning "Please create the release manually via GitHub UI."
                fi
            else
                echo ""
                print_step "Next steps:"
                echo "  1. Wait for pre-release-check workflow to complete (GitHub Actions)"
                echo "  2. Create a GitHub Release from tag $TAG_NAME"
                echo "  3. Copy changelog entry to release description"
                echo "  4. Publish the release (triggers PyPI upload)"
            fi
        else
            echo ""
            print_warning "GitHub CLI (gh) not found or not authenticated."
            echo "Install: https://cli.github.com/"
            echo ""
            print_step "Next steps:"
            echo "  1. Wait for pre-release-check workflow to complete (GitHub Actions)"
            echo "  2. Create a GitHub Release from tag $TAG_NAME"
            echo "  3. Copy changelog entry to release description"
            echo "  4. Publish the release (triggers PyPI upload)"
        fi
    else
        git push origin HEAD
        print_success "Pushed commit to origin (no tag to push)"
    fi
else
    print_warning "Changes not pushed. Push manually when ready:"
    echo "  git push origin HEAD"
    if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
        echo "  git push origin $TAG_NAME"
    fi
fi

# Post-release version bump
print_header "Post-Release Version Bump"

echo "After releasing $NEW_VERSION, we need to set the next development version."
echo ""
echo "Suggested next versions:"
echo "  1) $MAJOR.$((MINOR + 1)).0-dev (next minor, recommended for feature development)"
echo "  2) $MAJOR.$MINOR.$((PATCH + 1))-dev (next patch, for hotfix-only branch)"
echo "  3) $((MAJOR + 1)).0.0-dev (next major, for breaking changes)"
echo "  4) Custom version"
echo "  5) Skip (do manually later)"
echo ""
read -p "Select next dev version (1-5): " DEV_CHOICE

case $DEV_CHOICE in
    1)
        NEXT_DEV_VERSION="$MAJOR.$((MINOR + 1)).0-dev"
        ;;
    2)
        NEXT_DEV_VERSION="$MAJOR.$MINOR.$((PATCH + 1))-dev"
        ;;
    3)
        NEXT_DEV_VERSION="$((MAJOR + 1)).0.0-dev"
        ;;
    4)
        read -p "Enter custom dev version (must end with -dev): " NEXT_DEV_VERSION
        if ! [[ $NEXT_DEV_VERSION =~ -dev$ ]]; then
            print_error "Development version must end with -dev"
            exit 1
        fi
        ;;
    5)
        print_warning "Skipping dev version bump. Remember to do this before continuing development."
        print_success "Release preparation complete!"
        exit 0
        ;;
    *)
        print_error "Invalid selection"
        exit 1
        ;;
esac

print_step "Bumping to dev version: $NEXT_DEV_VERSION"

# Update version files
sed -i "s/^version = .*/version = \"$NEXT_DEV_VERSION\"/" pyproject.toml
sed -i "s/^__version__ = .*/__version__ = \"$NEXT_DEV_VERSION\"/" opc_replay/__init__.py

# Add new Unreleased section to changelog if it doesn't exist
if ! grep -q "## \[Unreleased\]" CHANGELOG.md; then
    # Insert after the header and before the first version section
    awk '/^## \[/ && !found {print "## [Unreleased]\n"; found=1} {print}' CHANGELOG.md > CHANGELOG.md.tmp
    mv CHANGELOG.md.tmp CHANGELOG.md
fi

print_success "Updated to dev version: $NEXT_DEV_VERSION"

# Show changes
echo ""
git diff pyproject.toml opc_replay/__init__.py CHANGELOG.md

echo ""
if prompt_yn "Commit dev version bump?"; then
    git add pyproject.toml opc_replay/__init__.py CHANGELOG.md
    git commit -m "Bump version to $NEXT_DEV_VERSION"
    print_success "Dev version committed"
    
    if prompt_yn "Push dev version commit?"; then
        git push origin HEAD
        print_success "Dev version pushed"
    else
        print_warning "Dev version not pushed. Push manually when ready:"
        echo "  git push origin HEAD"
    fi
else
    print_warning "Dev version changes not committed. Files are modified but not staged."
fi

print_header "Release Preparation Complete"
print_success "Release v$NEW_VERSION is ready!"
echo ""
echo "Summary:"
echo "  - Released: v$NEW_VERSION"
echo "  - Next dev: $NEXT_DEV_VERSION"
echo ""
if check_gh_cli && gh release view "$TAG_NAME" &> /dev/null; then
    print_success "GitHub Release created successfully!"
    echo ""
    echo "Final verification:"
    echo "  1. Monitor PyPI publication: https://pypi.org/project/opc-replay/"
    echo "  2. Test installation: pip install opc-replay==$NEW_VERSION"
    echo "  3. Verify CLI commands work: opc-replay --help"
else
    echo "Don't forget to:"
    if ! (check_gh_cli && gh release view "$TAG_NAME" &> /dev/null); then
        echo "  1. Create GitHub Release from tag v$NEW_VERSION (if not done)"
    fi
    echo "  2. Verify PyPI publication after release"
    echo "  3. Test installation: pip install opc-replay==$NEW_VERSION"
fi
