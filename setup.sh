#!/bin/bash

# Opinator Setup Script
# This script automates the setup process for the Opinator project

set -e  # Exit on any error

echo "🚀 Setting up Opinator - Multi-Platform Review Scraper"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "devbox.json" ]; then
    echo "❌ Error: Please run this script from the opinator project directory"
    echo "   Make sure you see files like: devbox.json, docker-compose.yml, etc."
    exit 1
fi

echo "📁 Current directory: $(pwd)"

# Step 1: Clone HeadlessX if it doesn't exist
if [ ! -d "HeadlessX" ]; then
    echo "📥 Cloning HeadlessX repository (required dependency)..."
    git clone https://github.com/saifyxpro/HeadlessX.git

    if [ $? -eq 0 ]; then
        echo "✅ HeadlessX cloned successfully"
    else
        echo "❌ Failed to clone HeadlessX. Please check your internet connection."
        exit 1
    fi
else
    echo "✅ HeadlessX directory already exists"
fi

# Step 2: Verify HeadlessX structure
if [ -f "HeadlessX/docker/Dockerfile" ]; then
    echo "✅ HeadlessX structure verified"
else
    echo "❌ HeadlessX structure is incomplete. Re-cloning..."
    rm -rf HeadlessX
    git clone https://github.com/saifyxpro/HeadlessX.git
fi

# Step 3: Create environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📄 Creating .env file from template..."
    cp .env.example .env

    # Generate secure AUTH_TOKEN
    echo "🔐 Generating secure AUTH_TOKEN for HeadlessX..."
    if command -v openssl &> /dev/null; then
        AUTH_TOKEN=$(openssl rand -hex 32)
        sed -i "s/your_secure_random_token_here/$AUTH_TOKEN/" .env
        echo "✅ AUTH_TOKEN generated and configured"
    else
        echo "⚠️  OpenSSL not found. Please manually set AUTH_TOKEN in .env"
        echo "   Generate with: openssl rand -hex 32"
    fi

    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

# Step 4: Create logs directory
mkdir -p logs
echo "✅ Logs directory created"

# Step 5: Check Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker is installed"

    if command -v docker-compose &> /dev/null; then
        echo "✅ Docker Compose is installed"
    else
        echo "⚠️  Docker Compose not found. Please install docker-compose"
    fi
else
    echo "⚠️  Docker not found. Please install Docker to use the full application"
fi

# Step 6: Check Devbox (optional)
if command -v devbox &> /dev/null; then
    echo "✅ Devbox is installed"
else
    echo "⚠️  Devbox not found. Install from: https://www.jetify.com/devbox"
    echo "   Devbox is recommended for development mode"
fi

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Start services:    docker compose -f docker/docker-compose.dev.yml up -d"
echo "   (or production):   docker compose -f docker/docker-compose.prod.yml up -d"
echo "2. Start FastAPI:     devbox shell && start_app"
echo "3. Open browser:      http://localhost:8001"
echo ""
echo "Docker files are now organized in the docker/ directory:"
echo "  - docker/docker-compose.dev.yml  (development)"
echo "  - docker/docker-compose.prod.yml (production)"
echo ""
echo "For more details, check the README.md file"