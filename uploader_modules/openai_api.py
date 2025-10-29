"""
OpenAI API integration for product taxonomy assignment and description rewriting.
"""

import json
import logging
from typing import Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logging.warning("openai package not installed. OpenAI features will be disabled.")

from .config import log_and_status


def is_reasoning_model(model: str) -> bool:
    """
    Determine if a model is a reasoning model (GPT-5, o-series).

    Reasoning models have restricted parameter support:
    - Use 'max_completion_tokens' instead of 'max_tokens'
    - Don't support custom temperature (only default value 1)
    - Don't support: top_p, presence_penalty, frequency_penalty, logprobs, logit_bias

    Args:
        model: Model identifier (e.g., "gpt-5", "gpt-4o", "o1-preview")

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

    # All other models (GPT-4o, GPT-4, GPT-3.5, etc.) are NOT reasoning models
    return False


def uses_max_completion_tokens(model: str) -> bool:
    """
    Determine if a model uses 'max_completion_tokens' instead of 'max_tokens'.

    This is a convenience wrapper around is_reasoning_model().

    Args:
        model: Model identifier

    Returns:
        True if model uses max_completion_tokens, False if it uses max_tokens
    """
    return is_reasoning_model(model)


def get_openai_model_pricing(model: str) -> tuple:
    """
    Get pricing for OpenAI models (input cost per 1M tokens, output cost per 1M tokens).

    Returns:
        Tuple of (input_cost, output_cost) per million tokens
    """
    # GPT-5 models (released August 2025)
    if model.startswith("gpt-5"):
        return (1.25, 10.00)  # GPT-5, GPT-5-mini, GPT-5-nano all same pricing

    # GPT-4o models
    elif model.startswith("gpt-4o"):
        return (2.50, 10.00)

    # GPT-4 Turbo
    elif "gpt-4-turbo" in model or "gpt-4-1106" in model or "gpt-4-0125" in model:
        return (10.00, 30.00)

    # GPT-4
    elif model.startswith("gpt-4"):
        return (30.00, 60.00)

    # Default to GPT-5 pricing (most common)
    else:
        return (1.25, 10.00)


def match_shopify_category_with_openai(
    product_title: str,
    product_description: str,
    shopify_categories: List[Dict],
    api_key: str,
    model: str,
    status_fn=None
) -> str:
    """
    Use OpenAI to match a product to the best Shopify taxonomy category.

    Args:
        product_title: Product title
        product_description: Product description
        shopify_categories: List of dicts with 'id' and 'fullName' from Shopify
        api_key: OpenAI API key
        model: OpenAI model ID
        status_fn: Optional status update function

    Returns:
        Shopify category ID (GID format) or None if no good match

    Raises:
        Exception: If API call fails
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot match Shopify categories."
        logging.error(error_msg)
        raise ImportError(error_msg)

    try:
        client = OpenAI(api_key=api_key)

        if status_fn:
            log_and_status(status_fn, f"  🔍 Matching to Shopify category...")

        logging.info("=" * 80)
        logging.info(f"OPENAI API CALL: SHOPIFY CATEGORY MATCHING")
        logging.info(f"Product: {product_title}")
        logging.info(f"Available categories: {len(shopify_categories)}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        # Build category list for prompt - include ALL categories in compact format
        # Group by top-level category to make it easier for AI to navigate
        categories_by_top = {}
        for cat in shopify_categories:
            full_name = cat['fullName']
            top_level = full_name.split(' > ')[0] if ' > ' in full_name else full_name
            if top_level not in categories_by_top:
                categories_by_top[top_level] = []
            categories_by_top[top_level].append(full_name)

        # Build compact category text
        categories_text = ""
        for top_level in sorted(categories_by_top.keys()):
            categories_text += f"\n{top_level}:\n"
            for cat_name in categories_by_top[top_level][:200]:  # Limit per top-level to manage size
                categories_text += f"  - {cat_name}\n"
            if len(categories_by_top[top_level]) > 200:
                categories_text += f"  ... and {len(categories_by_top[top_level]) - 200} more\n"

        prompt = f"""You are a product categorization expert. Match this product to the BEST category from Shopify's Standard Product Taxonomy.

Product Information:
- Title: {product_title}
- Description: {product_description[:1000]}

Available Shopify Categories (hierarchical paths):
{categories_text}

CRITICAL INSTRUCTIONS:
1. Analyze the product title and description carefully
2. Find the MOST SPECIFIC category - NOT a top-level category!
   - ❌ WRONG: "Home & Garden" (too generic)
   - ✅ CORRECT: "Home & Garden > Lawn & Garden > Outdoor Living > Pavers & Stepping Stones" (specific)
3. Choose the DEEPEST, most detailed category path that accurately describes this product
4. For patio/outdoor hardscape products, look for categories containing "Pavers", "Stepping Stones", "Outdoor Living", "Hardscape", "Landscaping"
5. Return the COMPLETE hierarchical path (e.g., "Parent > Child > Grandchild")

Return ONLY a valid JSON object in this exact format (no markdown, no code blocks, no explanation):
{{
  "category_fullName": "Complete hierarchical category path from the list above (must include all levels separated by ' > ')",
  "reasoning": "Brief 1-sentence explanation of why you chose this specific category"
}}

EXAMPLE GOOD RESPONSES:
- {{"category_fullName": "Home & Garden > Lawn & Garden > Outdoor Living > Pavers & Stepping Stones", "reasoning": "Product is patio slabs for outdoor hardscaping"}}
- {{"category_fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Beds", "reasoning": "Product is a bed specifically for dogs"}}

EXAMPLE BAD RESPONSES (too generic):
- {{"category_fullName": "Home & Garden", "reasoning": "..."}} ❌ TOO GENERIC
- {{"category_fullName": "Animals & Pet Supplies", "reasoning": "..."}} ❌ TOO GENERIC

If no good match exists, return: {{"category_fullName": null, "reasoning": "No suitable category found"}}"""

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt
            }]
        }

        # Add temperature only for non-reasoning models
        if not is_reasoning_model(model):
            api_params["temperature"] = 0.3
            logging.debug(f"Using temperature=0.3 for model {model}")
        else:
            logging.debug(f"Omitting temperature for reasoning model {model} (only default value 1 supported)")

        # Use correct token limit parameter
        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 512
            logging.debug(f"Using max_completion_tokens=512 for model {model}")
        else:
            api_params["max_tokens"] = 512
            logging.debug(f"Using max_tokens=512 for model {model}")

        response = client.chat.completions.create(**api_params)

        # Log response details
        logging.info(f"✅ Shopify category matching API call successful")
        logging.info(f"Response ID: {response.id}")
        logging.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}")

        # Extract response
        response_text = response.choices[0].message.content.strip()
        logging.debug(f"Raw response: {response_text}")

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse Shopify category JSON: {e}")
            logging.error(f"Response: {response_text}")
            return None

        category_fullName = result.get('category_fullName')
        reasoning = result.get('reasoning', '')

        if not category_fullName:
            logging.warning(f"⚠️  AI could not find suitable Shopify category: {reasoning}")
            if status_fn:
                log_and_status(status_fn, f"    ⚠️  No suitable Shopify category found")
            return None

        # Find the category ID by matching fullName
        category_id = None
        for cat in shopify_categories:
            if cat['fullName'] == category_fullName:
                category_id = cat['id']
                break

        if category_id:
            logging.info(f"✅ Matched Shopify category: {category_fullName}")
            logging.info(f"📝 Reasoning: {reasoning}")
            logging.info(f"🆔 Category ID: {category_id}")
            if status_fn:
                log_and_status(status_fn, f"    ✅ Matched: {category_fullName}")
        else:
            logging.warning(f"⚠️  AI selected category not found in list: {category_fullName}")
            if status_fn:
                log_and_status(status_fn, f"    ⚠️  Category not found: {category_fullName}")

        return category_id

    except Exception as e:
        logging.error(f"Error matching Shopify category: {e}")
        logging.exception("Full traceback:")
        return None


def enhance_product_with_openai(
    product: Dict,
    taxonomy_doc: str,
    voice_tone_doc: str,
    shopify_categories: List[Dict],
    api_key: str,
    model: str,
    status_fn=None,
    audience_config: Dict = None
) -> Dict:
    """
    Enhance a single product using OpenAI API.

    Args:
        product: Product dictionary
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: OpenAI API key
        model: OpenAI model ID (e.g., "gpt-4o")
        status_fn: Optional status update function
        audience_config: Optional audience configuration dict with keys:
            - count: 1 or 2
            - audience_1_name: str
            - audience_2_name: str (if count=2)
            - tab_1_label: str (if count=2)
            - tab_2_label: str (if count=2)

    Returns:
        Enhanced product dictionary (includes metafields for multiple audiences)

    Raises:
        Exception: If API call fails or response is invalid
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot enhance products. Install with: pip install openai"
        logging.error(error_msg)
        raise ImportError(error_msg)

    title = product.get('title', '')
    body_html = product.get('body_html', '')

    if not title:
        error_msg = f"Product has no title, cannot enhance: {product}"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = OpenAI(api_key=api_key)

        # ========== STEP 1: TAXONOMY ASSIGNMENT ==========
        if status_fn:
            log_and_status(status_fn, f"  🤖 Assigning taxonomy for: {title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"OPENAI API CALL #1: TAXONOMY ASSIGNMENT")
        logging.info(f"Product: {title}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        taxonomy_prompt = _build_taxonomy_prompt(title, body_html, taxonomy_doc)

        # Log prompt preview (first 500 chars)
        logging.debug(f"Taxonomy prompt (first 500 chars):\n{taxonomy_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(taxonomy_prompt)} characters")

        # Make API call with correct parameters based on model
        logging.info("Sending taxonomy assignment request to OpenAI API...")

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": taxonomy_prompt
            }]
        }

        # Add temperature only for non-reasoning models
        # Reasoning models (GPT-5, o-series) only support temperature=1 (default)
        if not is_reasoning_model(model):
            api_params["temperature"] = 0.3
            logging.debug(f"Using temperature=0.3 for model {model}")
        else:
            logging.debug(f"Omitting temperature for reasoning model {model} (only default value 1 supported)")

        # Use correct token limit parameter based on model
        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 1024
            logging.debug(f"Using max_completion_tokens=1024 for model {model}")
        else:
            api_params["max_tokens"] = 1024
            logging.debug(f"Using max_tokens=1024 for model {model}")

        taxonomy_response = client.chat.completions.create(**api_params)

        # Log response details
        logging.info(f"✅ Taxonomy API call successful")
        logging.info(f"Response ID: {taxonomy_response.id}")
        logging.info(f"Model used: {taxonomy_response.model}")
        logging.info(f"Finish reason: {taxonomy_response.choices[0].finish_reason}")
        logging.info(f"Token usage - Prompt: {taxonomy_response.usage.prompt_tokens}, Completion: {taxonomy_response.usage.completion_tokens}, Total: {taxonomy_response.usage.total_tokens}")

        # Calculate cost based on model pricing
        input_cost, output_cost = get_openai_model_pricing(model)
        taxonomy_cost = (taxonomy_response.usage.prompt_tokens * input_cost / 1_000_000) + (taxonomy_response.usage.completion_tokens * output_cost / 1_000_000)
        logging.info(f"Cost: ${taxonomy_cost:.6f} (Model: {model}, Pricing: ${input_cost}/${output_cost} per 1M tokens)")

        # Extract taxonomy from response
        taxonomy_text = taxonomy_response.choices[0].message.content.strip()
        logging.debug(f"Raw taxonomy response:\n{taxonomy_text}")

        # Remove markdown code blocks if present
        if taxonomy_text.startswith("```"):
            logging.debug("Removing markdown code block wrapper from taxonomy response")
            lines = taxonomy_text.split('\n')
            # Remove first line (```json or ```) and last line (```)
            taxonomy_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        # Parse JSON response
        try:
            taxonomy_result = json.loads(taxonomy_text)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse taxonomy JSON response: {e}"
            logging.error(error_msg)
            logging.error(f"Raw response text: {taxonomy_text}")
            raise ValueError(f"{error_msg}\nResponse: {taxonomy_text[:200]}...")

        # Validate required fields
        department = taxonomy_result.get('department', '')
        category = taxonomy_result.get('category', '')
        subcategory = taxonomy_result.get('subcategory', '')
        reasoning = taxonomy_result.get('reasoning', '')

        if not department or not category:
            error_msg = f"Taxonomy response missing required fields. Department: '{department}', Category: '{category}'"
            logging.error(error_msg)
            logging.error(f"Full taxonomy result: {taxonomy_result}")
            raise ValueError(error_msg)

        logging.info(f"✅ Taxonomy assigned: {department} > {category} > {subcategory}")
        logging.info(f"📝 Reasoning: {reasoning}")

        if status_fn:
            log_and_status(status_fn, f"    ✅ Department: {department}")
            log_and_status(status_fn, f"    ✅ Category: {category}")
            if subcategory:
                log_and_status(status_fn, f"    ✅ Subcategory: {subcategory}")
            log_and_status(status_fn, f"    📝 Reasoning: {reasoning}")

        # ========== STEP 2: DESCRIPTION REWRITING ==========
        # Determine number of audiences from config
        audience_count = 1
        audience_1_name = None
        audience_2_name = None
        if audience_config:
            audience_count = audience_config.get("count", 1)
            audience_1_name = audience_config.get("audience_1_name", "").strip()
            audience_2_name = audience_config.get("audience_2_name", "").strip()

        # Generate description(s) based on audience count
        enhanced_description = None  # Primary description (goes in body_html)
        description_audience_1 = None  # Audience 1 metafield
        description_audience_2 = None  # Audience 2 metafield
        total_description_cost = 0

        # Only generate multiple descriptions if both audience names are provided
        if audience_count == 2 and audience_1_name and audience_2_name:
            # Generate TWO descriptions for different audiences

            # Description for Audience 1
            if status_fn:
                log_and_status(status_fn, f"  ✍️  Generating description for {audience_1_name}...")

            logging.info("=" * 80)
            logging.info(f"OPENAI API CALL #2A: DESCRIPTION FOR AUDIENCE 1 ({audience_1_name})")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt_1 = _build_description_prompt(title, body_html, department, voice_tone_doc, audience_1_name)

            logging.debug(f"Description prompt for Audience 1 (first 500 chars):\n{description_prompt_1[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt_1)} characters")
            logging.info(f"Sending description rewriting request for {audience_1_name}...")

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt_1}]
            }
            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7
            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_response_1 = client.chat.completions.create(**api_params)

            logging.info(f"✅ Audience 1 description API call successful")
            logging.info(f"Token usage - Prompt: {description_response_1.usage.prompt_tokens}, Completion: {description_response_1.usage.completion_tokens}, Total: {description_response_1.usage.total_tokens}")

            input_cost, output_cost = get_openai_model_pricing(model)
            description_1_cost = (description_response_1.usage.prompt_tokens * input_cost / 1_000_000) + (description_response_1.usage.completion_tokens * output_cost / 1_000_000)
            logging.info(f"Cost: ${description_1_cost:.6f}")
            total_description_cost += description_1_cost

            description_audience_1 = description_response_1.choices[0].message.content.strip()
            if description_audience_1.startswith("```"):
                lines = description_audience_1.split('\n')
                description_audience_1 = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

            if not description_audience_1 or len(description_audience_1.strip()) == 0:
                logging.warning(f"⚠️  OpenAI returned empty description for {audience_1_name}! Using original body_html")
                description_audience_1 = body_html

            logging.info(f"✅ Description for {audience_1_name} complete ({len(description_audience_1)} characters)")

            # Description for Audience 2
            if status_fn:
                log_and_status(status_fn, f"  ✍️  Generating description for {audience_2_name}...")

            logging.info("=" * 80)
            logging.info(f"OPENAI API CALL #2B: DESCRIPTION FOR AUDIENCE 2 ({audience_2_name})")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt_2 = _build_description_prompt(title, body_html, department, voice_tone_doc, audience_2_name)

            logging.debug(f"Description prompt for Audience 2 (first 500 chars):\n{description_prompt_2[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt_2)} characters")
            logging.info(f"Sending description rewriting request for {audience_2_name}...")

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt_2}]
            }
            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7
            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_response_2 = client.chat.completions.create(**api_params)

            logging.info(f"✅ Audience 2 description API call successful")
            logging.info(f"Token usage - Prompt: {description_response_2.usage.prompt_tokens}, Completion: {description_response_2.usage.completion_tokens}, Total: {description_response_2.usage.total_tokens}")

            description_2_cost = (description_response_2.usage.prompt_tokens * input_cost / 1_000_000) + (description_response_2.usage.completion_tokens * output_cost / 1_000_000)
            logging.info(f"Cost: ${description_2_cost:.6f}")
            total_description_cost += description_2_cost

            description_audience_2 = description_response_2.choices[0].message.content.strip()
            if description_audience_2.startswith("```"):
                lines = description_audience_2.split('\n')
                description_audience_2 = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

            if not description_audience_2 or len(description_audience_2.strip()) == 0:
                logging.warning(f"⚠️  OpenAI returned empty description for {audience_2_name}! Using original body_html")
                description_audience_2 = body_html

            logging.info(f"✅ Description for {audience_2_name} complete ({len(description_audience_2)} characters)")

            # Use Audience 1 description as primary body_html
            enhanced_description = description_audience_1

            if status_fn:
                log_and_status(status_fn, f"    ✅ Generated 2 audience descriptions ({len(description_audience_1)} + {len(description_audience_2)} chars)")

        else:
            # Single audience mode (default behavior)
            if status_fn:
                audience_label = f" for {audience_1_name}" if audience_1_name else ""
                log_and_status(status_fn, f"  ✍️  Rewriting description{audience_label}...")

            logging.info("=" * 80)
            logging.info(f"OPENAI API CALL #2: DESCRIPTION REWRITING")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            if audience_1_name:
                logging.info(f"Audience: {audience_1_name}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt = _build_description_prompt(title, body_html, department, voice_tone_doc, audience_1_name if audience_1_name else None)

            logging.debug(f"Description prompt (first 500 chars):\n{description_prompt[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt)} characters")
            logging.info("Sending description rewriting request to OpenAI API...")

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt}]
            }
            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7
            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_response = client.chat.completions.create(**api_params)

            logging.info(f"✅ Description API call successful")
            logging.info(f"Response ID: {description_response.id}")
            logging.info(f"Model used: {description_response.model}")
            logging.info(f"Finish reason: {description_response.choices[0].finish_reason}")
            logging.info(f"Token usage - Prompt: {description_response.usage.prompt_tokens}, Completion: {description_response.usage.completion_tokens}, Total: {description_response.usage.total_tokens}")

            input_cost, output_cost = get_openai_model_pricing(model)
            total_description_cost = (description_response.usage.prompt_tokens * input_cost / 1_000_000) + (description_response.usage.completion_tokens * output_cost / 1_000_000)
            logging.info(f"Cost: ${total_description_cost:.6f} (Model: {model}, Pricing: ${input_cost}/${output_cost} per 1M tokens)")

            enhanced_description = description_response.choices[0].message.content.strip()

            logging.debug(f"Raw description response length: {len(enhanced_description)} characters")
            logging.debug(f"Raw description response (first 1000 chars):\n{enhanced_description[:1000]}...")

            if enhanced_description.startswith("```"):
                logging.debug("Removing markdown code block wrapper from description response")
                lines = enhanced_description.split('\n')
                enhanced_description = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
                logging.debug(f"After removing wrapper: {len(enhanced_description)} characters")

            if not enhanced_description or len(enhanced_description.strip()) == 0:
                logging.warning("⚠️  OpenAI returned empty description! Using original body_html")
                logging.warning(f"Original body_html length: {len(body_html)} characters")
                enhanced_description = body_html

            logging.info(f"✅ Description rewritten ({len(enhanced_description)} characters)")

            if status_fn:
                log_and_status(status_fn, f"    ✅ Description rewritten ({len(enhanced_description)} characters)")

        # Calculate total cost
        total_cost = taxonomy_cost + total_description_cost
        logging.info(f"Total cost for this product: ${total_cost:.6f}")

        # Create enhanced product with new taxonomy and description
        enhanced_product = product.copy()
        enhanced_product['product_type'] = department

        # Build tags array: category + subcategory (if exists)
        tags = [category]
        if subcategory:
            tags.append(subcategory)

        # Preserve any existing tags that aren't taxonomy-related
        existing_tags = product.get('tags', [])
        if isinstance(existing_tags, str):
            existing_tags = [t.strip() for t in existing_tags.split(',') if t.strip()]

        # Add existing tags that aren't department/category names
        for tag in existing_tags:
            if tag and tag not in tags and tag != department:
                tags.append(tag)

        enhanced_product['tags'] = tags
        enhanced_product['body_html'] = enhanced_description

        # Add audience descriptions as metafields if multiple audiences
        if audience_count == 2 and description_audience_1 and description_audience_2:
            # Initialize metafields array if it doesn't exist
            if 'metafields' not in enhanced_product:
                enhanced_product['metafields'] = []

            # Add audience configuration metafield (for Liquid template)
            audience_metadata = {
                "count": 2,
                "audience_1_name": audience_1_name,
                "audience_2_name": audience_2_name,
                "tab_1_label": audience_config.get("tab_1_label", audience_1_name),
                "tab_2_label": audience_config.get("tab_2_label", audience_2_name)
            }

            enhanced_product['metafields'].append({
                "namespace": "custom",
                "key": "audience_config",
                "value": json.dumps(audience_metadata),
                "type": "json"
            })

            # Add audience 1 description metafield
            enhanced_product['metafields'].append({
                "namespace": "custom",
                "key": "description_audience_1",
                "value": description_audience_1,
                "type": "multi_line_text_field"
            })

            # Add audience 2 description metafield
            enhanced_product['metafields'].append({
                "namespace": "custom",
                "key": "description_audience_2",
                "value": description_audience_2,
                "type": "multi_line_text_field"
            })

            logging.info(f"Added audience metafields to product:")
            logging.info(f"  - audience_config: {audience_metadata}")
            logging.info(f"  - description_audience_1: {len(description_audience_1)} chars")
            logging.info(f"  - description_audience_2: {len(description_audience_2)} chars")

        # ========== STEP 3: SHOPIFY CATEGORY MATCHING ==========
        # Use AI to match product to Shopify's standard taxonomy
        shopify_category_id = None
        if shopify_categories and len(shopify_categories) > 0:
            try:
                shopify_category_id = match_shopify_category_with_openai(
                    title,
                    enhanced_description,
                    shopify_categories,
                    api_key,
                    model,
                    status_fn
                )
            except Exception as e:
                logging.warning(f"Failed to match Shopify category: {e}")
                shopify_category_id = None

        # Store Shopify category ID in product
        if shopify_category_id:
            enhanced_product['shopify_category_id'] = shopify_category_id
            logging.info(f"Stored Shopify category ID: {shopify_category_id}")
        else:
            enhanced_product['shopify_category_id'] = None
            logging.warning("No Shopify category ID assigned")

        logging.info("=" * 80)
        logging.info(f"✅ PRODUCT ENHANCEMENT COMPLETE: {title}")
        logging.info(f"Custom taxonomy: {department} > {category} > {subcategory}")
        logging.info(f"Shopify category ID: {enhanced_product.get('shopify_category_id', 'None')}")
        logging.info(f"Description length: {len(enhanced_description)} characters")
        logging.info("=" * 80)

        return enhanced_product

    except Exception as e:
        # Log detailed error information
        error_msg = f"Error enhancing product '{title}' with OpenAI API"
        logging.error("=" * 80)
        logging.error(f"❌ {error_msg}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Error Details: {str(e)}")

        # Check if it's an OpenAI API error
        if OpenAI and hasattr(e, 'status_code'):
            logging.error(f"HTTP Status Code: {e.status_code}")
        if hasattr(e, 'response'):
            logging.error(f"API Response: {e.response}")

        # Log full stack trace
        logging.exception("Full traceback:")
        logging.error("=" * 80)

        # Re-raise with clear message
        raise Exception(f"{error_msg}: {str(e)}") from e


def generate_collection_description(
    collection_title: str,
    department: str,
    product_samples: List[str],
    voice_tone_doc: str,
    api_key: str,
    model: str,
    status_fn=None
) -> str:
    """
    Generate a collection description using OpenAI API.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions from this collection
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: OpenAI API key
        model: OpenAI model ID
        status_fn: Optional status update function

    Returns:
        Generated collection description (plain text)

    Raises:
        Exception: If API call fails
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot generate collection descriptions."
        logging.error(error_msg)
        raise ImportError(error_msg)

    if not collection_title:
        error_msg = f"Collection has no title, cannot generate description"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = OpenAI(api_key=api_key)

        if status_fn:
            log_and_status(status_fn, f"  📝 Generating description for: {collection_title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"OPENAI API CALL: COLLECTION DESCRIPTION")
        logging.info(f"Collection: {collection_title}")
        logging.info(f"Department: {department}")
        logging.info(f"Product samples: {len(product_samples)}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        collection_prompt = _build_collection_description_prompt(
            collection_title,
            department,
            product_samples,
            voice_tone_doc
        )

        # Log prompt preview
        logging.debug(f"Collection prompt (first 500 chars):\n{collection_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(collection_prompt)} characters")

        # Make API call with correct parameters based on model
        logging.info("Sending collection description request to OpenAI API...")

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": collection_prompt
            }]
        }

        # Add temperature only for non-reasoning models
        # Reasoning models (GPT-5, o-series) only support temperature=1 (default)
        if not is_reasoning_model(model):
            api_params["temperature"] = 0.7
            logging.debug(f"Using temperature=0.7 for model {model}")
        else:
            logging.debug(f"Omitting temperature for reasoning model {model} (only default value 1 supported)")

        # Use correct token limit parameter based on model
        # 100 words ~ 150 tokens, give buffer
        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 512
            logging.debug(f"Using max_completion_tokens=512 for model {model}")
        else:
            api_params["max_tokens"] = 512
            logging.debug(f"Using max_tokens=512 for model {model}")

        response = client.chat.completions.create(**api_params)

        # Log response details
        logging.info(f"✅ Collection description API call successful")
        logging.info(f"Response ID: {response.id}")
        logging.info(f"Model used: {response.model}")
        logging.info(f"Finish reason: {response.choices[0].finish_reason}")
        logging.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}, Total: {response.usage.total_tokens}")

        input_cost, output_cost = get_openai_model_pricing(model)
        cost = (response.usage.prompt_tokens * input_cost / 1_000_000) + (response.usage.completion_tokens * output_cost / 1_000_000)
        logging.info(f"Cost: ${cost:.6f} (Model: {model}, Pricing: ${input_cost}/${output_cost} per 1M tokens)")

        # Extract description
        description = response.choices[0].message.content.strip()
        logging.debug(f"Generated description ({len(description.split())} words):\n{description}")

        # Remove markdown code blocks if present
        if description.startswith("```"):
            logging.debug("Removing markdown code block wrapper from description")
            lines = description.split('\n')
            description = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        word_count = len(description.split())
        logging.info(f"✅ Collection description generated ({word_count} words)")

        if status_fn:
            log_and_status(status_fn, f"    ✅ Description generated ({word_count} words)")

        logging.info("=" * 80)
        logging.info(f"✅ COLLECTION DESCRIPTION COMPLETE: {collection_title}")
        logging.info("=" * 80)

        return description

    except Exception as e:
        # Log detailed error information
        error_msg = f"Error generating description for collection '{collection_title}'"
        logging.error("=" * 80)
        logging.error(f"❌ {error_msg}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Error Details: {str(e)}")

        # Check if it's an OpenAI API error
        if OpenAI and hasattr(e, 'status_code'):
            logging.error(f"HTTP Status Code: {e.status_code}")
        if hasattr(e, 'response'):
            logging.error(f"API Response: {e.response}")

        # Log full stack trace
        logging.exception("Full traceback:")
        logging.error("=" * 80)

        # Re-raise with clear message
        raise Exception(f"{error_msg}: {str(e)}") from e


# ========== PROMPT BUILDERS (MATCHING CLAUDE API PROMPTS) ==========

def _build_taxonomy_prompt(title: str, body_html: str, taxonomy_doc: str) -> str:
    """Build the prompt for taxonomy assignment (matches claude_api.py)."""
    prompt = f"""You are a product categorization expert. Given the product information below, assign it to the appropriate category in our taxonomy.

{taxonomy_doc}

Product to categorize:
- Title: {title}
- Description: {body_html}

Analyze the product title and description carefully, then assign it to the most appropriate Department, Category, and Subcategory from the taxonomy above.

Return ONLY a valid JSON object in this exact format (no markdown, no code blocks, no explanation):
{{
  "department": "Exact department name from taxonomy",
  "category": "Exact category name from taxonomy",
  "subcategory": "Exact subcategory name from taxonomy (or empty string if category has no subcategories)",
  "reasoning": "Brief 1-sentence explanation of why you chose this categorization"
}}"""

    return prompt


def _build_description_prompt(title: str, body_html: str, department: str, voice_tone_doc: str, audience_name: str = None) -> str:
    """Build the prompt for description rewriting - mobile-optimized for maximum conversion."""
    audience_context = f"\nTarget Audience: {audience_name}" if audience_name else ""

    prompt = f"""You are a professional e-commerce copywriter specializing in mobile-optimized product descriptions that drive conversions.

{voice_tone_doc}

Product information:
- Title: {title}
- Department: {department}
- Current Description: {body_html}{audience_context}

CRITICAL: Write for MOBILE-FIRST experience. Most customers will read this on phones where text appears longer and attention spans are shorter.
{f"AUDIENCE: Tailor this description specifically for {audience_name}. Use language, benefits, and examples that resonate with this audience." if audience_name else ""}

STRUCTURE & LENGTH:
- Target: 150-350 words (adjust based on product complexity)
- Simple products: 150-250 words
- Moderately complex: 250-350 words
- Complex/technical: 300-400 words maximum

OPENING SECTION (First 50-100 words - MOST CRITICAL):
- Lead with PRIMARY BENEFIT and key product attributes
- Include primary keyword in opening sentence
- Focus on how product solves customer problems
- This section appears above fold on mobile - make it count!
- Answer: "Why should I care about this product?"

CONTENT PRIORITY (in order):
1. Benefits first, then features
2. Combine features WITH their benefits (never list features alone)
3. Key specifications (dimensions, material, finish, color)
4. Address common customer questions/concerns
5. Installation, usage, or maintenance guidance (if relevant)

MOBILE FORMATTING RULES:
- Short sentences (10-15 words ideal) - mobile screens make text appear longer
- Short paragraphs (3-4 sentences maximum)
- Break content into scannable chunks with clear subheadings (use <h3> tags)
- Use <strong> tags to bold key features and specs for quick scanning
- Use bullet points for technical specs (<ul><li>...</li></ul>)
- Keep bullets concise (~20 words max per bullet)
- Ensure adequate white space between sections

HTML STRUCTURE EXAMPLE:
<p>[Hook opening with primary benefit + primary keyword. 2-3 sentences max.]</p>

<h3>Key Features</h3>
<ul>
  <li><strong>Feature:</strong> Brief benefit explanation</li>
  <li><strong>Feature:</strong> Brief benefit explanation</li>
  <li><strong>Feature:</strong> Brief benefit explanation</li>
</ul>

<h3>Applications</h3>
<p>[2-3 sentences about use cases and where/how product is used]</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> [material]</li>
  <li><strong>Dimensions:</strong> [sizes]</li>
  <li><strong>Finish:</strong> [texture/surface]</li>
  <li><strong>Colors:</strong> [available colors]</li>
</ul>

<p>[Optional closing: maintenance, installation tip, or warranty info. 1-2 sentences.]</p>

VOICE & TONE:
- Conversational and informative (not salesy or pushy)
- Honest and specific (avoid exaggerated claims like "revolutionary" or "world-class")
- Second-person voice ("you", "your")
- Professional but accessible
- Avoid clichés and marketing jargon

SEO REQUIREMENTS:
- Include primary keyword in first 100 words
- Naturally incorporate related keywords throughout
- Minimum 150 words for SEO value
- Write for humans first, search engines second
- Use specific, descriptive terms customers search for

FOR HARDSCAPING/CONSTRUCTION PRODUCTS (pavers, slabs, stones):
Always include:
- Material composition (wet cast, concrete, natural stone, etc.)
- Finish/texture description
- Recommended applications (patios, walkways, driveways, pool decks)
- Dimensions/sizes available
- Installation considerations (if relevant)
- Durability features (stain resistance, weather resistance)
- Maintenance requirements
- Color options

CRITICAL RULES:
- Put most important information in first 75-100 words
- No lengthy paragraphs - break them up
- Make content scannable without excessive scrolling
- Every sentence must add value - cut all fluff
- Combine features with benefits - never list features without context
- Use subheadings to help mobile users scan quickly

Return ONLY the HTML description. No explanations, notes, or markdown code blocks. Just clean, mobile-optimized HTML that will go directly into body_html."""

    return prompt


def _build_collection_description_prompt(collection_title: str, department: str, product_samples: List[str], voice_tone_doc: str) -> str:
    """Build the prompt for collection description (matches claude_api.py)."""
    # Limit to 5 product samples to keep prompt size reasonable
    samples_text = "\n\n".join([f"Product {i+1}:\n{sample[:500]}..." for i, sample in enumerate(product_samples[:5])])

    prompt = f"""You are a professional collection copywriter. Write a compelling 100-word description for this product collection.

{voice_tone_doc}

Collection information:
- Collection Name: {collection_title}
- Department: {department}
- Sample products in this collection:

{samples_text}

Your task:
1. Analyze the product samples to understand what this collection offers
2. Apply the tone guidelines for the "{department}" department
3. Write a 100-word collection description following these requirements:
   - Use second-person voice (addressing the customer directly)
   - Prefer imperative-first phrasing when appropriate
   - Avoid generic phrases like "premium", "must-have", "high-quality"
   - Focus on what the collection offers and who it's for
   - Ensure proper punctuation (no encoded characters like \\u2019)
   - Make it compelling and natural

4. SEO Optimization requirements:
   - Include the collection name naturally in the first sentence
   - Use specific, descriptive terms that customers would search for
   - Mention key product types and use cases in this collection
   - Focus on search intent (why would someone browse this collection?)
   - Avoid keyword stuffing - maintain natural, readable language
   - Include semantic variations (e.g., "patio slabs" and "outdoor pavers")

5. Length constraint:
   - Must be approximately 100 words (90-110 words is acceptable)
   - Be concise and impactful

Return ONLY the collection description in plain text format. Do not include any explanations, notes, HTML tags, or markdown formatting. Just the plain text description."""

    return prompt
