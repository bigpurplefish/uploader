#!/bin/bash
# Test runner script for Shopify Product Uploader
# Runs all tests with coverage reporting

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Running Shopify Product Uploader Tests${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}ERROR: pytest is not installed${NC}"
    echo "Install it with: pip install -r requirements-dev.txt"
    exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

echo -e "${YELLOW}Project Root:${NC} $PROJECT_ROOT"
echo -e "${YELLOW}Running tests from:${NC} $SCRIPT_DIR"
echo ""

# Run pytest with coverage
echo -e "${YELLOW}Running tests...${NC}"
echo ""

pytest tests/ \
    --verbose \
    --tb=short \
    --color=yes \
    --cov=uploader_modules \
    --cov-report=term-missing \
    --cov-report=html:tests/htmlcov \
    "$@"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Coverage report saved to: ${YELLOW}tests/htmlcov/index.html${NC}"
    echo ""
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ Tests failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
fi

exit $EXIT_CODE
