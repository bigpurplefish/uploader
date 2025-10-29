# OpenAI API Requirements & Compatibility

**Last Updated:** October 2025
**API Version:** Latest (includes GPT-5, o-series reasoning models)

## Overview

This document describes the requirements and compatibility considerations for integrating with the OpenAI API, including breaking changes introduced with GPT-5 and reasoning models.

## Critical API Changes

### Breaking Changes Summary

As of August 2025, OpenAI introduced **multiple breaking changes** with GPT-5 and reasoning models (o1, o3, o4 series):

1. **Token Parameter:** Must use `max_completion_tokens` instead of `max_tokens`
2. **Temperature:** Only supports default value (1), custom values rejected
3. **Sampling Parameters:** `top_p`, `presence_penalty`, `frequency_penalty` not supported
4. **Other Parameters:** `logprobs`, `top_logprobs`, `logit_bias` not supported

### 1. Token Parameter Change (Breaking)

**Problem:** As of August 2025, GPT-5 and reasoning models require a different parameter name for token limits.

**Old Behavior (GPT-4, GPT-3.5):**
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    max_tokens=1024  # ✅ WORKS
)
```

**New Behavior (GPT-5, o-series):**
```python
response = client.chat.completions.create(
    model="gpt-5",
    messages=[...],
    max_tokens=1024  # ❌ ERROR: "Unsupported parameter"
)
```

**Correct Implementation for GPT-5:**
```python
response = client.chat.completions.create(
    model="gpt-5",
    messages=[...],
    max_completion_tokens=1024  # ✅ WORKS
)
```

### Why the Change?

Reasoning models (o1, o3, o4, GPT-5) generate internal "reasoning tokens" that aren't visible in the response but count toward the token limit. The parameter name `max_completion_tokens` more accurately describes what it controls: the maximum number of tokens for the entire completion (visible output + hidden reasoning).

### 2. Temperature Parameter Restriction (Breaking)

**Problem:** GPT-5 and reasoning models reject custom temperature values.

**Error Message:**
```
Error code: 400 - "Unsupported value: 'temperature' does not support 0.3
with this model. Only the default (1) value is supported."
```

**Old Behavior (GPT-4, GPT-3.5):**
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    temperature=0.7  # ✅ WORKS - can control randomness
)
```

**New Behavior (GPT-5, o-series):**
```python
# WRONG - will error
response = client.chat.completions.create(
    model="gpt-5",
    messages=[...],
    temperature=0.7  # ❌ ERROR: "Unsupported value"
)

# CORRECT - omit temperature entirely
response = client.chat.completions.create(
    model="gpt-5",
    messages=[...]
    # temperature omitted - uses default value of 1
)
```

### 3. Complete List of Unsupported Parameters

The following parameters are **completely unsupported** for GPT-5 and reasoning models:

| Parameter | GPT-4/GPT-4o | GPT-5/o-series | Notes |
|-----------|--------------|----------------|-------|
| `max_tokens` | ✅ Supported | ❌ Use `max_completion_tokens` | Breaking |
| `temperature` | ✅ Any value 0-2 | ❌ Only default (1) | Must omit |
| `top_p` | ✅ Supported | ❌ Not supported | Must omit |
| `presence_penalty` | ✅ Supported | ❌ Not supported | Must omit |
| `frequency_penalty` | ✅ Supported | ❌ Not supported | Must omit |
| `logprobs` | ✅ Supported | ❌ Not supported | Must omit |
| `top_logprobs` | ✅ Supported | ❌ Not supported | Must omit |
| `logit_bias` | ✅ Supported | ❌ Not supported | Must omit |

**Why These Restrictions?**

Reasoning models use internal task-based adjustments for their reasoning process. They need consistent behavior and don't support the traditional "creativity knobs" that work with standard language models.

## Model Compatibility Matrix

| Model Series | Parameter Name | Status |
|-------------|----------------|--------|
| GPT-5, GPT-5-mini, GPT-5-nano | `max_completion_tokens` | ✅ Active |
| o1, o1-preview, o1-mini | `max_completion_tokens` | ✅ Active |
| o3, o3-mini | `max_completion_tokens` | ✅ Active |
| o4-mini | `max_completion_tokens` | ✅ Active |
| GPT-4o, GPT-4o-mini | `max_tokens` | ✅ Active |
| GPT-4-turbo | `max_tokens` | ✅ Active |
| GPT-4 | `max_tokens` | ✅ Active |
| GPT-3.5-turbo | `max_tokens` | ⚠️ Legacy |

## Implementation Strategy

Our codebase uses helper functions to handle parameter compatibility:

### Helper Function: Detect Reasoning Models

```python
def is_reasoning_model(model: str) -> bool:
    """
    Determine if a model is a reasoning model (GPT-5, o-series).

    Reasoning models have restricted parameter support:
    - Use 'max_completion_tokens' instead of 'max_tokens'
    - Don't support custom temperature (only default value 1)
    - Don't support: top_p, presence_penalty, frequency_penalty, logprobs, logit_bias

    Returns:
        True if model is a reasoning model, False otherwise
    """
    model_lower = model.lower()

    # GPT-5 series are reasoning models
    if model_lower.startswith("gpt-5"):
        return True

    # o-series are reasoning models (o1, o3, o4)
    if model_lower.startswith("o1") or model_lower.startswith("o3") or model_lower.startswith("o4"):
        return True

    # All other models are NOT reasoning models
    return False


def uses_max_completion_tokens(model: str) -> bool:
    """Convenience wrapper to check token parameter."""
    return is_reasoning_model(model)
```

### Usage Pattern (Complete)

```python
# Build base API call parameters
api_params = {
    "model": model,
    "messages": messages
}

# Add temperature only for non-reasoning models
if not is_reasoning_model(model):
    api_params["temperature"] = 0.7  # Can control for GPT-4/3.5
else:
    # Reasoning models: omit temperature (uses default value 1)
    pass

# Add correct token parameter
if uses_max_completion_tokens(model):
    api_params["max_completion_tokens"] = 2048  # GPT-5/o-series
else:
    api_params["max_tokens"] = 2048  # GPT-4/GPT-3.5

# Make API call with dynamically built parameters
response = client.chat.completions.create(**api_params)
```

### What NOT to Include

**Never include these parameters for reasoning models:**
```python
# ❌ BAD - Will cause errors with GPT-5/o-series
api_params = {
    "model": "gpt-5",
    "messages": messages,
    "temperature": 0.7,           # ❌ Unsupported
    "top_p": 0.9,                 # ❌ Unsupported
    "presence_penalty": 0.6,      # ❌ Unsupported
    "frequency_penalty": 0.5,     # ❌ Unsupported
    "max_tokens": 2048            # ❌ Wrong parameter name
}

# ✅ GOOD - Only supported parameters
api_params = {
    "model": "gpt-5",
    "messages": messages,
    "max_completion_tokens": 2048  # ✅ Correct
    # temperature omitted - will use default value 1
}
```

## Token Limits by Model

### GPT-5 Series
- **Context Window:** 400,000 tokens
- **Max Output:** 128,000 tokens
- **Pricing:** $1.25 input / $10 output (per 1M tokens)
- **Models:** gpt-5, gpt-5-mini, gpt-5-nano

### o-Series Reasoning Models
- **o1:** 200,000 context / 100,000 output
- **o1-mini:** 128,000 context / 65,000 output
- **o3:** 200,000 context / 100,000 output
- **o3-mini:** 200,000 context / 100,000 output
- **o4-mini:** 128,000 context / 100,000 output

### GPT-4o Series
- **Context Window:** 128,000 tokens
- **Max Output:** 16,384 tokens
- **Pricing:** $2.50 input / $10 output (per 1M tokens)
- **Models:** gpt-4o, gpt-4o-mini

### GPT-4 Series
- **Context Window:** Varies (8K-128K depending on variant)
- **Max Output:** 4,096-8,192 tokens
- **Pricing:** $10-$30 input / $30-$60 output (per 1M tokens)

## Required Python Package

```bash
pip install openai>=1.0.0
```

**Important:** Ensure you have openai package version 1.0.0 or higher to support the new API structure and parameter names.

## Error Handling

### Common Errors

**Error 400 - Unsupported Parameter:**
```
Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens'
is not supported with this model. Use 'max_completion_tokens' instead."}}
```

**Solution:** Update code to use `max_completion_tokens` for GPT-5/o-series models.

**Error 429 - Rate Limit / Insufficient Quota:**
```
Error code: 429 - {'error': {'message': 'You exceeded your current quota...'}}
```

**Solution:** Check billing settings at https://platform.openai.com/settings/organization/billing

### Best Practices

1. **Always use the helper function** to determine parameter name
2. **Log the parameter being used** for debugging (we do this at DEBUG level)
3. **Handle both error types** gracefully in production
4. **Test with multiple models** to ensure compatibility

## API Call Structure

### Standard Chat Completion

```python
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

# Build parameters based on model
api_params = {
    "model": "gpt-5",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7
}

# Add token limit with correct parameter name
if uses_max_completion_tokens("gpt-5"):
    api_params["max_completion_tokens"] = 1024
else:
    api_params["max_tokens"] = 1024

response = client.chat.completions.create(**api_params)
```

### Response Structure

```python
# Access response data
message = response.choices[0].message.content
tokens_used = response.usage.total_tokens
prompt_tokens = response.usage.prompt_tokens
completion_tokens = response.usage.completion_tokens

# For reasoning models, some tokens are hidden
# completion_tokens includes both visible and reasoning tokens
```

## Cost Calculation

```python
def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost for OpenAI API call."""

    # Get pricing per 1M tokens
    if model.startswith("gpt-5"):
        input_cost, output_cost = 1.25, 10.00
    elif model.startswith("gpt-4o"):
        input_cost, output_cost = 2.50, 10.00
    elif model.startswith("gpt-4"):
        input_cost, output_cost = 30.00, 60.00
    else:
        input_cost, output_cost = 1.25, 10.00  # Default to GPT-5

    # Calculate total cost
    cost = (prompt_tokens * input_cost / 1_000_000) + \
           (completion_tokens * output_cost / 1_000_000)

    return cost
```

## Migration Guide

### Updating Existing Code

**Before (deprecated):**
```python
response = client.chat.completions.create(
    model="gpt-5",
    max_tokens=1024,  # ❌ Will fail
    messages=[...]
)
```

**After (correct):**
```python
# Determine parameter name
token_param = "max_completion_tokens" if uses_max_completion_tokens(model) else "max_tokens"

# Build parameters dynamically
params = {
    "model": model,
    "messages": messages,
    token_param: 1024
}

response = client.chat.completions.create(**params)
```

### Testing Checklist

- [ ] Test with GPT-5 model
- [ ] Test with GPT-4o model (should still use max_tokens)
- [ ] Test with o1-preview (reasoning model)
- [ ] Verify error handling for unsupported parameters
- [ ] Check token usage logging
- [ ] Validate cost calculations

## References

- **OpenAI API Documentation:** https://platform.openai.com/docs/api-reference
- **Model Comparison:** https://platform.openai.com/docs/models
- **Pricing:** https://openai.com/api/pricing/
- **Migration Guide:** https://platform.openai.com/docs/guides/migration

## Support

- **OpenAI Community Forum:** https://community.openai.com
- **Rate Limits:** https://platform.openai.com/account/rate-limits
- **Billing:** https://platform.openai.com/settings/organization/billing

## OpenAI API Enhancement Features

### Description Rewriting with Fallback

The OpenAI API integration includes robust error handling for description generation:

**Fallback Logic:**
```python
if not enhanced_description or len(enhanced_description.strip()) == 0:
    logging.warning("⚠️  OpenAI returned empty description! Using original body_html")
    enhanced_description = body_html  # Fall back to original
```

**Why this matters:**
- GPT-5 and reasoning models occasionally return empty responses
- Fallback ensures product always has a description
- Original description preserved if AI enhancement fails
- Detailed debug logging tracks response length and content

### Shopify Category Mapping with AI

**NEW in 2025:** The script uses AI to intelligently match products to Shopify's Standard Product Taxonomy!

**How it works:**

1. **Fetch Shopify Taxonomy from GitHub** (once per batch, cached for 30 days):
   - Source: `https://raw.githubusercontent.com/Shopify/product-taxonomy/main/dist/en/categories.txt`
   - Official Shopify taxonomy repository (updated quarterly)
   - Downloads ~6,000+ categories with full hierarchical paths
   - Format: `gid://shopify/TaxonomyCategory/CODE : Category > Path > Name`
   - Example: "Home & Garden > Lawn & Garden > Outdoor Living > Pavers & Stepping Stones"
   - **No Shopify API credentials required** for taxonomy fetch

2. **AI-Based Matching** (per product):
   - Sends product title + enhanced description + complete taxonomy list to OpenAI
   - AI selects the MOST SPECIFIC and RELEVANT category
   - Explicit instructions to avoid generic top-level categories
   - Returns category ID in Shopify GID format

3. **Smart Caching**:
   - **Taxonomy Cache:** `shopify_taxonomy_cache.json` (30-day duration)
   - **Enhancement Cache:** `claude_enhanced_cache.json` (includes matched category ID)
   - Auto-refresh when cache expires
   - Stale fallback if GitHub fetch fails

4. **Storage**:
   - Stored as `shopify_category_id` in enhanced product
   - Used directly when creating products (no string matching needed!)

**Example Flow:**
```
Product: "Aberdeen Slabs - Patio slabs for outdoor hardscaping"

Step 1: Fetch official taxonomy from Shopify GitHub (6,247 categories)
        Cache for 30 days
Step 2: AI enhancement generates narrative description
Step 3: AI analyzes product + description against ALL 6,247 categories
Step 4: AI selects: "Home & Garden > Lawn & Garden > Outdoor Living > Pavers & Stepping Stones"
        (Not generic "Home & Garden")
Step 5: Returns: "gid://shopify/TaxonomyCategory/hg-6-1-8"
Step 6: Product created in Shopify with correct category assigned
```

**Benefits:**
- **Official Source**: Uses Shopify's canonical taxonomy from GitHub
- **Always Current**: Main branch reflects latest updates (currently 2025-09)
- **Complete Data**: 6,000+ categories vs GraphQL pagination limits
- **No API Quotas**: Direct file download, no rate limits
- **Accuracy**: AI understands context and meaning, not just keywords
- **Specificity**: Explicit instructions prevent generic category selection
- **Efficiency**: Cached for 30 days, one fetch per batch
- **Reliability**: Stale cache fallback if GitHub unavailable

## Multi-Strategy Taxonomy Matching (Fallback)

**Note:** This is now a FALLBACK method for products without AI enhancement. AI-enhanced products use the superior AI matching described above.

For non-AI enhanced products, the script uses a multi-strategy string matching approach:

### Search Strategies (in order)

**Strategy 1: Exact Match**
- Case-insensitive exact match of category name
- Example: "Pavers and Hardscaping" → exact match in Shopify taxonomy

**Strategy 2: Contains Match**
- Search term contained in Shopify taxonomy fullName
- Returns shortest match (most specific)
- Example: "Pavers" found in "Pavers & Stepping Stones"

**Strategy 3: Keyword Match**
- Extracts keywords from category string
- Counts keyword matches in taxonomy entries
- Sorts by match count (most matches first) and length (shortest first)
- Example: "Pavers and Hardscaping > Slabs" → ["pavers", "hardscaping", "slabs"]

### Fallback Strategies

If initial search fails, the script tries:

**Fallback 1: Hierarchical Parts**
- If category contains " > ", split into parts
- Try each part from most specific (last) to least specific (first)
- Example: "Pavers and Hardscaping > Slabs" → tries "Slabs", then "Pavers and Hardscaping"

**Fallback 2: Last Word**
- Try just the last word (often the product type)
- Example: "Outdoor Patio Slabs" → tries "Slabs"

### Caching

All taxonomy lookups are cached in `product_taxonomy.json`:

**Cache Format:**
```json
{
  "Pavers and Hardscaping > Slabs": "gid://shopify/TaxonomyCategory/sg-4-17-3-1",
  "Slabs": "gid://shopify/TaxonomyCategory/sg-4-17-3-1"
}
```

**Benefits:**
- Reduces API calls (Shopify taxonomy query is expensive)
- Consistent results across runs
- Negative results cached (avoids repeated failed lookups)

### Implementation Example

```python
# Get taxonomy ID with multi-strategy search
taxonomy_id, taxonomy_cache = get_taxonomy_id(
    "Pavers and Hardscaping > Slabs",  # Category from AI enhancement
    taxonomy_cache,
    api_url,
    headers,
    status_fn
)

if taxonomy_id:
    product_input["category"] = taxonomy_id
```

---

**Note:** OpenAI API specifications change frequently. Always refer to the official documentation for the most current information.
