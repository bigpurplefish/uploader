"""
Claude API integration for product taxonomy assignment and description rewriting.
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional

try:
    import anthropic
except ImportError:
    anthropic = None
    logging.warning("anthropic package not installed. Claude AI features will be disabled.")

from .config import log_and_status


# Cache file location
CACHE_FILE = "claude_enhanced_cache.json"


def load_cache() -> Dict:
    """Load the Claude enhancement cache from disk."""
    if not os.path.exists(CACHE_FILE):
        return {"cache_version": "1.0", "products": {}}

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to load Claude cache: {e}")
        return {"cache_version": "1.0", "products": {}}


def save_cache(cache: Dict):
    """Save the Claude enhancement cache to disk."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to save Claude cache: {e}")


def compute_product_hash(product: Dict) -> str:
    """Compute a hash of the product's title and body_html to detect changes."""
    title = product.get('title', '')
    body_html = product.get('body_html', '')
    content = f"{title}||{body_html}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def load_markdown_file(file_path: str) -> str:
    """Load a markdown file and return its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"Markdown file not found: {file_path}")
        return ""
    except Exception as e:
        logging.error(f"Error loading markdown file {file_path}: {e}")
        return ""


def build_taxonomy_prompt(title: str, body_html: str, taxonomy_doc: str) -> str:
    """
    Build the prompt for Claude to assign product taxonomy.

    Args:
        title: Product title
        body_html: Product description (HTML)
        taxonomy_doc: Full taxonomy markdown document

    Returns:
        Formatted prompt string
    """
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


def build_description_prompt(title: str, body_html: str, department: str, voice_tone_doc: str) -> str:
    """
    Build the prompt for Claude to rewrite product description.

    Args:
        title: Product title
        body_html: Current product description (HTML)
        department: Assigned department (for tone selection)
        voice_tone_doc: Full voice and tone guidelines document

    Returns:
        Formatted prompt string
    """
    prompt = f"""You are a professional product copywriter. Rewrite this product description following our voice and tone guidelines.

{voice_tone_doc}

Product information:
- Title: {title}
- Department: {department}
- Current Description: {body_html}

Your task:
1. Read the current description to understand the product's features and benefits
2. Apply the tone guidelines for the "{department}" department
3. Rewrite the description following ALL the core requirements:
   - Use second-person voice (addressing the customer directly)
   - Prefer imperative-first phrasing (e.g., "Support...", "Keep...", "Help...")
   - Avoid generic phrases like "premium", "must-have", "high-quality"
   - Focus on benefits and use cases, not just features
   - Ensure proper punctuation (no encoded characters like \\u2019)
   - Make it unique and natural (vary your phrasing)

4. SEO Optimization requirements:
   - Include relevant keywords naturally in the first paragraph
   - Use specific, descriptive terms that customers would search for
   - Mention key product attributes (size, material, color, use case) early
   - Focus on search intent (what problem does this solve?)
   - Avoid keyword stuffing - maintain natural, readable language
   - Include semantic variations of key terms

Return ONLY the rewritten description in HTML format. Do not include any explanations, notes, or markdown formatting. Just the HTML content that will go directly into the body_html field."""

    return prompt


def build_collection_description_prompt(collection_title: str, department: str, product_samples: List[str], voice_tone_doc: str) -> str:
    """
    Build the prompt for Claude to generate collection description.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions (body_html) from this collection
        voice_tone_doc: Full voice and tone guidelines document

    Returns:
        Formatted prompt string
    """
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


def enhance_product_with_claude(
    product: Dict,
    taxonomy_doc: str,
    voice_tone_doc: str,
    api_key: str,
    model: str,
    status_fn=None
) -> Dict:
    """
    Enhance a single product using Claude API.

    Args:
        product: Product dictionary
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: Claude API key
        model: Claude model ID
        status_fn: Optional status update function

    Returns:
        Enhanced product dictionary

    Raises:
        Exception: If API call fails or response is invalid
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Cannot enhance products. Install with: pip install anthropic"
        logging.error(error_msg)
        raise ImportError(error_msg)

    title = product.get('title', '')
    body_html = product.get('body_html', '')

    if not title:
        error_msg = f"Product has no title, cannot enhance: {product}"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # ========== STEP 1: TAXONOMY ASSIGNMENT ==========
        if status_fn:
            log_and_status(status_fn, f"  🤖 Assigning taxonomy for: {title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"CLAUDE API CALL #1: TAXONOMY ASSIGNMENT")
        logging.info(f"Product: {title}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        taxonomy_prompt = build_taxonomy_prompt(title, body_html, taxonomy_doc)

        # Log prompt preview (first 500 chars)
        logging.debug(f"Taxonomy prompt (first 500 chars):\n{taxonomy_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(taxonomy_prompt)} characters")

        # Make API call
        logging.info("Sending taxonomy assignment request to Claude API...")
        taxonomy_response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": taxonomy_prompt
            }]
        )

        # Log response details
        logging.info(f"✅ Taxonomy API call successful")
        logging.info(f"Response ID: {taxonomy_response.id}")
        logging.info(f"Model used: {taxonomy_response.model}")
        logging.info(f"Stop reason: {taxonomy_response.stop_reason}")
        logging.info(f"Token usage - Input: {taxonomy_response.usage.input_tokens}, Output: {taxonomy_response.usage.output_tokens}")

        taxonomy_cost = (taxonomy_response.usage.input_tokens * 0.003 / 1000) + (taxonomy_response.usage.output_tokens * 0.015 / 1000)
        logging.info(f"Cost: ${taxonomy_cost:.6f}")

        # Extract taxonomy from response
        taxonomy_text = taxonomy_response.content[0].text.strip()
        logging.debug(f"Raw taxonomy response:\n{taxonomy_text}")

        # Remove markdown code blocks if present
        if taxonomy_text.startswith("```"):
            logging.debug("Removing markdown code block wrapper from taxonomy response")
            lines = taxonomy_text.split('\n')
            taxonomy_text = '\n'.join(lines[1:-1])

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
        time.sleep(0.5)  # Brief delay between API calls

        if status_fn:
            log_and_status(status_fn, f"  ✍️  Rewriting description...")

        logging.info("=" * 80)
        logging.info(f"CLAUDE API CALL #2: DESCRIPTION REWRITING")
        logging.info(f"Product: {title}")
        logging.info(f"Department: {department}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        description_prompt = build_description_prompt(title, body_html, department, voice_tone_doc)

        # Log prompt preview
        logging.debug(f"Description prompt (first 500 chars):\n{description_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(description_prompt)} characters")

        # Make API call
        logging.info("Sending description rewriting request to Claude API...")
        description_response = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": description_prompt
            }]
        )

        # Log response details
        logging.info(f"✅ Description API call successful")
        logging.info(f"Response ID: {description_response.id}")
        logging.info(f"Model used: {description_response.model}")
        logging.info(f"Stop reason: {description_response.stop_reason}")
        logging.info(f"Token usage - Input: {description_response.usage.input_tokens}, Output: {description_response.usage.output_tokens}")

        description_cost = (description_response.usage.input_tokens * 0.003 / 1000) + (description_response.usage.output_tokens * 0.015 / 1000)
        logging.info(f"Cost: ${description_cost:.6f}")

        total_cost = taxonomy_cost + description_cost
        logging.info(f"Total cost for this product: ${total_cost:.6f}")

        # Extract enhanced description
        enhanced_description = description_response.content[0].text.strip()
        logging.debug(f"Enhanced description (first 500 chars):\n{enhanced_description[:500]}...")

        # Remove markdown code blocks if present
        if enhanced_description.startswith("```"):
            logging.debug("Removing markdown code block wrapper from description response")
            lines = enhanced_description.split('\n')
            enhanced_description = '\n'.join(lines[1:-1])

        logging.info(f"✅ Description rewritten ({len(enhanced_description)} characters)")

        if status_fn:
            log_and_status(status_fn, f"    ✅ Description rewritten ({len(enhanced_description)} characters)")

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

        logging.info("=" * 80)
        logging.info(f"✅ PRODUCT ENHANCEMENT COMPLETE: {title}")
        logging.info(f"Final taxonomy: {department} > {category} > {subcategory}")
        logging.info("=" * 80)

        return enhanced_product

    except Exception as e:
        # Log detailed error information
        error_msg = f"Error enhancing product '{title}' with Claude API"
        logging.error("=" * 80)
        logging.error(f"❌ {error_msg}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Error Details: {str(e)}")

        # Check if it's an Anthropic API error
        if anthropic and isinstance(e, anthropic.APIError):
            logging.error("This is an Anthropic API error")
            if hasattr(e, 'status_code'):
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
    Generate a collection description using Claude API.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions from this collection
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: Claude API key
        model: Claude model ID
        status_fn: Optional status update function

    Returns:
        Generated collection description (plain text)

    Raises:
        Exception: If API call fails
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Cannot generate collection descriptions."
        logging.error(error_msg)
        raise ImportError(error_msg)

    if not collection_title:
        error_msg = f"Collection has no title, cannot generate description"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        if status_fn:
            log_and_status(status_fn, f"  📝 Generating description for: {collection_title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"CLAUDE API CALL: COLLECTION DESCRIPTION")
        logging.info(f"Collection: {collection_title}")
        logging.info(f"Department: {department}")
        logging.info(f"Product samples: {len(product_samples)}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        collection_prompt = build_collection_description_prompt(
            collection_title,
            department,
            product_samples,
            voice_tone_doc
        )

        # Log prompt preview
        logging.debug(f"Collection prompt (first 500 chars):\n{collection_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(collection_prompt)} characters")

        # Make API call
        logging.info("Sending collection description request to Claude API...")
        response = client.messages.create(
            model=model,
            max_tokens=512,  # 100 words ~ 150 tokens, give buffer
            messages=[{
                "role": "user",
                "content": collection_prompt
            }]
        )

        # Log response details
        logging.info(f"✅ Collection description API call successful")
        logging.info(f"Response ID: {response.id}")
        logging.info(f"Model used: {response.model}")
        logging.info(f"Stop reason: {response.stop_reason}")
        logging.info(f"Token usage - Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")

        cost = (response.usage.input_tokens * 0.003 / 1000) + (response.usage.output_tokens * 0.015 / 1000)
        logging.info(f"Cost: ${cost:.6f}")

        # Extract description
        description = response.content[0].text.strip()
        logging.debug(f"Generated description ({len(description.split())} words):\n{description}")

        # Remove markdown code blocks if present
        if description.startswith("```"):
            logging.debug("Removing markdown code block wrapper from description")
            lines = description.split('\n')
            description = '\n'.join(lines[1:-1])

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

        # Check if it's an Anthropic API error
        if anthropic and isinstance(e, anthropic.APIError):
            logging.error("This is an Anthropic API error")
            if hasattr(e, 'status_code'):
                logging.error(f"HTTP Status Code: {e.status_code}")
            if hasattr(e, 'response'):
                logging.error(f"API Response: {e.response}")

        # Log full stack trace
        logging.exception("Full traceback:")
        logging.error("=" * 80)

        # Re-raise with clear message
        raise Exception(f"{error_msg}: {str(e)}") from e


def batch_enhance_products(
    products: List[Dict],
    cfg: Dict,
    status_fn,
    taxonomy_path: str = "docs/PRODUCT_TAXONOMY.md",
    voice_tone_path: str = "docs/VOICE_AND_TONE_GUIDELINES.md"
) -> List[Dict]:
    """
    Enhance multiple products with Claude API using caching.

    Args:
        products: List of product dictionaries
        cfg: Configuration dictionary
        status_fn: Status update function
        taxonomy_path: Path to taxonomy markdown file
        voice_tone_path: Path to voice and tone guidelines markdown file

    Returns:
        List of enhanced product dictionaries

    Raises:
        Exception: Stops immediately on API failure
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Install with: pip install anthropic"
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise ImportError(error_msg)

    api_key = cfg.get("CLAUDE_API_KEY", "").strip()
    model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    if not api_key:
        error_msg = "Claude API key not configured. Add your API key in Settings dialog."
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise ValueError(error_msg)

    # Load taxonomy and voice/tone documents
    log_and_status(status_fn, f"Loading taxonomy document: {taxonomy_path}")
    taxonomy_doc = load_markdown_file(taxonomy_path)
    if not taxonomy_doc:
        error_msg = f"Failed to load taxonomy document: {taxonomy_path}"
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise FileNotFoundError(error_msg)

    log_and_status(status_fn, f"Loading voice and tone guidelines: {voice_tone_path}")
    voice_tone_doc = load_markdown_file(voice_tone_path)
    if not voice_tone_doc:
        error_msg = f"Failed to load voice/tone document: {voice_tone_path}"
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise FileNotFoundError(error_msg)

    log_and_status(status_fn, f"✅ Loaded enhancement documents")
    log_and_status(status_fn, f"🤖 Using Claude model: {model}\n")

    # Load cache
    cache = load_cache()
    cached_products = cache.get("products", {})

    enhanced_products = []
    enhanced_count = 0
    cached_count = 0

    total = len(products)

    logging.info("=" * 80)
    logging.info(f"STARTING BATCH CLAUDE AI ENHANCEMENT")
    logging.info(f"Total products to process: {total}")
    logging.info(f"Model: {model}")
    logging.info("=" * 80)

    for i, product in enumerate(products, 1):
        title = product.get('title', f'Product {i}')
        log_and_status(
            status_fn,
            f"Processing product {i}/{total}: {title[:60]}...",
            ui_msg=f"Enhancing with Claude AI: {i}/{total}"
        )

        # Check cache
        product_hash = compute_product_hash(product)
        cache_key = product.get('id', product.get('handle', title))

        if cache_key in cached_products:
            cached_data = cached_products[cache_key]
            if cached_data.get('input_hash') == product_hash:
                # Use cached enhancement
                log_and_status(status_fn, f"  ♻️  Using cached enhancement")

                enhanced_product = product.copy()
                enhanced_product['product_type'] = cached_data.get('department', '')

                tags = []
                if cached_data.get('category'):
                    tags.append(cached_data['category'])
                if cached_data.get('subcategory'):
                    tags.append(cached_data['subcategory'])

                enhanced_product['tags'] = tags
                enhanced_product['body_html'] = cached_data.get('enhanced_description', product.get('body_html', ''))

                enhanced_products.append(enhanced_product)
                cached_count += 1
                continue

        # Not in cache or changed - enhance with Claude
        try:
            enhanced_product = enhance_product_with_claude(
                product,
                taxonomy_doc,
                voice_tone_doc,
                api_key,
                model,
                status_fn
            )

            # Save to cache
            cached_products[cache_key] = {
                "enhanced_at": datetime.now().isoformat(),
                "input_hash": product_hash,
                "department": enhanced_product.get('product_type', ''),
                "category": enhanced_product.get('tags', [])[0] if enhanced_product.get('tags') else '',
                "subcategory": enhanced_product.get('tags', [])[1] if len(enhanced_product.get('tags', [])) > 1 else '',
                "enhanced_description": enhanced_product.get('body_html', '')
            }
            enhanced_count += 1

            enhanced_products.append(enhanced_product)

        except Exception as e:
            # Claude API failed - stop processing immediately
            log_and_status(status_fn, "", "error")
            log_and_status(status_fn, "=" * 80, "error")
            log_and_status(status_fn, "❌ CLAUDE API ENHANCEMENT FAILED", "error")
            log_and_status(status_fn, "=" * 80, "error")
            log_and_status(status_fn, f"Product that failed: {title}", "error")
            log_and_status(status_fn, f"Product index: {i}/{total}", "error")
            log_and_status(status_fn, f"Error: {str(e)}", "error")
            log_and_status(status_fn, "", "error")
            log_and_status(status_fn, "Processing stopped to prevent data issues.", "error")
            log_and_status(status_fn, "Check the log file for detailed error information.", "error")
            log_and_status(status_fn, "=" * 80, "error")

            # Save cache before stopping
            cache["products"] = cached_products
            save_cache(cache)

            # Re-raise to stop processing
            raise

        # Rate limiting: ~10 requests per minute (5 products = 10 requests)
        if i % 5 == 0 and i < total:
            log_and_status(status_fn, f"  ⏸️  Rate limit pause (5 products processed)...")
            time.sleep(6)  # 6 second pause every 5 products

        log_and_status(status_fn, "")  # Empty line between products

    # Save cache
    cache["products"] = cached_products
    save_cache(cache)

    # Summary
    logging.info("=" * 80)
    logging.info(f"BATCH CLAUDE AI ENHANCEMENT COMPLETE")
    logging.info(f"Newly enhanced: {enhanced_count}")
    logging.info(f"Used cache: {cached_count}")
    logging.info(f"Total processed: {total}")
    logging.info("=" * 80)

    log_and_status(status_fn, "=" * 80)
    log_and_status(status_fn, "CLAUDE AI ENHANCEMENT SUMMARY")
    log_and_status(status_fn, "=" * 80)
    log_and_status(status_fn, f"✅ Newly enhanced: {enhanced_count}")
    log_and_status(status_fn, f"♻️  Used cache: {cached_count}")
    log_and_status(status_fn, f"📊 Total processed: {total}")

    return enhanced_products
