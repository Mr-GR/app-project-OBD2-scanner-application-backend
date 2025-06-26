#!/bin/bash

# Environment management script
# Usage: source ./scripts/env.sh [development|staging|production]

ENVIRONMENT=${1:-development}
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

echo "🔧 Setting up $ENVIRONMENT environment..."

case $ENVIRONMENT in
  "development"|"staging"|"production")
    ENV_FILE="$PROJECT_ROOT/environments/$ENVIRONMENT/.env"
    
    if [ -f "$ENV_FILE" ]; then
      export ENVIRONMENT=$ENVIRONMENT
      export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
      echo "✅ Environment variables loaded from $ENV_FILE"
      echo "📋 Current environment: $ENVIRONMENT"
      echo "🗄️  Database: $(echo $DATABASE_URL | cut -d'@' -f2)"
    else
      echo "❌ Environment file not found: $ENV_FILE"
      exit 1
    fi
    ;;
    
  *)
    echo "❌ Invalid environment: $ENVIRONMENT"
    echo "Usage: source $0 [development|staging|production]"
    exit 1
    ;;
esac