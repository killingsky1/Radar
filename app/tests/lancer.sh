#!/usr/bin/env bash
# Teste l'app dans un vrai navigateur, avec des données TEST (jamais publiées).
set -euo pipefail
cd "$(dirname "$0")/.."  # dossier app/
node build.mjs > /dev/null
rm -rf dist-test && cp -r dist dist-test
python3 tests/donnees_test.py dist-test/brut > /dev/null
mkdir -p dist-test/data && cp -r dist-test/brut/app dist-test/data/
python3 -m http.server 8767 -d dist-test > /dev/null 2>&1 &
SERVEUR=$!
trap 'kill $SERVEUR' EXIT
sleep 1
ADRESSE="http://localhost:8767/" node tests/app.test.mjs
