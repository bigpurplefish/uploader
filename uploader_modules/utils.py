"""
Utility functions for Shopify Product Uploader.
"""

from urllib.parse import urlparse


def is_shopify_cdn_url(url):
    """Check if URL is from Shopify CDN."""
    try:
        if not url or not isinstance(url, str):
            return False
        parsed = urlparse(url.lower())
        shopify_domains = ['cdn.shopify.com', 'shopify.com']
        return any(domain in parsed.netloc for domain in shopify_domains)
    except Exception:
        return False


def key_to_label(key):
    """
    Convert a metafield key to a human-readable label.
    Examples:
        'layout_possibilities' -> 'Layout Possibilities'
        'whats_included' -> 'What's Included'
        'additional_documentation' -> 'Additional Documentation'
    """
    # Handle special cases
    special_cases = {
        'whats_included': "What's Included",
        'nutritional_information': 'Nutritional Information',
    }

    if key in special_cases:
        return special_cases[key]

    # Convert snake_case to Title Case
    words = key.replace('_', ' ').split()
    return ' '.join(word.capitalize() for word in words)


def extract_category_subcategory(product):
    """
    Extract category and subcategory from product data.

    Priority order:
    1. Metafields (custom.product_category, custom.product_subcategory)
    2. Tags in array format (first tag = category, second tag = subcategory)
    3. Tags with '>' separator (format: 'Category > Subcategory')

    Args:
        product: Product dictionary

    Returns:
        Tuple of (category, subcategory) or (None, None)
    """
    # Try metafields first
    for mf in product.get('metafields', []):
        if mf.get('namespace') == 'custom' and mf.get('key') == 'product_category':
            category = mf.get('value', '').strip()

            # Look for subcategory in metafields
            subcategory = None
            for mf2 in product.get('metafields', []):
                if mf2.get('namespace') == 'custom' and mf2.get('key') == 'product_subcategory':
                    subcategory = mf2.get('value', '').strip()
                    break

            return (category if category else None, subcategory if subcategory else None)

    # Try tags - handle multiple formats
    tags = product.get('tags', [])
    if isinstance(tags, str):
        # Split comma-separated tags
        tags = [t.strip() for t in tags.split(',') if t.strip()]

    # Check for '>' separator format first (format: 'Category > Subcategory')
    for tag in tags:
        if '>' in tag:
            parts = [p.strip() for p in tag.split('>')]
            if len(parts) == 2:
                return (parts[0], parts[1])

    # If no '>' format, treat multiple tags as category/subcategory
    # First tag = category, second tag = subcategory
    if len(tags) >= 2:
        return (tags[0], tags[1])
    elif len(tags) == 1:
        return (tags[0], None)

    return (None, None)


def extract_unique_option_values(product):
    """
    Extract all unique option values from product variants.

    Returns a dictionary mapping option names to sets of unique values.
    Example: {"Color": {"Red", "Blue"}, "Size": {"Small", "Large"}}
    """
    option_values_map = {}

    # Get option names from product options
    for opt in product.get('options', []):
        if isinstance(opt, dict):
            option_name = opt.get('name')
            if option_name:
                option_values_map[option_name] = set()

    # Collect all unique values from variants
    for variant in product.get('variants', []):
        for i in range(1, 4):  # option1, option2, option3
            option_key = f'option{i}'
            if option_key in variant and variant[option_key]:
                # Find the corresponding option name
                if i-1 < len(product.get('options', [])):
                    option_dict = product.get('options', [])[i-1]
                    if isinstance(option_dict, dict):
                        option_name = option_dict.get('name')
                        if option_name:
                            if option_name not in option_values_map:
                                option_values_map[option_name] = set()
                            option_values_map[option_name].add(str(variant[option_key]))

    return option_values_map


def validate_image_urls(products):
    """
    Validate that all image URLs in products are Shopify CDN URLs.

    According to Shopify's requirements, all image URLs must be pre-uploaded
    to Shopify CDN before creating products. This function scans all products
    for non-Shopify CDN URLs in images and metafields.

    Args:
        products: List of product dictionaries

    Returns:
        Tuple of (is_valid, invalid_urls_list)
        - is_valid: True if all URLs are valid, False otherwise
        - invalid_urls_list: List of dicts with {product_title, location, url}
    """
    invalid_urls = []

    for product in products:
        product_title = product.get('title', 'Unknown Product')

        # Check product images
        for idx, img in enumerate(product.get('images', [])):
            img_url = img.get('src', '')
            if img_url and not is_shopify_cdn_url(img_url):
                invalid_urls.append({
                    'product_title': product_title,
                    'location': f'Product image #{idx + 1}',
                    'url': img_url
                })

        # Check product metafields for URL types
        for mf in product.get('metafields', []):
            mf_type = mf.get('type', '')
            mf_value = mf.get('value', '')
            mf_key = mf.get('key', '')

            if mf_type in ['url', 'file_reference'] and mf_value:
                if not is_shopify_cdn_url(mf_value):
                    invalid_urls.append({
                        'product_title': product_title,
                        'location': f'Product metafield: {mf_key}',
                        'url': mf_value
                    })

        # Check variant metafields for URL types
        # Also check known image metafield keys that may have single_line_text_field type
        IMAGE_METAFIELD_KEYS = {'color_swatch_image', 'texture_swatch_image', 'finish_swatch_image'}

        for var_idx, variant in enumerate(product.get('variants', [])):
            for mf in variant.get('metafields', []):
                mf_type = mf.get('type', '')
                mf_value = mf.get('value', '')
                mf_key = mf.get('key', '')

                # Check URL/file_reference types OR known image metafield keys
                is_url_type = mf_type in ['url', 'file_reference']
                is_image_key = mf_key in IMAGE_METAFIELD_KEYS

                if (is_url_type or is_image_key) and mf_value:
                    if not is_shopify_cdn_url(mf_value):
                        invalid_urls.append({
                            'product_title': product_title,
                            'location': f'Variant #{var_idx + 1} metafield: {mf_key}',
                            'url': mf_value
                        })

    is_valid = len(invalid_urls) == 0
    return is_valid, invalid_urls


def format_value_for_filter_tag(value):
    """
    Format an option value for use in image alt tag filter hashtags.

    Replaces spaces and special characters with underscores to match
    Shopify theme filtering requirements.

    Args:
        value: The option value string (e.g., "20 X 10 & 20 X 20")

    Returns:
        Formatted string (e.g., "20_X_10___20_X_20")

    Examples:
        "ROCK GARDEN BROWN" -> "ROCK_GARDEN_BROWN"
        "20 X 10 & 20 X 20" -> "20_X_10___20_X_20"
        "KLEAN-BLOC SLATE" -> "KLEAN_BLOC_SLATE"
    """
    if not value:
        return ""

    # Convert to uppercase and replace spaces and special chars with underscores
    formatted = str(value).upper()
    # Replace common separators with underscores
    for char in [' ', '-', '/', '&', '+', ',', '.']:
        formatted = formatted.replace(char, '_')

    return formatted


def generate_image_filter_hashtags(options_dict):
    """
    Generate filter hashtags for image alt tags based on variant options.

    Many Shopify themes use hashtags in image alt text to filter which images
    display when users select different variant options (color, size, finish, etc.).

    Args:
        options_dict: Dictionary mapping option names to values
                     E.g., {"Color": "Rock Garden Brown", "Finish": "Klean-Bloc Slate", "Size": "20 X 10 & 20 X 20"}

    Returns:
        String of hashtags (e.g., "#ROCK_GARDEN_BROWN#KLEAN_BLOC_SLATE#20_X_10___20_X_20")

    Example:
        >>> generate_image_filter_hashtags({"Color": "Azzurro", "Finish": "Klean-Bloc Slate", "Size": "30 X 30"})
        "#AZZURRO#KLEAN_BLOC_SLATE#30_X_30"
    """
    if not options_dict:
        return ""

    hashtags = []
    for value in options_dict.values():
        if value:
            formatted_value = format_value_for_filter_tag(value)
            if formatted_value:
                hashtags.append(f"#{formatted_value}")

    return "".join(hashtags)


def validate_image_alt_tags_for_filtering(products):
    """
    Check if images have alt tags with filter hashtags for variant-based filtering.

    Many Shopify themes filter product images based on hashtags in alt text.
    This function identifies images that may be missing filter tags.

    Args:
        products: List of product dictionaries

    Returns:
        Tuple of (has_warnings, warnings_list)
        - has_warnings: True if any images lack filter hashtags
        - warnings_list: List of dicts with {product_title, image_index, current_alt}
    """
    warnings = []

    for product in products:
        product_title = product.get('title', 'Unknown Product')

        for idx, img in enumerate(product.get('images', [])):
            alt_text = img.get('alt', '')

            # Check if alt text contains hashtags (filter tags)
            if alt_text and '#' not in alt_text:
                warnings.append({
                    'product_title': product_title,
                    'image_index': idx + 1,
                    'current_alt': alt_text,
                    'suggestion': 'Add filter hashtags like #COLOR#FINISH#SIZE to enable variant-based filtering'
                })

    has_warnings = len(warnings) > 0
    return has_warnings, warnings


def load_taxonomy_structure(taxonomy_path: str = None) -> dict:
    """
    Load and parse the product taxonomy structure from PRODUCT_TAXONOMY.md.

    Args:
        taxonomy_path: Path to PRODUCT_TAXONOMY.md file

    Returns:
        Dictionary with taxonomy structure:
        {
            "Landscape and Construction": {
                "Aggregates": ["Stone", "Soil", "Mulch", "Sand"],
                "Pavers and Hardscaping": ["Slabs", "Pavers", ...],
                ...
            },
            ...
        }
    """
    import os
    import re
    import logging

    if not taxonomy_path:
        # Default path
        taxonomy_path = "/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md"

    if not os.path.exists(taxonomy_path):
        logging.error(f"Taxonomy file not found: {taxonomy_path}")
        return {}

    try:
        with open(taxonomy_path, 'r', encoding='utf-8') as f:
            content = f.read()

        taxonomy = {}
        current_department = None
        current_category = None

        lines = content.split('\n')

        for line in lines:
            # Match department headers: "### 1. LANDSCAPE AND CONSTRUCTION"
            dept_match = re.match(r'^### \d+\.\s+(.+)$', line)
            if dept_match:
                dept_name_upper = dept_match.group(1).strip()
                # Convert to title case to match our standard format
                current_department = dept_name_upper.title()
                if current_department not in taxonomy:
                    taxonomy[current_department] = {}
                current_category = None
                continue

            # Match category headers: "#### Aggregates"
            cat_match = re.match(r'^####\s+(.+)$', line)
            if cat_match and current_department:
                current_category = cat_match.group(1).strip()
                if current_category not in taxonomy[current_department]:
                    taxonomy[current_department][current_category] = []
                continue

            # Match subcategory entries: "  1. **Stone** - Options: 1, 2"
            subcat_match = re.match(r'^\s+\d+\.\s+\*\*(.+?)\*\*', line)
            if subcat_match and current_department and current_category:
                subcategory = subcat_match.group(1).strip()
                if subcategory not in taxonomy[current_department][current_category]:
                    taxonomy[current_department][current_category].append(subcategory)
                continue

        logging.info(f"Loaded taxonomy structure with {len(taxonomy)} departments")
        return taxonomy

    except Exception as e:
        logging.error(f"Error loading taxonomy structure: {e}")
        return {}


def validate_taxonomy_assignment(department: str, category: str, subcategory: str, taxonomy_path: str = None) -> tuple:
    """
    Validate that taxonomy assignment matches the defined taxonomy structure.

    Args:
        department: Department name from AI
        category: Category name from AI
        subcategory: Subcategory name from AI (can be empty)
        taxonomy_path: Optional path to taxonomy file

    Returns:
        Tuple of (is_valid: bool, error_message: str, suggestions: dict)
    """
    import logging

    taxonomy = load_taxonomy_structure(taxonomy_path)

    if not taxonomy:
        return (False, "Failed to load taxonomy structure for validation", {})

    # Check department
    if department not in taxonomy:
        valid_departments = list(taxonomy.keys())
        return (
            False,
            f"Invalid department: '{department}' is not in the defined taxonomy",
            {
                "valid_departments": valid_departments,
                "suggestion": f"Add '{department}' to PRODUCT_TAXONOMY.md or correct the product data"
            }
        )

    # Check category
    if category not in taxonomy[department]:
        valid_categories = list(taxonomy[department].keys())
        return (
            False,
            f"Invalid category: '{category}' does not exist under department '{department}'",
            {
                "valid_categories": valid_categories,
                "suggestion": f"Add '{category}' under '{department}' in PRODUCT_TAXONOMY.md or correct the product data"
            }
        )

    # Check subcategory (if provided)
    if subcategory:
        valid_subcategories = taxonomy[department][category]
        if valid_subcategories and subcategory not in valid_subcategories:
            return (
                False,
                f"Invalid subcategory: '{subcategory}' does not exist under '{department}' > '{category}'",
                {
                    "valid_subcategories": valid_subcategories if valid_subcategories else ["(no subcategories defined)"],
                    "suggestion": f"Add '{subcategory}' under '{department}' > '{category}' in PRODUCT_TAXONOMY.md or correct the product data"
                }
            )

    logging.debug(f"✅ Taxonomy validation passed: {department} > {category} > {subcategory}")
    return (True, "", {})
