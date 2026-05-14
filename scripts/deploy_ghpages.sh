#!/usr/bin/env bash
# Deploy the static LTDB mirror to the gh-pages branch.
#
# Usage:
#   scripts/deploy_ghpages.sh [--from DIR] [--remote REMOTE] [--dry-run]
#
# Defaults:
#   --from     test-output/
#   --remote   origin
#
# The gh-pages branch is force-pushed as an orphan commit (no history)
# to keep the repo size stable across rebuilds.
#
# GitHub Pages must be configured to serve from the gh-pages branch root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$REPO_ROOT/test-output"
REMOTE="origin"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)    SOURCE="$2"; shift 2 ;;
    --remote)  REMOTE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$SOURCE/ltdb" ]]; then
  echo "Source directory not found or not built: $SOURCE/ltdb" >&2
  echo "Run scripts/build_static_mirror.sh first." >&2
  exit 1
fi

# Warn if any file would exceed GitHub's 100 MB limit
LARGE=$(find "$SOURCE" -size +95M -type f 2>/dev/null | head -5)
if [[ -n "$LARGE" ]]; then
  echo "WARNING: files >95 MB found (GitHub will reject >100 MB):" >&2
  echo "$LARGE" >&2
  echo "Re-run build_static_mirror.sh without --no-gzip." >&2
  exit 1
fi

WORKTREE="$REPO_ROOT/.gh-pages-deploy"
BRANCH="gh-pages"
COMMIT_MSG="Deploy $(date -u '+%Y-%m-%d %H:%M UTC')"

cleanup() { git -C "$REPO_ROOT" worktree remove --force "$WORKTREE" 2>/dev/null || true; }
trap cleanup EXIT

echo "==> Source: $SOURCE"
echo "==> Target: $REMOTE/$BRANCH"
[[ "$DRY_RUN" == true ]] && echo "==> DRY RUN — no push"
echo ""

# Add worktree for gh-pages (creates branch if it doesn't exist)
if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git -C "$REPO_ROOT" worktree add "$WORKTREE" "$BRANCH"
else
  git -C "$REPO_ROOT" worktree add --orphan "$WORKTREE" "$BRANCH"
fi

# Replace content
echo "Syncing files..."
git -C "$WORKTREE" rm -rf --quiet . 2>/dev/null || true
# Copy the ltdb mirror content to the root of gh-pages
rsync -a --delete "$SOURCE/ltdb/" "$WORKTREE/"
# Copy any other docs/ content (summary.md etc.) if present
if [[ -d "$SOURCE/static" ]]; then
  rsync -a "$SOURCE/static/" "$WORKTREE/static/"
fi

git -C "$WORKTREE" add -A
if git -C "$WORKTREE" diff --cached --quiet; then
  echo "Nothing changed — gh-pages is already up to date."
  exit 0
fi

git -C "$WORKTREE" commit -m "$COMMIT_MSG"

if [[ "$DRY_RUN" == true ]]; then
  echo "Dry run complete. Commit ready but not pushed."
  git -C "$WORKTREE" show --stat HEAD
else
  echo "Pushing to $REMOTE/$BRANCH..."
  git -C "$WORKTREE" push --force "$REMOTE" "$BRANCH"
  echo ""
  echo "Deployed. GitHub Pages will update in ~1 minute."
fi
