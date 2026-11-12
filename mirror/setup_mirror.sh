#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
REPO="maciejonisiewicz/railsentinel-app"
if ! gh repo view "$REPO" > /dev/null 2>&1; then
  gh repo create "$REPO" --public --description "Kopia lustrzana aplikacji RailSentinel (github.io), odświeżana automatycznie z repozytorium railsentinel"
fi
W=$(mktemp -d)
git -C "$W" init -q -b main
mkdir -p "$W/.github/workflows"
cp README.md "$W/README.md"
cp sync.yml "$W/.github/workflows/sync.yml"
git -C "$W" add -A
git -C "$W" -c user.name="Maciej Onisiewicz" -c user.email="$(git config user.email)" commit -q -m "Kopia lustrzana: workflow synchronizacji"
git -C "$W" push -q -f "https://github.com/$REPO.git" main
rm -rf "$W"
gh workflow run sync.yml -R "$REPO"
echo "Czekam na pierwszą synchronizację..."
sleep 15
for i in $(seq 1 40); do
  s=$(gh run list -R "$REPO" --workflow=sync.yml --limit 1 --json status,conclusion --jq '.[0].status + " " + .[0].conclusion' 2>/dev/null || echo "")
  case "$s" in
    "completed success") break ;;
    "completed "*) echo "Synchronizacja nieudana: $s"; exit 1 ;;
  esac
  sleep 10
done
gh api -X POST "repos/$REPO/pages" -f build_type=legacy -f "source[branch]=gh-pages" -f "source[path]=/" > /dev/null 2>&1 || true
echo "Gotowe: https://maciejonisiewicz.github.io/railsentinel-app/ (pierwsze uruchomienie Pages trwa 1-2 minuty)"
