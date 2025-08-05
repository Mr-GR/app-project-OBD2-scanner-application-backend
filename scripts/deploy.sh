#!/bin/bash

# Deployment script for different environments
# Usage: ./scripts/deploy.sh [development|staging|production]

set -e  # Exit on any error

ENVIRONMENT=${1:-development}
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

echo "🚀 Deploying to $ENVIRONMENT environment..."

case $ENVIRONMENT in
  "development")
    echo "📁 Loading development environment..."
    source environments/development/.env
    echo "🔧 Starting development server (native Python)..."
    echo "📋 Environment: $ENVIRONMENT"
    echo "🗄️  Database: Local PostgreSQL"
    echo "🚀 Server will start on http://192.168.1.48:8080"
    cd "$PROJECT_ROOT"
    python main.py
    ;;
    
  "staging")
    echo "📁 Loading staging environment..."
    cd "$PROJECT_ROOT/environments/staging"
    echo "🐳 Starting staging containers..."
    docker-compose up -d
    echo "✅ Staging deployed! API: http://192.168.1.48:8081"
    ;;
    
  "production")
    echo "📁 Loading production environment..."
    cd "$PROJECT_ROOT/environments/production"
    echo "🐳 Starting production containers..."
    docker-compose up -d
    echo "✅ Production deployed! API: http://192.168.1.48:8082"
    ;;
    
  *)
    echo "❌ Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [development|staging|production]"
    exit 1
    ;;
esac