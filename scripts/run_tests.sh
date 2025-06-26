#!/bin/bash

# Comprehensive test runner script
# Usage: ./scripts/run_tests.sh [database|api|all]

set -e

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}$1${NC}"
    echo "$(printf '=%.0s' {1..60})"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

test_database() {
    print_header "🗄️  DATABASE TESTS"
    echo "Testing database connection, tables, and operations..."
    echo
    
    # Load development environment
    if [ -f "environments/development/.env" ]; then
        export $(cat environments/development/.env | grep -v '^#' | xargs)
        echo "📁 Loaded development environment"
    fi
    
    # Run database tests
    if python scripts/test_database.py; then
        print_success "Database tests completed successfully"
        return 0
    else
        print_error "Database tests failed"
        return 1
    fi
}

test_api() {
    print_header "🌐 API TESTS"
    echo "Testing API endpoints and functionality..."
    echo
    
    # Check if server is running
    if ! curl -s http://localhost:8080/ > /dev/null; then
        print_warning "Server not running, starting server..."
        
        # Load development environment
        if [ -f "environments/development/.env" ]; then
            export $(cat environments/development/.env | grep -v '^#' | xargs)
        fi
        
        # Start server in background
        python main.py &
        SERVER_PID=$!
        
        # Wait for server to start
        echo "⏳ Waiting for server to start..."
        sleep 5
        
        # Check if server started successfully
        if curl -s http://localhost:8080/ > /dev/null; then
            print_success "Server started successfully"
            SERVER_STARTED=true
        else
            print_error "Failed to start server"
            kill $SERVER_PID 2>/dev/null || true
            return 1
        fi
    else
        print_success "Server is already running"
        SERVER_STARTED=false
    fi
    
    # Run API tests
    if python scripts/test_api.py; then
        print_success "API tests completed successfully"
        TEST_RESULT=0
    else
        print_error "API tests failed"
        TEST_RESULT=1
    fi
    
    # Stop server if we started it
    if [ "$SERVER_STARTED" = true ]; then
        print_warning "Stopping test server..."
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    fi
    
    return $TEST_RESULT
}

run_all_tests() {
    print_header "🧪 COMPREHENSIVE TEST SUITE"
    echo "Running all tests for OBD2 Scanner Backend"
    echo
    
    TOTAL_TESTS=0
    PASSED_TESTS=0
    
    # Database tests
    echo
    ((TOTAL_TESTS++))
    if test_database; then
        ((PASSED_TESTS++))
    fi
    
    # API tests
    echo
    ((TOTAL_TESTS++))
    if test_api; then
        ((PASSED_TESTS++))
    fi
    
    # Final summary
    echo
    print_header "📊 FINAL TEST SUMMARY"
    echo "Passed: $PASSED_TESTS/$TOTAL_TESTS test suites"
    
    if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
        print_success "🎉 ALL TESTS PASSED! Your application is working perfectly!"
        return 0
    else
        print_error "⚠️  Some tests failed. Check the output above for details."
        return 1
    fi
}

# Main script logic
case "${1:-all}" in
    "database"|"db")
        test_database
        ;;
    "api")
        test_api
        ;;
    "all"|"")
        run_all_tests
        ;;
    *)
        echo "Usage: $0 [database|api|all]"
        echo
        echo "Options:"
        echo "  database  - Run only database tests"
        echo "  api       - Run only API tests"
        echo "  all       - Run all tests (default)"
        exit 1
        ;;
esac