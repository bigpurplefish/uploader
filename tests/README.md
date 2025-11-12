# Shopify Product Uploader - Test Suite

## Overview

This test suite provides comprehensive coverage of all functionality in the Shopify Product Uploader, including utility functions, state management, configuration, API interactions, and end-to-end workflows.

## Test Structure

```
tests/
├── README.md                           # This file
├── conftest.py                         # Pytest fixtures and configuration
├── test_utils.py                       # Utility function tests
├── test_state.py                       # State management tests
├── test_config.py                      # Configuration tests
├── test_taxonomy_validation.py         # Taxonomy validation tests
├── test_weight_calculation.py          # Weight calculation logic tests
├── test_shopify_api.py                 # Shopify API interaction tests (mocked)
├── test_ai_integration.py              # AI provider tests (mocked)
├── test_integration.py                 # End-to-end integration tests
├── samples/                            # Sample data for testing
│   ├── sample_products.json
│   ├── sample_taxonomy.md
│   └── sample_config.json
└── output/                             # Test output files (gitignored)
```

## Running Tests

### Quick Test (Fast tests only)
```bash
./run_tests.sh
```

### Full Test Suite (All tests including integration)
```bash
./run_tests.sh --all
```

### Specific Test File
```bash
pytest tests/test_utils.py -v
```

### With Coverage Report
```bash
pytest --cov=uploader_modules --cov-report=html
```

## Test Coverage

### Utils Module (`test_utils.py`)
- ✅ `is_shopify_cdn_url()` - URL validation
- ✅ `key_to_label()` - Key formatting
- ✅ `extract_category_subcategory()` - Category extraction
- ✅ `extract_unique_option_values()` - Option value extraction
- ✅ `validate_image_urls()` - Image URL validation
- ✅ `format_value_for_filter_tag()` - Filter tag formatting
- ✅ `generate_image_filter_hashtags()` - Hashtag generation
- ✅ `validate_image_alt_tags_for_filtering()` - Alt tag validation
- ✅ `load_taxonomy_structure()` - Taxonomy file parsing
- ✅ `validate_taxonomy_assignment()` - Taxonomy validation

### State Module (`test_state.py`)
- ✅ `load_state()` / `save_state()` - Upload state persistence
- ✅ `load_collections()` / `save_collections()` - Collections tracking
- ✅ `load_products()` / `save_products()` - Product restore points
- ✅ `update_product_in_restore()` - Product update tracking
- ✅ `load_taxonomy_cache()` / `save_taxonomy_cache()` - Taxonomy caching

### Config Module (`test_config.py`)
- ✅ `load_config()` / `save_config()` - Configuration management
- ✅ `setup_logging()` - Logging configuration
- ✅ `log_and_status()` - Dual logging pattern

### Taxonomy Validation (`test_taxonomy_validation.py`)
- ✅ Valid taxonomy assignment (department/category/subcategory)
- ✅ Invalid department detection
- ✅ Invalid category detection
- ✅ Invalid subcategory detection
- ✅ Error message generation
- ✅ Suggestion generation

### Weight Calculation (`test_weight_calculation.py`)
- ✅ Priority A: Using existing variant.weight
- ✅ Priority B: Extracting from text (with unit conversions)
- ✅ Priority C: Calculating from dimensions (concrete products)
- ✅ Priority D: Estimating from context
- ✅ Liquid conversions (gallons/fl oz → lbs)
- ✅ Packaging weight application
- ✅ Safety margin calculation (10%)
- ✅ Confidence level assignment

### Shopify API (`test_shopify_api.py`)
- ✅ Collection search (mocked)
- ✅ Collection creation (mocked)
- ✅ Product creation (mocked)
- ✅ Variant bulk creation (mocked)
- ✅ Taxonomy search (mocked)
- ✅ Error handling

### AI Integration (`test_ai_integration.py`)
- ✅ OpenAI taxonomy assignment (mocked)
- ✅ OpenAI description rewriting (mocked)
- ✅ Claude taxonomy assignment (mocked)
- ✅ Claude description rewriting (mocked)
- ✅ Weight estimation in AI response
- ✅ Purchase options in AI response

### Integration Tests (`test_integration.py`)
- ✅ Full product upload workflow (mocked APIs)
- ✅ Collection creation workflow
- ✅ Resume functionality
- ✅ Error recovery
- ✅ State persistence

## Test Data

### Sample Products
Located in `samples/sample_products.json`:
- Techo-Bloc concrete pavers with dimensions
- Pet food products with weight specifications
- Liquid products (gallons/fl oz)
- Products without weight data

### Sample Taxonomy
Located in `samples/sample_taxonomy.md`:
- Simplified version of PRODUCT_TAXONOMY.md for testing
- Includes all department/category/subcategory structure

## Requirements

```bash
pip install pytest pytest-cov pytest-mock requests-mock
```

## Writing New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test functions: `test_<function_name>_<scenario>()`
- Example: `test_validate_taxonomy_assignment_invalid_department()`

### Using Fixtures
```python
def test_example(sample_products):
    # sample_products fixture provides test data
    assert len(sample_products) > 0
```

### Mocking External Calls
```python
def test_api_call(requests_mock):
    requests_mock.post('https://api.example.com', json={'success': True})
    # Your test code here
```

## Continuous Integration

Tests should be run:
- ✅ Before every commit
- ✅ In CI/CD pipeline (GitHub Actions)
- ✅ Before merging pull requests
- ✅ After dependency updates

## Troubleshooting

### Tests Fail Due to Missing Files
- Ensure `samples/` directory has all required test data
- Check that `.python-version` matches expected Python version (3.12.9)

### Tests Fail Due to Import Errors
- Verify virtual environment is activated
- Run `pip install -r requirements.txt`
- Check that `uploader_modules/` is in Python path

### Integration Tests Are Slow
- Run quick tests only: `./run_tests.sh` (skips slow integration tests)
- Mark slow tests with `@pytest.mark.slow` decorator

## Test Metrics

Target metrics:
- **Code Coverage**: > 80%
- **Test Pass Rate**: 100%
- **Test Execution Time**: < 30 seconds (quick tests)

## Contributing

When adding new functionality:
1. Write tests FIRST (TDD approach) or alongside code
2. Ensure new tests pass
3. Verify existing tests still pass
4. Update this README if adding new test categories
5. Only commit after 100% test pass rate

---

**Last Updated**: 2025-11-12
**Test Suite Version**: 1.0
