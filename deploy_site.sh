#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
curl -sf "https://raw.githubusercontent.com/maciejonisiewicz/railsentinel/gh-pages/data/live.js" -o /tmp/rs_live.js \
  && grep -q '"issued"' /tmp/rs_live.js && cp /tmp/rs_live.js web/data/live.js || true
SITE=$(mktemp -d)
cp -R web/. "$SITE/"
cp docs/RailSentinel_praca_konkursowa.pdf "$SITE/" 2>/dev/null || true
mkdir -p "$SITE/video"
[ -f video/RailSentinel_film.mp4 ] && cp video/RailSentinel_film.mp4 "$SITE/video/railsentinel.mp4"
[ -f video/poster.jpg ] && cp video/poster.jpg "$SITE/video/poster.jpg"
echo "railsentinel.pl" > "$SITE/CNAME"
touch "$SITE/.nojekyll"
cd "$SITE"
git init -q -b gh-pages
git add -A
git -c user.name="Maciej Onisiewicz" -c user.email="$(git -C "$OLDPWD" config user.email)" commit -q -m "Publikacja strony RailSentinel ($(date '+%Y-%m-%d %H:%M'))"
git push -q -f "https://github.com/maciejonisiewicz/railsentinel.git" gh-pages
echo "Wysłano do gh-pages: $(du -sh "$SITE" | cut -f1)"
rm -rf "$SITE"

gh workflow run prognoza.yml -R maciejonisiewicz/railsentinel >/dev/null 2>&1 && echo "Uruchomiono codzienną prognozę" || true
