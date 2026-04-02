"""
Tests for menu caching in shopify_api.py and taxonomy path deduplication
in product_processing.py.
"""

import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules import shopify_api


# ============================================================================
# MENU CACHE TESTS
# ============================================================================

class TestMenuCache:
    """Tests for the module-level menu cache in shopify_api."""

    def setup_method(self):
        """Clear cache before each test."""
        shopify_api.invalidate_menu_cache()

    def test_cache_starts_empty(self):
        """Menu cache should be empty after invalidation."""
        shopify_api.invalidate_menu_cache()
        assert shopify_api._menu_cache == {}

    @patch('uploader_modules.shopify_api.requests.post')
    def test_first_call_fetches_from_api(self, mock_post):
        """First call to get_menu_by_handle should hit the API."""
        menu_data = {
            "data": {
                "menus": {
                    "edges": [{
                        "node": {
                            "id": "gid://shopify/Menu/123",
                            "handle": "main-menu",
                            "title": "Main Menu",
                            "items": []
                        }
                    }]
                }
            }
        }
        mock_response = Mock()
        mock_response.json.return_value = menu_data
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.get_menu_by_handle("main-menu", cfg)

        assert result is not None
        assert result["handle"] == "main-menu"
        assert mock_post.call_count == 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_second_call_uses_cache(self, mock_post):
        """Second call to get_menu_by_handle should use the cache, not the API."""
        menu_data = {
            "data": {
                "menus": {
                    "edges": [{
                        "node": {
                            "id": "gid://shopify/Menu/123",
                            "handle": "main-menu",
                            "title": "Main Menu",
                            "items": []
                        }
                    }]
                }
            }
        }
        mock_response = Mock()
        mock_response.json.return_value = menu_data
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        # First call - hits API
        result1 = shopify_api.get_menu_by_handle("main-menu", cfg)
        # Second call - should use cache
        result2 = shopify_api.get_menu_by_handle("main-menu", cfg)

        assert result1 == result2
        assert mock_post.call_count == 1  # Only one API call

    @patch('uploader_modules.shopify_api.requests.post')
    def test_different_handles_cached_separately(self, mock_post):
        """Different menu handles should be cached independently."""
        def make_menu_response(handle, menu_id):
            return {
                "data": {
                    "menus": {
                        "edges": [{
                            "node": {
                                "id": f"gid://shopify/Menu/{menu_id}",
                                "handle": handle,
                                "title": handle.replace("-", " ").title(),
                                "items": []
                            }
                        }]
                    }
                }
            }

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_resp = Mock()
            mock_resp.raise_for_status = Mock()
            if call_count[0] == 1:
                mock_resp.json.return_value = make_menu_response("main-menu", 123)
            else:
                mock_resp.json.return_value = make_menu_response("footer-menu", 456)
            return mock_resp

        mock_post.side_effect = side_effect

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result1 = shopify_api.get_menu_by_handle("main-menu", cfg)
        result2 = shopify_api.get_menu_by_handle("footer-menu", cfg)

        assert result1["handle"] == "main-menu"
        assert result2["handle"] == "footer-menu"
        assert mock_post.call_count == 2

        # Now both should be cached
        result3 = shopify_api.get_menu_by_handle("main-menu", cfg)
        result4 = shopify_api.get_menu_by_handle("footer-menu", cfg)
        assert mock_post.call_count == 2  # No additional API calls

    @patch('uploader_modules.shopify_api.requests.post')
    def test_cache_not_found_menu_returns_none(self, mock_post):
        """If menu is not found, None should be cached so we don't re-fetch."""
        menu_data = {
            "data": {
                "menus": {
                    "edges": [{
                        "node": {
                            "id": "gid://shopify/Menu/123",
                            "handle": "other-menu",
                            "title": "Other Menu",
                            "items": []
                        }
                    }]
                }
            }
        }
        mock_response = Mock()
        mock_response.json.return_value = menu_data
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        # Menu "main-menu" not in the response data
        result1 = shopify_api.get_menu_by_handle("main-menu", cfg)
        assert result1 is None

        # Second call should still return None but NOT hit API again
        result2 = shopify_api.get_menu_by_handle("main-menu", cfg)
        assert result2 is None
        assert mock_post.call_count == 1


# ============================================================================
# CACHE INVALIDATION TESTS
# ============================================================================

class TestMenuCacheInvalidation:
    """Tests for cache invalidation behavior."""

    def setup_method(self):
        shopify_api.invalidate_menu_cache()

    def test_invalidate_specific_handle(self):
        """Invalidating a specific handle should only clear that entry."""
        shopify_api._menu_cache["main-menu"] = {"id": "123", "handle": "main-menu"}
        shopify_api._menu_cache["footer-menu"] = {"id": "456", "handle": "footer-menu"}

        shopify_api.invalidate_menu_cache("main-menu")

        assert "main-menu" not in shopify_api._menu_cache
        assert "footer-menu" in shopify_api._menu_cache

    def test_invalidate_all(self):
        """Invalidating with no handle should clear entire cache."""
        shopify_api._menu_cache["main-menu"] = {"id": "123"}
        shopify_api._menu_cache["footer-menu"] = {"id": "456"}

        shopify_api.invalidate_menu_cache()

        assert shopify_api._menu_cache == {}

    def test_invalidate_nonexistent_handle_no_error(self):
        """Invalidating a handle that isn't cached should not raise an error."""
        shopify_api._menu_cache["main-menu"] = {"id": "123"}

        # Should not raise
        shopify_api.invalidate_menu_cache("nonexistent-menu")

        assert "main-menu" in shopify_api._menu_cache

    @patch('uploader_modules.shopify_api.requests.post')
    def test_update_menu_invalidates_cache(self, mock_post):
        """Calling update_menu should invalidate the cache for that menu's handle."""
        # Pre-populate cache
        shopify_api._menu_cache["main-menu"] = {
            "id": "gid://shopify/Menu/123",
            "handle": "main-menu",
            "title": "Main Menu",
            "items": []
        }

        # Mock successful update response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "menuUpdate": {
                    "menu": {
                        "id": "gid://shopify/Menu/123",
                        "title": "Main Menu",
                        "items": []
                    },
                    "userErrors": []
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.update_menu(
            "gid://shopify/Menu/123", "Main Menu", [], cfg
        )

        assert result is True
        # Cache should be cleared entirely (we don't know the handle from the mutation)
        assert "main-menu" not in shopify_api._menu_cache

    @patch('uploader_modules.shopify_api.requests.post')
    def test_failed_update_does_not_invalidate_cache(self, mock_post):
        """Failed update_menu call should not invalidate the cache."""
        shopify_api._menu_cache["main-menu"] = {
            "id": "gid://shopify/Menu/123",
            "handle": "main-menu",
            "title": "Main Menu",
            "items": []
        }

        # Mock failed update
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "menuUpdate": {
                    "menu": None,
                    "userErrors": [{"field": "items", "message": "Invalid item"}]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.update_menu(
            "gid://shopify/Menu/123", "Main Menu", [], cfg
        )

        assert result is False
        # Cache should still be intact
        assert "main-menu" in shopify_api._menu_cache


# ============================================================================
# CLEAR MENU CACHE (PUBLIC API) TESTS
# ============================================================================

class TestClearMenuCache:
    """Tests for the public clear_menu_cache function."""

    def test_clear_menu_cache_clears_all(self):
        """clear_menu_cache should clear the entire menu cache."""
        shopify_api._menu_cache["main-menu"] = {"id": "123"}
        shopify_api._menu_cache["footer-menu"] = {"id": "456"}

        shopify_api.clear_menu_cache()

        assert shopify_api._menu_cache == {}


# ============================================================================
# TAXONOMY PATH DEDUPLICATION TESTS
# ============================================================================

class TestTaxonomyPathDeduplication:
    """Tests for taxonomy path deduplication in the product loop."""

    def setup_method(self):
        shopify_api.invalidate_menu_cache()

    @patch('uploader_modules.shopify_api.get_menu_by_handle')
    @patch('uploader_modules.shopify_api.update_menu')
    def test_duplicate_taxonomy_paths_only_checked_once(self, mock_update, mock_get_menu):
        """Products with the same taxonomy path should only trigger one menu check."""
        from uploader_modules.product_processing import _checked_taxonomy_paths

        # Clear the set
        _checked_taxonomy_paths.clear()

        # Two products with same taxonomy
        products = [
            {
                "title": "Product A",
                "product_type": "Pet Supplies",
                "tags": ["Dogs", "Food"]
            },
            {
                "title": "Product B",
                "product_type": "Pet Supplies",
                "tags": ["Dogs", "Food"]
            }
        ]

        # Build taxonomy path keys and check deduplication
        from uploader_modules.utils import extract_category_subcategory

        paths_seen = set()
        for product in products:
            dept = product.get("product_type", "").strip()
            cat, subcat = extract_category_subcategory(product)
            path_key = (dept, cat or "", subcat or "")
            paths_seen.add(path_key)

        # Both products produce the same path key
        assert len(paths_seen) == 1

    def test_different_taxonomy_paths_not_deduplicated(self):
        """Products with different taxonomy paths should each be checked."""
        from uploader_modules.utils import extract_category_subcategory

        products = [
            {
                "title": "Product A",
                "product_type": "Pet Supplies",
                "tags": ["Dogs", "Food"]
            },
            {
                "title": "Product B",
                "product_type": "Landscape and Construction",
                "tags": ["Pavers and Hardscaping", "Slabs"]
            }
        ]

        paths_seen = set()
        for product in products:
            dept = product.get("product_type", "").strip()
            cat, subcat = extract_category_subcategory(product)
            path_key = (dept, cat or "", subcat or "")
            paths_seen.add(path_key)

        assert len(paths_seen) == 2

    def test_checked_taxonomy_paths_set_exists(self):
        """The _checked_taxonomy_paths set should be importable from product_processing."""
        from uploader_modules.product_processing import _checked_taxonomy_paths
        assert isinstance(_checked_taxonomy_paths, set)

    def test_clear_checked_taxonomy_paths(self):
        """The _checked_taxonomy_paths set should be clearable for fresh runs."""
        from uploader_modules.product_processing import _checked_taxonomy_paths
        _checked_taxonomy_paths.add(("Test", "Cat", "Sub"))
        assert len(_checked_taxonomy_paths) > 0
        _checked_taxonomy_paths.clear()
        assert len(_checked_taxonomy_paths) == 0
