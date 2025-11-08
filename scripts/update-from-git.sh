#!/usr/bin/env bash
# Safe update-from-git script
# - backs up key local files
# - uses `git pull --rebase --autostash` to preserve local edits when possible
# - rebuilds the Docker stack

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

timestamp() { date +%Y%m%d-%H%M%S; }

BACKUP_DIR="backups/update-$(timestamp)"
mkdir -p "$BACKUP_DIR"

echo "🔄 Safe update EM340D from GitHub"
echo "Repo: $REPO_ROOT"
echo

echo "1) Stopping Docker compose (if running)"
docker compose down || true

echo
echo "2) Backing up local important files to: $BACKUP_DIR"
# Backup docker-compose and env/config if present
for f in .env docker-compose.yml docker-compose.yaml config; do
	if [ -e "$f" ]; then
		echo "  - backing up $f"
		cp -a "$f" "$BACKUP_DIR/" || true
	fi
done

echo
echo "3) Show local git status (brief)"
git status --short || true

echo
echo "4) Pulling latest changes (rebase, autostash local edits)"
if git --version >/dev/null 2>&1 && git pull --rebase --autostash origin main; then
	echo "✓ Pulled and rebased successfully"
else
	echo "Warning: automatic rebase/autostash failed. Trying a fast-forward merge..."
	if git fetch origin && git merge --ff-only origin/main; then
		echo "✓ Fast-forwarded to origin/main"
	else
		echo
		echo "ERROR: Could not automatically update the branch."
		echo "Your local changes are backed up in: $BACKUP_DIR"
		echo "Please resolve conflicts manually. Suggested steps:" 
		echo "  git fetch origin"
		echo "  git status --short"
		echo "  git pull --rebase --autostash origin main  # try again"
		echo "  # or inspect backups in $BACKUP_DIR and restore what you need"
		exit 1
	fi
fi

echo
echo "5) Rebuilding and restarting the service"
if [ -x "./scripts/quick-rebuild.sh" ]; then
	./scripts/quick-rebuild.sh
else
	echo "scripts/quick-rebuild.sh not found or not executable. Running docker compose up -d"
	docker compose build --no-cache || true
	docker compose up -d
fi

echo
echo "✅ Update complete!"
echo
echo "Next steps:"
echo "  - Check container status: docker compose ps"
echo "  - View logs: ./scripts/logs.sh -f"
echo "  - If you had local changes, inspect backups: $BACKUP_DIR"
