#!/bin/bash
# Met à jour le bot depuis GitHub et redémarre le conteneur.
# Usage : ./update.sh

set -e

echo "📥 Pull des dernières modifs depuis GitHub..."
git pull

echo "🔨 Rebuild de l'image Docker..."
docker compose build

echo "♻️  Redémarrage du conteneur..."
docker compose up -d

echo "✅ Mise à jour terminée. Logs en direct :"
docker compose logs -f --tail=50
