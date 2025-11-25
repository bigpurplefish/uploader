# Add Shopify Mutation Command

Add a new Shopify GraphQL mutation following project patterns.

## Usage
```
/add-shopify-mutation <mutation name>
```

## Process

### Step 1: Research the Mutation
1. Check Shopify GraphQL docs for correct signature
2. Review `@requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md` for patterns
3. Look at existing mutations in `uploader_modules/shopify_api.py`

### Step 2: Define Mutation String
Follow this pattern:

```python
MUTATION_NAME = """
mutation mutationName($param1: Type1!, $param2: Type2) {
  mutationName(param1: $param1, param2: $param2) {
    returnedObject {
      id
      # other fields
    }
    userErrors {
      field
      message
    }
  }
}
"""
```

**Key Requirements:**
- Always include `userErrors { field message }` in return
- Use proper variable types with `!` for required
- Match parameter names to API 2025-10 specs

### Step 3: Create Function
Follow this pattern:

```python
def mutation_function_name(
    param1: str,
    param2: Optional[dict],
    cfg: dict,
    status_fn: Optional[Callable] = None
) -> Optional[dict]:
    """
    Brief description of what this mutation does.

    Args:
        param1: Description of param1
        param2: Description of param2
        cfg: Configuration dictionary with API credentials
        status_fn: Optional callback for status updates

    Returns:
        Dict with created/updated object data, or None on failure
    """
    api_url = f"https://{cfg['SHOPIFY_STORE_URL']}/admin/api/2025-10/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": cfg['SHOPIFY_ACCESS_TOKEN']
    }

    variables = {
        "param1": param1,
        "param2": param2
    }

    try:
        response = requests.post(
            api_url,
            json={"query": MUTATION_NAME, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # Check for GraphQL errors
        if "errors" in result:
            logging.error(f"GraphQL errors: {result['errors']}")
            return None

        # Check for userErrors
        mutation_result = result.get("data", {}).get("mutationName", {})
        user_errors = mutation_result.get("userErrors", [])

        if user_errors:
            for error in user_errors:
                logging.error(f"Mutation error: {error.get('field')}: {error.get('message')}")
            return None

        return mutation_result.get("returnedObject")

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        if status_fn:
            status_fn(f"❌ API request failed: {e}")
        return None
```

### Step 4: Add Tests
Create tests in `tests/test_shopify_api.py`:

```python
@patch('uploader_modules.shopify_api.requests.post')
def test_mutation_function_success(self, mock_post, sample_config):
    """Test successful mutation."""
    mock_post.return_value.json.return_value = {
        "data": {
            "mutationName": {
                "returnedObject": {"id": "gid://shopify/Object/123"},
                "userErrors": []
            }
        }
    }
    mock_post.return_value.raise_for_status = Mock()

    result = mutation_function_name("value", None, sample_config)

    assert result is not None
    assert result["id"] == "gid://shopify/Object/123"
```

### Step 5: Update Documentation
Add mutation to `@requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md`

## Examples
```
/add-shopify-mutation productDelete
/add-shopify-mutation inventoryAdjustQuantities
/add-shopify-mutation collectionAddProducts
```
