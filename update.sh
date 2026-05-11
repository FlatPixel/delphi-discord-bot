#!/bin/bash
# Pulls the latest changes from GitHub and restarts the container.
# Usage: ./update.sh

set -e

echo "📥 Pulling latest changes from GitHub..."
git pull

echo "🔨 Rebuilding Docker image..."
docker compose build

echo "♻️  Restarting container..."
docker compose up -d

echo "✅ Update complete. Live logs:"
docker compose logs -f --tail=50
