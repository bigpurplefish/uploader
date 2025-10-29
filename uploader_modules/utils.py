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
        for var_idx, variant in enumerate(product.get('variants', [])):
            for mf in variant.get('metafields', []):
                mf_type = mf.get('type', '')
                mf_value = mf.get('value', '')
                mf_key = mf.get('key', '')

                if mf_type in ['url', 'file_reference'] and mf_value:
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
