# Test Command

Generate or run tests for the specified module or feature.

## Usage
```
/test [module name or action]
```

Actions:
- `run` - Run all tests with coverage
- `run <module>` - Run tests for specific module
- `write <module>` - Write/update tests for module
- `coverage` - Generate coverage report

## Process

### For Running Tests

```bash
# Run all tests with coverage
pytest --cov=uploader_modules --cov-report=term-missing

# Run specific module tests
pytest tests/test_<module>.py -v

# Generate HTML coverage report
pytest --cov=uploader_modules --cov-report=html
```

### For Writing Tests

1. **Analyze the module** to understand functions and their behaviors
2. **Review existing fixtures** in `tests/conftest.py`
3. **Create test class** following pattern:

```python
import pytest
from unittest.mock import Mock, patch

class TestModuleName:
    """Tests for module_name module."""

    def test_function_success(self, fixture):
        """Test successful execution."""
        result = function_under_test(fixture)
        assert result == expected

    def test_function_error(self, fixture):
        """Test error handling."""
        with pytest.raises(ExpectedError):
            function_under_test(bad_input)

    @patch('module.external_dependency')
    def test_with_mock(self, mock_dep, fixture):
        """Test with mocked dependency."""
        mock_dep.return_value = mock_response
        result = function_under_test(fixture)
        mock_dep.assert_called_once()
```

### Coverage Targets
- Overall: 90%+
- Critical modules (shopify_api, product_processing): 95%+
- GUI: 80%+ (threading is hard to test)

### Test Categories to Cover
1. **Happy path** - Normal successful execution
2. **Edge cases** - Empty inputs, boundary values
3. **Error handling** - Invalid inputs, API errors
4. **Integration** - Module interactions (with mocks)

## Examples
```
/test run                     # Run all tests
/test run shopify_api         # Run Shopify API tests
/test write config            # Write tests for config module
/test coverage                # Generate coverage report
```
