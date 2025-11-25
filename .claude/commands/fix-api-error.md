# Fix API Error Command

Diagnose and fix Shopify or OpenAI API errors.

## Usage
```
/fix-api-error <error description or message>
```

## Process

### Step 1: Identify Error Type

**Shopify GraphQL Errors:**
- `userErrors` array in response - Validation issues
- HTTP 401 - Authentication failure
- HTTP 429 - Rate limit exceeded
- HTTP 5xx - Shopify server issues

**OpenAI Errors:**
- `Unsupported parameter: 'max_tokens'` - Using wrong parameter for GPT-5/o-series
- `Unsupported value: 'temperature'` - Using temperature with reasoning model
- HTTP 429 - Quota exceeded or rate limit
- HTTP 401 - Invalid API key

### Step 2: Check Common Causes

**For Shopify "Unsupported" errors:**
1. Check mutation signature against `@requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md`
2. Verify using `product` parameter (not `input`)
3. Verify using `ProductCreateInput` type
4. Check field names (`descriptionHtml` not `bodyHTML`)

**For OpenAI parameter errors:**
1. Check if model is reasoning model (GPT-5, o1, o3, o4)
2. For reasoning models:
   - Use `max_completion_tokens` (not `max_tokens`)
   - Do NOT include: temperature, top_p, presence_penalty, frequency_penalty
3. Verify with `@requirements/OPENAI_API_REQUIREMENTS.md`

**For authentication errors:**
1. Verify credentials in config.json
2. Check API token permissions/scopes
3. Verify token hasn't expired

### Step 3: Apply Fix

**Pattern for Shopify API fix:**
```python
# Before (wrong)
variables = {"input": product_input}

# After (correct for 2025-10)
variables = {"product": product_input}
```

**Pattern for OpenAI fix:**
```python
# Check model type first
if is_reasoning_model(model):
    api_params["max_completion_tokens"] = 2048
    # Do NOT add temperature
else:
    api_params["max_tokens"] = 2048
    api_params["temperature"] = 0.7
```

### Step 4: Add Error Handling
Ensure proper error handling exists:

```python
# For Shopify
user_errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
if user_errors:
    for error in user_errors:
        logging.error(f"Shopify error: {error.get('field')}: {error.get('message')}")

# For OpenAI
try:
    response = client.chat.completions.create(**params)
except openai.APIError as e:
    logging.error(f"OpenAI API error: {e}")
    # Implement fallback
```

### Step 5: Verify Fix
- Run relevant tests
- Test with actual API call if safe
- Check logs for successful response

## Examples
```
/fix-api-error Unsupported parameter 'max_tokens' with gpt-5
/fix-api-error productCreate userErrors: "Title can't be blank"
/fix-api-error Rate limit exceeded
```
