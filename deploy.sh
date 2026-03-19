#!/bin/bash
# Deploy NYC Kids Signal Finder Dashboard
# Run this on the VPS after cloning the repo

set -e

echo "=== NYC Kids Signal Finder — Deploy ==="

# 1. Clone or pull
if [ -d "reddit-signal-finder" ]; then
    echo "Updating existing repo..."
    cd reddit-signal-finder
    git pull
else
    echo "Cloning repo..."
    git clone git@github.com:dmt29yt2043-debug/Reddita-Signal-Finder.git reddit-signal-finder
    cd reddit-signal-finder
fi

# 2. Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file missing. Create it with:"
    echo "  FIRECRAWL_API_KEY=..."
    echo "  OPENAI_API_KEY=..."
    echo "  GOOGLE_SPREADSHEET_ID=..."
    exit 1
fi

# 3. Build and run
echo "Building Docker containers..."
docker compose build

echo "Starting services..."
docker compose up -d

# 4. Import data if DB is empty
echo "Importing CSV data..."
docker compose exec web python -m dashboard.import_csv

echo ""
echo "=== Deploy complete ==="
echo "Dashboard: https://kids.srv1362562.hstgr.cloud"
echo ""
echo "Commands:"
echo "  docker compose logs -f        # View logs"
echo "  docker compose restart web    # Restart app"
echo "  docker compose down           # Stop all"
