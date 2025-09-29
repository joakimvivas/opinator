#!/bin/bash
# Script to start development environment with proper .env loading

# Load environment variables from .env file
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '#' | sed 's/\r$//' | awk '/=/ {print $1}')
    echo "✅ Loaded environment variables from .env"
else
    echo "❌ .env file not found"
    exit 1
fi

# Start docker-compose services
echo "🚀 Starting Opinator development services..."
docker-compose -f docker-compose.dev.yml up -d $@

echo "🎉 Services started!"
echo "📊 Inngest UI: http://localhost:8288"
echo "🌐 HeadlessX: http://localhost:3001"