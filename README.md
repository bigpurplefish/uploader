# Shopify Product Uploader

A Python GUI application for uploading products to Shopify using the GraphQL Admin API (2025-10). Handles products with variants, images, 3D models, metafields, automated collection creation, AI-powered taxonomy assignment, and intelligent shipping weight calculation.

**Version:** 2.6.0
**API Version:** Shopify GraphQL Admin API 2025-10

## Features

- **Bulk Product Upload**: Upload products with variants, images, and 3D models
- **AI-Powered Enhancement**: Automatic product taxonomy assignment and description rewriting
- **Smart Weight Calculation**: Intelligent shipping weight estimation with multiple data sources
- **Automated Collections**: Three-level taxonomy collections (department, category, subcategory)
- **Resume Capability**: Interrupt and resume uploads without losing progress
- **Validation**: URL validation, taxonomy validation, and image alt tag checking
- **Purchase Options**: Configurable purchase and delivery options per product category

## Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone git@github.com:bigpurplefish/uploader.git
   cd uploader
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run setup script** (first time only)
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

### Running the Application

```bash
python3 uploader.py
```

## Development

### Requirements

- Python 3.8+
- pyenv (recommended for virtual environment management)
- See `requirements.txt` for Python package dependencies

### Testing

This project includes a comprehensive test suite covering all core functionality.

#### Running Tests

**Quick method:**
```bash
./tests/run_tests.sh
```

**Manual method:**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=uploader_modules --cov-report=html

# Run specific test file
pytest tests/test_utils.py

# Run specific test class
pytest tests/test_utils.py::TestValidateTaxonomyAssignment

# Run specific test
pytest tests/test_utils.py::TestValidateTaxonomyAssignment::test_valid_assignment
```

#### Test Coverage

The test suite includes 133 tests covering:

- **Utility Functions** (test_utils.py): URL validation, taxonomy validation, category extraction, image filtering
- **State Management** (test_state.py): Upload state, collections, products, taxonomy cache
- **Configuration** (test_config.py): Config file management, logging setup, dual logging pattern
- **Taxonomy Validation** (test_taxonomy_validation.py): Structure loading, assignment validation, edge cases
- **Weight Calculation** (test_weight_calculation.py): All weight estimation scenarios, liquid conversions, safety margins

Current coverage: ~9% overall (91% of utils.py, 70% of state.py, 67% of config.py)

*Note: Coverage focuses on testable utility modules. GUI, API integration, and main processing logic require manual testing.*

#### Viewing Coverage Report

After running tests with coverage:
```bash
open tests/htmlcov/index.html
```

### Project Structure

```
uploader/
├── uploader.py                 # Main application entry point
├── uploader_modules/           # Core modules
│   ├── config.py              # Configuration management
│   ├── state.py               # State file management
│   ├── utils.py               # Utility functions
│   ├── openai_api.py          # OpenAI API integration
│   ├── claude_api.py          # Claude API integration
│   ├── shopify_api.py         # Shopify GraphQL API
│   └── gui.py                 # GUI components
├── tests/                      # Test suite
│   ├── conftest.py            # Pytest fixtures
│   ├── test_*.py              # Test files
│   ├── samples/               # Test data
│   └── run_tests.sh           # Test runner script
├── docs/                       # Documentation
├── requirements.txt            # Production dependencies
└── requirements-dev.txt        # Development dependencies
```

### Development Workflow

This project follows the mandatory workflow specified in `/Users/moosemarketer/Code/shared-docs/python/`:

1. **Write Code**: Implement features or fixes
2. **Write Tests**: Create comprehensive tests for new functionality
3. **Run Tests**: Execute test suite with `./tests/run_tests.sh`
4. **Fix Errors**: Address any test failures
5. **Re-run Tests**: Verify all tests pass
6. **Commit**: Only commit when tests pass

**Important:** Never commit code without passing tests. This is non-negotiable.

### Contributing

1. Follow the development workflow above
2. Ensure all tests pass before committing
3. Use Context7 MCP tools for library documentation
4. Follow coding standards in shared-docs
5. Update tests for any new functionality

## Configuration

Configuration is stored in `config.json` (not committed to repository):

```json
{
  "SHOPIFY_STORE_URL": "your-store.myshopify.com",
  "SHOPIFY_ACCESS_TOKEN": "your-access-token",
  "CLAUDE_API_KEY": "your-claude-key",
  "OPENAI_API_KEY": "your-openai-key",
  "USE_AI_ENHANCEMENT": true,
  "AI_PROVIDER": "claude"
}
```

## State Files

The application manages several state files:

- **upload_state.json**: Processing checkpoint for resume capability
- **collections.json**: Created collection tracking
- **products.json**: Full product restore backup
- **product_taxonomy.json**: Shopify taxonomy cache

## AI Integration

The application uses AI (Claude or OpenAI) for:

1. **Taxonomy Assignment**: Automatically categorize products into department → category → subcategory
2. **Description Rewriting**: Apply voice and tone guidelines to product descriptions
3. **Weight Estimation**: Intelligent shipping weight calculation when data is incomplete
4. **Purchase Options**: Determine applicable purchase and delivery methods per product

See `docs/VOICE_AND_TONE_GUIDELINES.md` and `docs/PRODUCT_TAXONOMY.md` for details.

## Documentation

- **docs/README.md**: User guide and feature overview
- **docs/TECHNICAL_DOCS.md**: Architecture and design decisions
- **docs/QUICK_START.md**: Getting started guide
- **docs/PRODUCT_TAXONOMY.md**: Product taxonomy structure
- **docs/VOICE_AND_TONE_GUIDELINES.md**: Content standards
- **CLAUDE.md**: AI assistant guidance and project instructions

## License

Proprietary - Big Purple Fish / Garoppos Hardware

## Support

For issues or questions, contact the development team or open an issue at:
https://github.com/bigpurplefish/uploader/issues
