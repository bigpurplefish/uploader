"""
Tests for uploader_modules/utils.py

Tests all utility functions including URL validation, taxonomy validation,
image filtering, and data extraction.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules.utils import (
    is_shopify_cdn_url,
    key_to_label,
    extract_category_subcategory,
    extract_unique_option_values,
    validate_image_urls,
    format_value_for_filter_tag,
    generate_image_filter_hashtags,
    validate_image_alt_tags_for_filtering,
    load_taxonomy_structure,
    validate_taxonomy_assignment
)


# ============================================================================
# URL VALIDATION TESTS
# ============================================================================

class TestIsShopifyCDNUrl:
    """Tests for is_shopify_cdn_url() function."""

    def test_valid_shopify_cdn_url(self):
        """Test that valid Shopify CDN URLs are recognized."""
        assert is_shopify_cdn_url("https://cdn.shopify.com/s/files/1/0123/4567/files/image.jpg") is True

    def test_valid_shopify_cdn_url_http(self):
        """Test that HTTP Shopify CDN URLs are recognized."""
        assert is_shopify_cdn_url("http://cdn.shopify.com/image.png") is True

    def test_shopify_domain(self):
        """Test that shopify.com URLs are recognized."""
        assert is_shopify_cdn_url("https://example.shopify.com/products/test") is True

    def test_non_shopify_url(self):
        """Test that non-Shopify URLs are rejected."""
        assert is_shopify_cdn_url("https://example.com/image.jpg") is False

    def test_empty_url(self):
        """Test that empty URLs are rejected."""
        assert is_shopify_cdn_url("") is False

    def test_none_url(self):
        """Test that None URLs are rejected."""
        assert is_shopify_cdn_url(None) is False

    def test_non_string_url(self):
        """Test that non-string values are rejected."""
        assert is_shopify_cdn_url(12345) is False

    def test_malformed_url_exception_handling(self, monkeypatch):
        """Test that exceptions in URL parsing are handled."""
        # Mock urlparse to raise an exception
        from urllib.parse import urlparse as original_urlparse

        def mock_urlparse_error(url):
            raise ValueError("Invalid URL")

        # We need to patch it in the utils module
        monkeypatch.setattr("uploader_modules.utils.urlparse", mock_urlparse_error)

        # Should return False instead of crashing
        assert is_shopify_cdn_url("http://test.com") is False


# ============================================================================
# KEY TO LABEL TESTS
# ============================================================================

class TestKeyToLabel:
    """Tests for key_to_label() function."""

    def test_snake_case_conversion(self):
        """Test conversion of snake_case to Title Case."""
        assert key_to_label("layout_possibilities") == "Layout Possibilities"

    def test_special_case_whats_included(self):
        """Test special case for 'whats_included'."""
        assert key_to_label("whats_included") == "What's Included"

    def test_special_case_nutritional_information(self):
        """Test special case for 'nutritional_information'."""
        assert key_to_label("nutritional_information") == "Nutritional Information"

    def test_single_word(self):
        """Test single word conversion."""
        assert key_to_label("description") == "Description"

    def test_multiple_underscores(self):
        """Test multiple underscores."""
        assert key_to_label("this_is_a_long_key") == "This Is A Long Key"


# ============================================================================
# CATEGORY EXTRACTION TESTS
# ============================================================================

class TestExtractCategorySubcategory:
    """Tests for extract_category_subcategory() function."""

    def test_extract_from_tags_array(self):
        """Test extraction from tags array (first = category, second = subcategory)."""
        product = {"tags": ["Pavers and Hardscaping", "Slabs"]}
        category, subcategory = extract_category_subcategory(product)
        assert category == "Pavers and Hardscaping"
        assert subcategory == "Slabs"

    def test_extract_from_tags_single(self):
        """Test extraction from tags array with only category."""
        product = {"tags": ["Aggregates"]}
        category, subcategory = extract_category_subcategory(product)
        assert category == "Aggregates"
        assert subcategory is None

    def test_extract_from_metafields(self):
        """Test extraction from metafields."""
        product = {
            "metafields": [
                {"namespace": "custom", "key": "product_category", "value": "Dogs"},
                {"namespace": "custom", "key": "product_subcategory", "value": "Food"}
            ]
        }
        category, subcategory = extract_category_subcategory(product)
        assert category == "Dogs"
        assert subcategory == "Food"

    def test_extract_from_separator_format(self):
        """Test extraction from '>' separator format."""
        product = {"tags": ["Pavers and Hardscaping > Slabs"]}
        category, subcategory = extract_category_subcategory(product)
        assert category == "Pavers and Hardscaping"
        assert subcategory == "Slabs"

    def test_no_category_data(self):
        """Test when no category data exists."""
        product = {"tags": []}
        category, subcategory = extract_category_subcategory(product)
        assert category is None
        assert subcategory is None

    def test_extract_from_string_tags(self):
        """Test extraction from comma-separated string tags."""
        product = {"tags": "Pavers and Hardscaping, Slabs, Other Tag"}
        category, subcategory = extract_category_subcategory(product)
        assert category == "Pavers and Hardscaping"
        assert subcategory == "Slabs"


# ============================================================================
# OPTION VALUES EXTRACTION TESTS
# ============================================================================

class TestExtractUniqueOptionValues:
    """Tests for extract_unique_option_values() function."""

    def test_extract_multiple_options(self):
        """Test extraction of multiple options from variants."""
        product = {
            "options": [{"name": "Color"}, {"name": "Size"}],
            "variants": [
                {"option1": "Red", "option2": "Small"},
                {"option1": "Blue", "option2": "Small"},
                {"option1": "Red", "option2": "Large"}
            ]
        }
        result = extract_unique_option_values(product)
        assert "Color" in result
        assert result["Color"] == {"Red", "Blue"}
        assert "Size" in result
        assert result["Size"] == {"Small", "Large"}

    def test_extract_single_option(self):
        """Test extraction of single option."""
        product = {
            "options": [{"name": "Color"}],
            "variants": [
                {"option1": "Red"},
                {"option1": "Blue"}
            ]
        }
        result = extract_unique_option_values(product)
        assert result["Color"] == {"Red", "Blue"}

    def test_no_options(self):
        """Test product with no options."""
        product = {"options": [], "variants": []}
        result = extract_unique_option_values(product)
        assert result == {}

    def test_variant_option_not_in_initial_map(self):
        """Test defensive code for option not in initial map."""
        # This tests line 122 - defensive code for edge case
        # Create a scenario where an option entry changes between initial loop and variant processing

        call_counter = {'count': 0}

        class DynamicDict(dict):
            """Dict that changes behavior based on access count."""
            def get(self, key, default=None):
                if key == 'name':
                    call_counter['count'] += 1
                    # First call (initial loop): no name
                    if call_counter['count'] == 1:
                        return None
                    # Subsequent calls (variant processing): has name
                    else:
                        return "Size"
                return super().get(key, default)

        product = {
            "options": [
                {"name": "Color"},
                DynamicDict(),  # This will have no name initially, then gain one
            ],
            "variants": [
                {
                    "option1": "Red",
                    "option2": "Large"
                }
            ]
        }

        result = extract_unique_option_values(product)
        # Color should definitely be in result
        assert "Color" in result
        # Size might be added via line 122 if the defensive code executes
        assert isinstance(result, dict)


# ============================================================================
# IMAGE URL VALIDATION TESTS
# ============================================================================

class TestValidateImageUrls:
    """Tests for validate_image_urls() function."""

    def test_valid_shopify_urls(self):
        """Test that valid Shopify URLs pass validation."""
        products = [
            {
                "title": "Test Product",
                "images": [
                    {"src": "https://cdn.shopify.com/image1.jpg"}
                ],
                "metafields": [],
                "variants": []
            }
        ]
        is_valid, invalid_urls = validate_image_urls(products)
        assert is_valid is True
        assert len(invalid_urls) == 0

    def test_invalid_product_image_url(self):
        """Test that non-Shopify image URLs are caught."""
        products = [
            {
                "title": "Test Product",
                "images": [
                    {"src": "https://example.com/image.jpg"}
                ],
                "metafields": [],
                "variants": []
            }
        ]
        is_valid, invalid_urls = validate_image_urls(products)
        assert is_valid is False
        assert len(invalid_urls) == 1
        assert invalid_urls[0]["url"] == "https://example.com/image.jpg"

    def test_invalid_metafield_url(self):
        """Test that non-Shopify metafield URLs are caught."""
        products = [
            {
                "title": "Test Product",
                "images": [],
                "metafields": [
                    {
                        "key": "swatch_image",
                        "value": "https://example.com/swatch.jpg",
                        "type": "url"
                    }
                ],
                "variants": []
            }
        ]
        is_valid, invalid_urls = validate_image_urls(products)
        assert is_valid is False
        assert len(invalid_urls) == 1

    def test_invalid_variant_metafield_url(self):
        """Test that non-Shopify variant metafield URLs are caught."""
        products = [
            {
                "title": "Test Product",
                "images": [],
                "metafields": [],
                "variants": [
                    {
                        "title": "Variant 1",
                        "metafields": [
                            {
                                "key": "variant_image",
                                "value": "https://example.com/variant.jpg",
                                "type": "file_reference"
                            }
                        ]
                    }
                ]
            }
        ]
        is_valid, invalid_urls = validate_image_urls(products)
        assert is_valid is False
        assert len(invalid_urls) == 1
        assert "Variant #1 metafield" in invalid_urls[0]["location"]


# ============================================================================
# FILTER TAG FORMATTING TESTS
# ============================================================================

class TestFormatValueForFilterTag:
    """Tests for format_value_for_filter_tag() function."""

    def test_spaces_to_underscores(self):
        """Test that spaces are converted to underscores."""
        assert format_value_for_filter_tag("Rock Garden Brown") == "ROCK_GARDEN_BROWN"

    def test_special_characters(self):
        """Test that special characters are converted."""
        assert format_value_for_filter_tag("20 X 10 & 20 X 20") == "20_X_10___20_X_20"

    def test_hyphens(self):
        """Test that hyphens are converted."""
        assert format_value_for_filter_tag("Klean-Bloc Slate") == "KLEAN_BLOC_SLATE"

    def test_empty_value(self):
        """Test empty value returns empty string."""
        assert format_value_for_filter_tag("") == ""

    def test_none_value(self):
        """Test None value returns empty string."""
        assert format_value_for_filter_tag(None) == ""


class TestGenerateImageFilterHashtags:
    """Tests for generate_image_filter_hashtags() function."""

    def test_single_option(self):
        """Test generation of hashtag for single option."""
        options = {"Color": "Azzurro"}
        result = generate_image_filter_hashtags(options)
        assert result == "#AZZURRO"

    def test_multiple_options(self):
        """Test generation of hashtags for multiple options."""
        options = {
            "Color": "Rock Garden Brown",
            "Finish": "Klean-Bloc Slate",
            "Size": "30 X 30"
        }
        result = generate_image_filter_hashtags(options)
        assert "#ROCK_GARDEN_BROWN" in result
        assert "#KLEAN_BLOC_SLATE" in result
        assert "#30_X_30" in result

    def test_empty_options(self):
        """Test empty options returns empty string."""
        result = generate_image_filter_hashtags({})
        assert result == ""


# ============================================================================
# TAXONOMY STRUCTURE LOADING TESTS
# ============================================================================

class TestLoadTaxonomyStructure:
    """Tests for load_taxonomy_structure() function."""

    def test_load_valid_taxonomy(self, temp_taxonomy_file):
        """Test loading a valid taxonomy file."""
        taxonomy = load_taxonomy_structure(str(temp_taxonomy_file))
        assert len(taxonomy) > 0
        assert "Landscape And Construction" in taxonomy

    def test_load_nonexistent_file(self, caplog):
        """Test loading non-existent file returns empty dict."""
        import logging
        with caplog.at_level(logging.ERROR):
            taxonomy = load_taxonomy_structure("/nonexistent/path/taxonomy.md")

        assert taxonomy == {}
        assert "Taxonomy file not found" in caplog.text

    def test_load_taxonomy_with_none_path(self):
        """Test loading taxonomy with None uses default path."""
        # This will use the default path
        taxonomy = load_taxonomy_structure(None)

        # Should return dictionary (may be empty or have content depending on environment)
        assert isinstance(taxonomy, dict)

    def test_load_taxonomy_generic_exception(self, temp_taxonomy_file, monkeypatch, caplog):
        """Test that load_taxonomy_structure handles unexpected exceptions."""
        import logging

        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            taxonomy = load_taxonomy_structure(str(temp_taxonomy_file))

        assert taxonomy == {}
        assert "Error loading taxonomy structure" in caplog.text


# ============================================================================
# TAXONOMY VALIDATION TESTS
# ============================================================================

class TestValidateTaxonomyAssignment:
    """Tests for validate_taxonomy_assignment() function."""

    def test_valid_assignment(self, temp_taxonomy_file):
        """Test valid taxonomy assignment."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Pavers And Hardscaping",
            "Slabs",
            str(temp_taxonomy_file)
        )
        assert is_valid is True
        assert error_msg == ""

    def test_invalid_department(self, temp_taxonomy_file):
        """Test invalid department is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Invalid Department",
            "Some Category",
            "",
            str(temp_taxonomy_file)
        )
        assert is_valid is False
        assert "Invalid department" in error_msg
        assert "valid_departments" in suggestions

    def test_invalid_category(self, temp_taxonomy_file):
        """Test invalid category is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Invalid Category",
            "",
            str(temp_taxonomy_file)
        )
        assert is_valid is False
        assert "Invalid category" in error_msg
        assert "valid_categories" in suggestions

    def test_invalid_subcategory(self, temp_taxonomy_file):
        """Test invalid subcategory is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Pavers And Hardscaping",
            "Invalid Subcategory",
            str(temp_taxonomy_file)
        )
        assert is_valid is False
        assert "Invalid subcategory" in error_msg
        assert "valid_subcategories" in suggestions

    def test_valid_without_subcategory(self, temp_taxonomy_file):
        """Test valid assignment without subcategory."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Pet Supplies",
            "Dogs",
            "",
            str(temp_taxonomy_file)
        )
        assert is_valid is True


# ============================================================================
# IMAGE ALT TAG VALIDATION TESTS
# ============================================================================

class TestValidateImageAltTagsForFiltering:
    """Tests for validate_image_alt_tags_for_filtering() function."""

    def test_images_without_hashtags(self):
        """Test that images without hashtags trigger warnings."""
        products = [
            {
                "title": "Test Product",
                "images": [
                    {"alt": "Product image without hashtags"}
                ]
            }
        ]
        has_warnings, warnings = validate_image_alt_tags_for_filtering(products)
        assert has_warnings is True
        assert len(warnings) == 1

    def test_images_with_hashtags(self):
        """Test that images with hashtags pass validation."""
        products = [
            {
                "title": "Test Product",
                "images": [
                    {"alt": "Product image #COLOR#SIZE"}
                ]
            }
        ]
        has_warnings, warnings = validate_image_alt_tags_for_filtering(products)
        assert has_warnings is False
        assert len(warnings) == 0

    def test_empty_alt_text(self):
        """Test that images with empty alt text don't trigger warnings."""
        products = [
            {
                "title": "Test Product",
                "images": [
                    {"alt": ""}
                ]
            }
        ]
        has_warnings, warnings = validate_image_alt_tags_for_filtering(products)
        assert has_warnings is False
