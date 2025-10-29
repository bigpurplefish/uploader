#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Shopify Product Uploader - Setup Script"
echo "=========================================="
echo ""

# Check if we're in the right directory (should have the main script)
if [ ! -f "shopify_product_uploader.py" ]; then
    echo -e "${RED}❌ Error: shopify_product_uploader.py not found in current directory${NC}"
    echo ""
    echo "Please ensure all downloaded files are in the current directory and run this script again."
    echo ""
    echo "Expected files:"
    echo "  - shopify_product_uploader.py"
    echo "  - requirements.txt"
    echo "  - README.md"
    echo "  - QUICK_START.md"
    echo "  - TECHNICAL_DOCS.md"
    echo "  - DEPLOYMENT_GUIDE.md"
    echo "  - CHANGELOG.md"
    echo "  - config_sample.json"
    echo ""
    exit 1
fi

echo -e "${BLUE}Step 1: Creating directory structure...${NC}"
echo ""

mkdir -p docs
mkdir -p input
mkdir -p output
mkdir -p logs

echo -e "${GREEN}✅ Created directories:${NC}"
echo "   - docs/     (documentation files)"
echo "   - input/    (your product JSON files)"
echo "   - output/   (result files)"
echo "   - logs/     (log files)"
echo ""

echo -e "${BLUE}Step 2: Organizing files...${NC}"
echo ""

# Move documentation files to docs/ folder
if [ -f "README.md" ]; then
    mv README.md docs/ && echo -e "${GREEN}✅ Moved README.md to docs/${NC}"
fi

if [ -f "QUICK_START.md" ]; then
    mv QUICK_START.md docs/ && echo -e "${GREEN}✅ Moved QUICK_START.md to docs/${NC}"
fi

if [ -f "TECHNICAL_DOCS.md" ]; then
    mv TECHNICAL_DOCS.md docs/ && echo -e "${GREEN}✅ Moved TECHNICAL_DOCS.md to docs/${NC}"
fi

if [ -f "DEPLOYMENT_GUIDE.md" ]; then
    mv DEPLOYMENT_GUIDE.md docs/ && echo -e "${GREEN}✅ Moved DEPLOYMENT_GUIDE.md to docs/${NC}"
fi

if [ -f "CHANGELOG.md" ]; then
    mv CHANGELOG.md docs/ && echo -e "${GREEN}✅ Moved CHANGELOG.md to docs/${NC}"
fi

if [ -f "SETUP_INSTRUCTIONS.md" ]; then
    mv SETUP_INSTRUCTIONS.md docs/ && echo -e "${GREEN}✅ Moved SETUP_INSTRUCTIONS.md to docs/${NC}"
fi

# Keep these files in root
echo -e "${GREEN}✅ Main script in place: shopify_product_uploader.py${NC}"
echo -e "${GREEN}✅ Dependencies file in place: requirements.txt${NC}"
echo -e "${GREEN}✅ Config sample in place: config_sample.json${NC}"
echo ""

echo -e "${BLUE}Step 3: Creating .gitignore file...${NC}"
cat > .gitignore << 'EOF'
# Configuration (contains credentials - DO NOT COMMIT)
config.json

# State file (temporary)
upload_state.json

# Output and log files
output/
logs/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.py[cod]
*$py.class

# C extensions
*.so

# Virtual environment
venv/
env/
ENV/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/
EOF

echo -e "${GREEN}✅ Created .gitignore file${NC}"
echo ""

echo -e "${BLUE}Step 4: Checking Python installation...${NC}"
echo ""

# Check if python3 is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
    echo -e "${GREEN}✅ Found Python 3${NC}"
    python3 --version
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PIP_CMD="pip"
    echo -e "${GREEN}✅ Found Python${NC}"
    python --version
else
    echo -e "${RED}❌ Python not found!${NC}"
    echo ""
    echo "Please install Python 3.7 or higher:"
    echo "  brew install python3"
    echo ""
    exit 1
fi
echo ""

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.7"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then 
    echo -e "${GREEN}✅ Python version $PYTHON_VERSION is compatible (requires 3.7+)${NC}"
else
    echo -e "${RED}❌ Python version $PYTHON_VERSION is too old (requires 3.7+)${NC}"
    echo ""
    echo "Please upgrade Python:"
    echo "  brew upgrade python3"
    echo ""
    exit 1
fi
echo ""

echo -e "${BLUE}Step 5: Installing Python dependencies...${NC}"
echo ""

# Check if pip is available
if ! command -v $PIP_CMD &> /dev/null; then
    echo -e "${RED}❌ pip not found!${NC}"
    echo ""
    echo "Installing pip..."
    $PYTHON_CMD -m ensurepip --upgrade
    echo ""
fi

# Install requirements
echo "Installing required packages..."
echo ""

if $PIP_CMD install -r requirements.txt; then
    echo ""
    echo -e "${GREEN}✅ Successfully installed all dependencies${NC}"
else
    echo ""
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    echo ""
    echo "Try installing manually:"
    echo "  $PIP_CMD install ttkbootstrap requests"
    echo ""
    exit 1
fi
echo ""

echo -e "${BLUE}Step 6: Verifying installation...${NC}"
echo ""

# Verify packages are installed
if $PYTHON_CMD -c "import ttkbootstrap; import requests" 2>/dev/null; then
    echo -e "${GREEN}✅ All required packages are installed correctly${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Could not verify package installation${NC}"
    echo "   Try running the script anyway - it might still work!"
fi
echo ""

# Check if Homebrew is installed (optional but helpful)
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}ℹ️  Note: Homebrew not detected${NC}"
    echo "   Homebrew is optional but recommended for managing Python on Mac"
    echo "   Install from: https://brew.sh"
    echo ""
fi

echo "=========================================="
echo -e "${GREEN}Setup Complete! 🎉${NC}"
echo "=========================================="
echo ""
echo "Directory structure:"
echo ""
echo "$(pwd | xargs basename)/"
echo "├── shopify_product_uploader.py   ← Main script"
echo "├── requirements.txt               ← Dependencies (installed)"
echo "├── config_sample.json            ← Example config"
echo "├── setup.sh                      ← This setup script"
echo "├── .gitignore                    ← Git ignore rules"
echo "├── docs/                         ← All documentation"
echo "│   ├── README.md"
echo "│   ├── QUICK_START.md"
echo "│   ├── TECHNICAL_DOCS.md"
echo "│   ├── DEPLOYMENT_GUIDE.md"
echo "│   ├── CHANGELOG.md"
echo "│   └── SETUP_INSTRUCTIONS.md"
echo "├── input/                        ← Put your JSON files here"
echo "├── output/                       ← Results will be saved here"
echo "└── logs/                         ← Logs will be saved here"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Get Shopify credentials (see docs/README.md)"
echo "2. Place your input JSON in the input/ folder"
echo "3. Run the application:"
echo -e "   ${BLUE}$PYTHON_CMD shopify_product_uploader.py${NC}"
echo ""
echo -e "${YELLOW}Quick reference:${NC}"
echo "• View quick start guide:  cat docs/QUICK_START.md"
echo "• View full documentation: cat docs/README.md"
echo "• Run the application:     $PYTHON_CMD shopify_product_uploader.py"
echo ""
echo -e "${GREEN}Happy uploading! 🚀${NC}"
echo ""
