#!/bin/bash

# Build and push all Pak'nSave services to TrueNAS registry

set -e  # Exit on error

REGISTRY="192.168.1.85:5000"
PLATFORM="linux/amd64"

echo "🔨 Building and pushing Pak'nSave services..."
echo ""

# ========================
# API
# ========================
echo "📦 Building API image..."
docker build --platform $PLATFORM -t $REGISTRY/paknsave-api:latest ./meal-api
echo "✓ API image built"

echo "📤 Pushing API image..."
docker push $REGISTRY/paknsave-api:latest
echo "✓ API image pushed"
echo ""

# ========================
# PWA
# ========================
echo "📦 Building PWA image..."
docker build --platform $PLATFORM -t $REGISTRY/paknsave-pwa:latest ./meal-pwa
echo "✓ PWA image built"

echo "📤 Pushing PWA image..."
docker push $REGISTRY/paknsave-pwa:latest
echo "✓ PWA image pushed"
echo ""

# ========================
# Scraper
# ========================
echo "📦 Building Scraper image..."
docker build --platform $PLATFORM -t $REGISTRY/pakn-scraper:latest ./pakn-scraper
echo "✓ Scraper image built"

echo "📤 Pushing Scraper image..."
docker push $REGISTRY/pakn-scraper:latest
echo "✓ Scraper image pushed"
echo ""

# ========================
# Planner
# ========================
echo "📦 Building Planner image..."
docker build --platform $PLATFORM -t $REGISTRY/paknsave-planner:latest ./paknsave-planner
echo "✓ Planner image built"

echo "📤 Pushing Planner image..."
docker push $REGISTRY/paknsave-planner:latest
echo "✓ Planner image pushed"
echo ""

echo "✅ All done! Images pushed to $REGISTRY"
echo ""
echo "Next steps in TrueNAS Scale:"
echo "  1. Update each app image tag to 'latest'"