"""
Tests for uploader_modules/shopify_api.py

Tests Shopify API helper functions and data formatting.
"""

import pytest
import json
import sys
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules import shopify_api


# ============================================================================
# SALES CHANNEL ID RETRIEVAL TESTS
# ============================================================================

class TestGetSalesChannelIds:
    """Tests for get_sales_channel_ids() function."""

    def test_missing_credentials(self, caplog):
        """Test that missing credentials returns None."""
        cfg = {}
        with caplog.at_level(logging.ERROR):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None
        assert "Shopify credentials not configured" in caplog.text

    def test_empty_store_url(self, caplog):
        """Test that empty store URL returns None."""
        cfg = {
            "SHOPIFY_STORE_URL": "",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        with caplog.at_level(logging.ERROR):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None

    def test_empty_access_token(self, caplog):
        """Test that empty access token returns None."""
        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": ""
        }
        with caplog.at_level(logging.ERROR):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_retrieval(self, mock_post, caplog):
        """Test successful retrieval of sales channel IDs."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publications": {
                    "edges": [
                        {"node": {"id": "gid://shopify/Publication/1", "name": "Online Store"}},
                        {"node": {"id": "gid://shopify/Publication/2", "name": "Point of Sale"}}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.INFO):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is not None
        assert "online_store" in result
        assert "point_of_sale" in result
        assert result["online_store"] == "gid://shopify/Publication/1"
        assert result["point_of_sale"] == "gid://shopify/Publication/2"
        assert "Retrieved 2 sales channel IDs" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None
        assert "GraphQL errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_no_sales_channels_found(self, mock_post, caplog):
        """Test when no sales channels are found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publications": {
                    "edges": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.WARNING):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None
        assert "No sales channels found" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None
        assert "Network error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_unexpected_error(self, mock_post, caplog):
        """Test handling of unexpected errors."""
        mock_post.side_effect = Exception("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.get_sales_channel_ids(cfg)

        assert result is None
        assert "Unexpected error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_strips_https_from_store_url(self, mock_post):
        """Test that https:// is stripped from store URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"publications": {"edges": []}}
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "https://test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        shopify_api.get_sales_channel_ids(cfg)

        # Verify the URL was constructed correctly without https://
        call_args = mock_post.call_args
        called_url = call_args[0][0]
        assert "https://test-store.myshopify.com/admin/" in called_url
        assert "https://https://" not in called_url


# ============================================================================
# COLLECTION PUBLISHING TESTS
# ============================================================================

class TestPublishCollectionToChannels:
    """Tests for publish_collection_to_channels() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_publish(self, mock_post):
        """Test successful collection publishing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishablePublish": {
                    "publishable": {"id": "gid://shopify/Collection/123"},
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        result = shopify_api.publish_collection_to_channels(
            "gid://shopify/Collection/123",
            sales_channel_ids,
            cfg
        )

        assert result is True

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_publish_both_channels(self, mock_post):
        """Test successful collection publishing to both channels."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishablePublish": {
                    "publishable": {"id": "gid://shopify/Collection/123"},
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {
            "online_store": "gid://shopify/Publication/1",
            "point_of_sale": "gid://shopify/Publication/2"
        }

        result = shopify_api.publish_collection_to_channels(
            "gid://shopify/Collection/123",
            sales_channel_ids,
            cfg
        )

        assert result is True

    @patch('uploader_modules.shopify_api.requests.post')
    def test_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishablePublish": {
                    "userErrors": [{"message": "Invalid collection"}]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_collection_to_channels(
                "gid://shopify/Collection/123",
                {"online_store": "gid://shopify/Publication/1"},
                cfg
            )

        assert result is False

    def test_missing_credentials(self, caplog):
        """Test handling of missing Shopify credentials."""
        cfg = {
            "SHOPIFY_STORE_URL": "",
            "SHOPIFY_ACCESS_TOKEN": ""
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_collection_to_channels(
                "gid://shopify/Collection/123",
                {"online_store": "gid://shopify/Publication/1"},
                cfg
            )

        assert result is False
        assert "Shopify credentials not configured" in caplog.text

    def test_no_sales_channels_configured(self, caplog):
        """Test handling when no sales channels are configured."""
        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.WARNING):
            result = shopify_api.publish_collection_to_channels(
                "gid://shopify/Collection/123",
                {},  # Empty sales channels
                cfg
            )

        assert result is False
        assert "No sales channels configured" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_graphql_top_level_errors(self, mock_post, caplog):
        """Test handling of top-level GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Internal server error"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_collection_to_channels(
                "gid://shopify/Collection/123",
                {"online_store": "gid://shopify/Publication/1"},
                cfg
            )

        assert result is False
        assert "GraphQL errors publishing collection" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_collection_to_channels(
                "gid://shopify/Collection/123",
                {"online_store": "gid://shopify/Publication/1"},
                cfg
            )

        assert result is False
        assert "Network error publishing collection" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_generic_exception(self, mock_post, caplog):
        """Test handling of unexpected exceptions."""
        mock_post.side_effect = ValueError("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_collection_to_channels(
                "gid://shopify/Collection/123",
                {"online_store": "gid://shopify/Publication/1"},
                cfg
            )

        assert result is False
        assert "Unexpected error publishing collection" in caplog.text


# ============================================================================
# PRODUCT DELETION TESTS
# ============================================================================

class TestDeleteShopifyProduct:
    """Tests for delete_shopify_product() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_deletion(self, mock_post):
        """Test successful product deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "productDelete": {
                    "deletedProductId": "gid://shopify/Product/123",
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.delete_shopify_product("gid://shopify/Product/123", cfg)
        assert result is True

    def test_delete_missing_credentials(self, caplog):
        """Test deletion with missing credentials."""
        cfg = {
            "SHOPIFY_STORE_URL": "",
            "SHOPIFY_ACCESS_TOKEN": ""
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.delete_shopify_product("gid://shopify/Product/123", cfg)

        assert result is False
        assert "Shopify credentials not configured for deletion" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_delete_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors during deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "GraphQL error"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.delete_shopify_product("gid://shopify/Product/123", cfg)

        assert result is False
        assert "GraphQL errors deleting product" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_delete_user_errors(self, mock_post, caplog):
        """Test handling of user errors during deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "productDelete": {
                    "userErrors": [{"field": "id", "message": "Product is invalid"}]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.delete_shopify_product("gid://shopify/Product/123", cfg)

        assert result is False
        assert "Product deletion errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_delete_product_not_found_is_success(self, mock_post, caplog):
        """Test that 'product not found' error is treated as success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "productDelete": {
                    "userErrors": [{"message": "Product does not exist"}]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.INFO):
            result = shopify_api.delete_shopify_product("gid://shopify/Product/123", cfg)

        assert result is True  # Should be success since product is already gone
        assert "Product already deleted" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_delete_no_deleted_id_returned(self, mock_post, caplog):
        """Test handling when no deleted product ID is returned."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "productDelete": {
                    "deletedProductId": None,
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.delete_shopify_product("gid://shopify/Product/123", cfg)

        assert result is False
        assert "No deleted product ID returned" in caplog.text


# ============================================================================
# COLLECTION SEARCH TESTS
# ============================================================================

class TestSearchCollection:
    """Tests for search_collection() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_collection_found(self, mock_post):
        """Test finding an existing collection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "collections": {
                    "edges": [
                        {"node": {"id": "gid://shopify/Collection/123", "handle": "test-collection", "title": "Test Collection"}}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.search_collection("Test Collection", cfg)
        assert result is not None
        assert result["id"] == "gid://shopify/Collection/123"
        assert result["handle"] == "test-collection"

    @patch('uploader_modules.shopify_api.requests.post')
    def test_collection_not_found(self, mock_post):
        """Test when collection is not found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "collections": {
                    "edges": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.search_collection("Nonexistent Collection", cfg)
        assert result is None

    def test_search_collection_missing_credentials(self, caplog):
        """Test collection search with missing credentials."""
        cfg = {
            "SHOPIFY_STORE_URL": "",
            "SHOPIFY_ACCESS_TOKEN": ""
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_collection("Test", cfg)

        assert result is None
        assert "Shopify credentials not configured for collection search" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_search_collection_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors when searching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "GraphQL error"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_collection("Test", cfg)

        assert result is None
        assert "GraphQL errors searching collection" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_search_collection_network_error(self, mock_post, caplog):
        """Test handling of network errors when searching."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_collection("Test", cfg)

        assert result is None
        assert "Network error searching collection" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_search_collection_generic_exception(self, mock_post, caplog):
        """Test handling of unexpected exceptions when searching."""
        mock_post.side_effect = ValueError("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_collection("Test", cfg)

        assert result is None
        assert "Unexpected error searching collection" in caplog.text


# ============================================================================
# COLLECTION CREATION TESTS
# ============================================================================

class TestCreateCollection:
    """Tests for create_collection() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_creation(self, mock_post):
        """Test successful collection creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "collectionCreate": {
                    "collection": {
                        "id": "gid://shopify/Collection/456",
                        "title": "New Collection"
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        rules = [{"column": "TAG", "relation": "EQUALS", "condition": "test"}]
        result = shopify_api.create_collection("New Collection", rules, cfg)

        assert result is not None
        assert result["id"] == "gid://shopify/Collection/456"

    def test_create_collection_missing_credentials(self, caplog):
        """Test collection creation with missing credentials."""
        cfg = {
            "SHOPIFY_STORE_URL": "",
            "SHOPIFY_ACCESS_TOKEN": ""
        }

        rules = [{"column": "TAG", "relation": "EQUALS", "condition": "test"}]

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_collection("Test", rules, cfg)

        assert result is None
        assert "Shopify credentials not configured for collection creation" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_create_collection_with_description(self, mock_post):
        """Test collection creation with description."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "collectionCreate": {
                    "collection": {
                        "id": "gid://shopify/Collection/789",
                        "title": "Test Collection"
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        rules = [{"column": "TAG", "relation": "EQUALS", "condition": "test"}]
        result = shopify_api.create_collection("Test Collection", rules, cfg, description="This is a test collection")

        assert result is not None
        # Verify description was passed in the API call
        call_kwargs = mock_post.call_args[1]
        assert "descriptionHtml" in call_kwargs["json"]["variables"]["input"]

    @patch('uploader_modules.shopify_api.requests.post')
    def test_create_collection_no_data_returned(self, mock_post, caplog):
        """Test handling when no collection data is returned."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "collectionCreate": {
                    "collection": None,
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        rules = [{"column": "TAG", "relation": "EQUALS", "condition": "test"}]

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_collection("Test", rules, cfg)

        assert result is None
        assert "No collection data returned" in caplog.text


# ============================================================================
# PRODUCT PUBLISHING TESTS
# ============================================================================

class TestPublishProductToChannels:
    """Tests for publish_product_to_channels() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_publish_to_online_store(self, mock_post):
        """Test successful product publishing to online store."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishablePublish": {
                    "publishable": {
                        "availablePublicationsCount": {"count": 1}
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        result = shopify_api.publish_product_to_channels(
            "gid://shopify/Product/123",
            sales_channel_ids,
            cfg
        )

        assert result is True

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_publish_to_both_channels(self, mock_post):
        """Test successful product publishing to both channels."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishablePublish": {
                    "publishable": {
                        "availablePublicationsCount": {"count": 2}
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {
            "online_store": "gid://shopify/Publication/1",
            "point_of_sale": "gid://shopify/Publication/2"
        }

        result = shopify_api.publish_product_to_channels(
            "gid://shopify/Product/123",
            sales_channel_ids,
            cfg
        )

        assert result is True

    def test_publish_product_missing_credentials(self, caplog):
        """Test that missing credentials returns False."""
        cfg = {}
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_product_to_channels(
                "gid://shopify/Product/123",
                sales_channel_ids,
                cfg
            )

        assert result is False
        assert "Shopify credentials not configured" in caplog.text

    def test_publish_product_no_channels(self, caplog):
        """Test that empty sales channels returns False."""
        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {}

        with caplog.at_level(logging.WARNING):
            result = shopify_api.publish_product_to_channels(
                "gid://shopify/Product/123",
                sales_channel_ids,
                cfg
            )

        assert result is False
        assert "No sales channels to publish to" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_publish_product_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid product ID"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_product_to_channels(
                "gid://shopify/Product/123",
                sales_channel_ids,
                cfg
            )

        assert result is False
        assert "GraphQL errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_publish_product_user_errors(self, mock_post, caplog):
        """Test handling of user errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "publishablePublish": {
                    "userErrors": [
                        {"field": "id", "message": "Product not found"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_product_to_channels(
                "gid://shopify/Product/123",
                sales_channel_ids,
                cfg
            )

        assert result is False
        assert "Publishing errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_publish_product_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_product_to_channels(
                "gid://shopify/Product/123",
                sales_channel_ids,
                cfg
            )

        assert result is False
        assert "Network error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_publish_product_unexpected_error(self, mock_post, caplog):
        """Test handling of unexpected errors."""
        mock_post.side_effect = Exception("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }
        sales_channel_ids = {"online_store": "gid://shopify/Publication/1"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.publish_product_to_channels(
                "gid://shopify/Product/123",
                sales_channel_ids,
                cfg
            )

        assert result is False
        assert "Unexpected error" in caplog.text


# ============================================================================
# METAFIELD DEFINITION TESTS
# ============================================================================

class TestCreateMetafieldDefinition:
    """Tests for create_metafield_definition() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_creation(self, mock_post):
        """Test successful metafield definition creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "createdDefinition": {
                        "id": "gid://shopify/MetafieldDefinition/123",
                        "name": "Layout Possibilities",
                        "namespace": "custom",
                        "key": "layout_possibilities"
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        result = shopify_api.create_metafield_definition(
            "custom",
            "layout_possibilities",
            "json",
            "PRODUCT",
            cfg
        )

        assert result is True

    def test_metafield_definition_missing_credentials(self, caplog):
        """Test that missing credentials returns False."""
        cfg = {}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_metafield_definition(
                "custom",
                "test_field",
                "single_line_text_field",
                "PRODUCT",
                cfg
            )

        assert result is False
        assert "Shopify credentials not configured" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_definition_already_exists(self, mock_post, caplog):
        """Test handling when metafield definition already exists."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": [
                        {"code": "TAKEN", "message": "Key has already been taken"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.INFO):
            result = shopify_api.create_metafield_definition(
                "custom",
                "existing_field",
                "single_line_text_field",
                "PRODUCT",
                cfg
            )

        # Should return True because "already exists" is not an error
        assert result is True
        assert "already exists" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_definition_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_metafield_definition(
                "custom",
                "test_field",
                "single_line_text_field",
                "PRODUCT",
                cfg
            )

        assert result is False
        assert "GraphQL errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_definition_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_metafield_definition(
                "custom",
                "test_field",
                "single_line_text_field",
                "PRODUCT",
                cfg
            )

        assert result is False
        assert "Network error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_graphql_errors_with_status_fn(self, mock_post):
        """Test GraphQL errors with status_fn to cover status_fn branch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is False
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_already_exists_with_status_fn(self, mock_post):
        """Test already exists case with status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": [
                        {"code": "TAKEN", "message": "Key has already been taken"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "existing_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is True
        # Verify status_fn was called
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_user_error_with_status_fn(self, mock_post):
        """Test user errors (non-TAKEN) with status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": [
                        {"code": "INVALID", "message": "Invalid field type"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "invalid_type",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is False
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_user_error_without_status_fn(self, mock_post, caplog):
        """Test user errors (non-TAKEN) without status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": [
                        {"code": "INVALID", "message": "Invalid field type"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_metafield_definition(
                "custom",
                "test_field",
                "invalid_type",
                "PRODUCT",
                cfg
            )

        assert result is False
        assert "Error creating metafield definition" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_success_with_status_fn(self, mock_post):
        """Test successful creation with status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "createdDefinition": {
                        "id": "gid://shopify/MetafieldDefinition/123",
                        "name": "Test Field",
                        "namespace": "custom",
                        "key": "test_field"
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is True
        # Verify status_fn was called
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_no_data_returned_with_status_fn(self, mock_post):
        """Test no data returned with status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is False
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_no_data_returned_without_status_fn(self, mock_post, caplog):
        """Test no data returned without status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_metafield_definition(
                "custom",
                "test_field",
                "single_line_text_field",
                "PRODUCT",
                cfg
            )

        assert result is False
        assert "No metafield definition data returned" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_network_error_with_status_fn(self, mock_post):
        """Test network error with status_fn."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is False
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_generic_exception_with_status_fn(self, mock_post):
        """Test generic exception with status_fn."""
        mock_post.side_effect = RuntimeError("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()
        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is False
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_generic_exception_without_status_fn(self, mock_post, caplog):
        """Test generic exception without status_fn."""
        mock_post.side_effect = RuntimeError("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_metafield_definition(
                "custom",
                "test_field",
                "single_line_text_field",
                "PRODUCT",
                cfg
            )

        assert result is False
        assert "Unexpected error" in caplog.text


# ============================================================================
# TAXONOMY SEARCH TESTS
# ============================================================================

class TestSearchShopifyTaxonomy:
    """Tests for search_shopify_taxonomy() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_successful_exact_match(self, mock_post):
        """Test successful taxonomy search with exact match."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/sg-1-2-3",
                                    "fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Food",
                                    "name": "Dog Food"
                                },
                                "cursor": "cursor1"
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "cursor1"
                        }
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = shopify_api.search_shopify_taxonomy("Dog Food", api_url, headers)

        assert result == "gid://shopify/TaxonomyCategory/sg-1-2-3"

    @patch('uploader_modules.shopify_api.requests.post')
    def test_no_match_found(self, mock_post, caplog):
        """Test when no taxonomy match is found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/sg-1-2-3",
                                    "fullName": "Animals & Pet Supplies > Pet Supplies",
                                    "name": "Pet Supplies"
                                },
                                "cursor": "cursor1"
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "cursor1"
                        }
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result = shopify_api.search_shopify_taxonomy("ZZZZZ12345ABCDE", api_url, headers)

        assert result is None
        assert "No taxonomy match found" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_shopify_taxonomy("Test", api_url, headers)

        assert result is None
        assert "GraphQL errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_shopify_taxonomy("Test", api_url, headers)

        assert result is None
        assert "Network error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_pagination_multiple_pages(self, mock_post):
        """Test taxonomy search with multiple pages of results."""
        # First page
        mock_response_page1 = Mock()
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/1",
                                    "fullName": "Category 1",
                                    "name": "Cat1"
                                },
                                "cursor": "cursor1"
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "cursor1"
                        }
                    }
                }
            }
        }

        # Second page with match
        mock_response_page2 = Mock()
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/sg-target",
                                    "fullName": "Target Category",
                                    "name": "Target"
                                },
                                "cursor": "cursor2"
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "cursor2"
                        }
                    }
                }
            }
        }

        mock_post.side_effect = [mock_response_page1, mock_response_page2]

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = shopify_api.search_shopify_taxonomy("Target", api_url, headers)

        assert result == "gid://shopify/TaxonomyCategory/sg-target"
        # Verify pagination was used
        assert mock_post.call_count == 2


# ============================================================================
# GET TAXONOMY ID TESTS
# ============================================================================

class TestGetTaxonomyId:
    """Tests for get_taxonomy_id() function."""

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_cached_taxonomy_id(self, mock_save_cache, mock_search, caplog):
        """Test that cached taxonomy ID is returned."""
        taxonomy_cache = {"Dog Food": "gid://shopify/TaxonomyCategory/cached"}
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result_id, updated_cache = shopify_api.get_taxonomy_id(
                "Dog Food",
                taxonomy_cache,
                api_url,
                headers
            )

        assert result_id == "gid://shopify/TaxonomyCategory/cached"
        assert updated_cache == taxonomy_cache
        assert "Using cached" in caplog.text
        # Should not call search
        mock_search.assert_not_called()

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_taxonomy_id_not_cached_successful_search(self, mock_save_cache, mock_search, caplog):
        """Test successful taxonomy lookup when not cached."""
        mock_search.return_value = "gid://shopify/TaxonomyCategory/found"
        taxonomy_cache = {}
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result_id, updated_cache = shopify_api.get_taxonomy_id(
                "Dog Food",
                taxonomy_cache,
                api_url,
                headers
            )

        assert result_id == "gid://shopify/TaxonomyCategory/found"
        assert updated_cache["Dog Food"] == "gid://shopify/TaxonomyCategory/found"
        assert "Cached taxonomy mapping" in caplog.text
        mock_save_cache.assert_called_once()

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_hierarchical_category_fallback(self, mock_save_cache, mock_search, caplog):
        """Test hierarchical fallback when full name not found."""
        # First call (full name) returns None, second call (part) returns ID
        mock_search.side_effect = [None, "gid://shopify/TaxonomyCategory/part"]
        taxonomy_cache = {}
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result_id, updated_cache = shopify_api.get_taxonomy_id(
                "Pet Supplies > Dog Food",
                taxonomy_cache,
                api_url,
                headers
            )

        assert result_id == "gid://shopify/TaxonomyCategory/part"
        assert "Trying hierarchical parts" in caplog.text
        # Should try full name first, then parts
        assert mock_search.call_count >= 2

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_last_word_fallback(self, mock_save_cache, mock_search, caplog):
        """Test last word fallback when category not found."""
        # First call (full name) returns None, second call (last word) returns ID
        mock_search.side_effect = [None, "gid://shopify/TaxonomyCategory/last"]
        taxonomy_cache = {}
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result_id, updated_cache = shopify_api.get_taxonomy_id(
                "Premium Dog Food",
                taxonomy_cache,
                api_url,
                headers
            )

        assert result_id == "gid://shopify/TaxonomyCategory/last"
        assert "Trying last word" in caplog.text

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_no_match_caches_none(self, mock_save_cache, mock_search, caplog):
        """Test that failed lookups are cached as None."""
        mock_search.return_value = None
        taxonomy_cache = {}
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.WARNING):
            result_id, updated_cache = shopify_api.get_taxonomy_id(
                "Nonexistent Category",
                taxonomy_cache,
                api_url,
                headers
            )

        assert result_id is None
        assert updated_cache["Nonexistent Category"] is None
        assert "No taxonomy match" in caplog.text
        mock_save_cache.assert_called_once()

    def test_empty_category_name(self):
        """Test that empty category name returns None."""
        taxonomy_cache = {}
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result_id, updated_cache = shopify_api.get_taxonomy_id(
            "",
            taxonomy_cache,
            api_url,
            headers
        )

        assert result_id is None
        assert updated_cache == taxonomy_cache


# ============================================================================
# 3D MODEL UPLOAD TESTS
# ============================================================================

class TestUploadModelToShopify:
    """Tests for upload_model_to_shopify() function."""

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_successful_glb_upload(self, mock_get, mock_post):
        """Test successful GLB model upload."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_glb_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload creation
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": "https://storage.example.com/upload",
                            "resourceUrl": "https://cdn.shopify.com/model.glb",
                            "parameters": [
                                {"name": "key", "value": "123abc"},
                                {"name": "policy", "value": "xyz"}
                            ]
                        }
                    ],
                    "userErrors": []
                }
            }
        }

        # Mock file upload to staged URL
        mock_upload_response = Mock()
        mock_upload_response.status_code = 200

        mock_post.side_effect = [mock_staged_response, mock_upload_response]

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg
        )

        assert cdn_url == "https://cdn.shopify.com/model.glb"
        assert file_id is None  # API 2025-10 doesn't return file_id
        # Verify all HTTP calls were made
        assert mock_get.call_count == 1
        assert mock_post.call_count == 2

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_successful_usdz_upload(self, mock_get, mock_post):
        """Test successful USDZ model upload."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_usdz_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload creation
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": "https://storage.example.com/upload",
                            "resourceUrl": "https://cdn.shopify.com/model.usdz",
                            "parameters": []
                        }
                    ],
                    "userErrors": []
                }
            }
        }

        # Mock file upload
        mock_upload_response = Mock()
        mock_upload_response.status_code = 200
        mock_post.side_effect = [mock_staged_response, mock_upload_response]

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.usdz",
            "model.usdz",
            cfg
        )

        assert cdn_url == "https://cdn.shopify.com/model.usdz"

    def test_upload_model_missing_credentials(self, caplog):
        """Test that missing credentials returns None, None."""
        cfg = {}

        with caplog.at_level(logging.ERROR):
            cdn_url, file_id = shopify_api.upload_model_to_shopify(
                "https://example.com/model.glb",
                "model.glb",
                cfg
            )

        assert cdn_url is None
        assert file_id is None
        assert "Shopify credentials not configured" in caplog.text

    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_download_error(self, mock_get, caplog):
        """Test handling of model download errors."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Download failed")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            cdn_url, file_id = shopify_api.upload_model_to_shopify(
                "https://example.com/model.glb",
                "model.glb",
                cfg
            )

        assert cdn_url is None
        assert file_id is None
        assert "Network error uploading model" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_staged_upload_graphql_errors(self, mock_get, mock_post, caplog):
        """Test handling of GraphQL errors during staged upload creation."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload with errors
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "errors": [{"message": "Invalid input"}]
        }
        mock_post.return_value = mock_staged_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            cdn_url, file_id = shopify_api.upload_model_to_shopify(
                "https://example.com/model.glb",
                "model.glb",
                cfg
            )

        assert cdn_url is None
        assert file_id is None
        assert "Failed to create staged upload" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_staged_upload_user_errors(self, mock_get, mock_post, caplog):
        """Test handling of user errors during staged upload creation."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload with user errors
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "userErrors": [
                        {"field": "mimeType", "message": "Invalid MIME type"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_staged_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            cdn_url, file_id = shopify_api.upload_model_to_shopify(
                "https://example.com/model.glb",
                "model.glb",
                cfg
            )

        assert cdn_url is None
        assert file_id is None

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_no_staged_target(self, mock_get, mock_post, caplog):
        """Test handling when no staged target is returned."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload with no targets (empty list causes IndexError)
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [],
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_staged_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            cdn_url, file_id = shopify_api.upload_model_to_shopify(
                "https://example.com/model.glb",
                "model.glb",
                cfg
            )

        assert cdn_url is None
        assert file_id is None
        # Empty list causes IndexError which goes to generic exception handler
        assert "Unexpected error uploading model" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_file_upload_error(self, mock_get, mock_post, caplog):
        """Test handling of file upload errors to staged URL."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock successful staged upload creation
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": "https://storage.example.com/upload",
                            "resourceUrl": "https://cdn.shopify.com/model.glb",
                            "parameters": []
                        }
                    ],
                    "userErrors": []
                }
            }
        }

        # Mock failed file upload
        import requests
        mock_post.side_effect = [
            mock_staged_response,
            requests.exceptions.ConnectionError("Upload failed")
        ]

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            cdn_url, file_id = shopify_api.upload_model_to_shopify(
                "https://example.com/model.glb",
                "model.glb",
                cfg
            )

        assert cdn_url is None
        assert file_id is None
        assert "Network error uploading model" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_with_status_fn(self, mock_get, mock_post):
        """Test model upload with status function."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload creation
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": "https://storage.example.com/upload",
                            "resourceUrl": "https://cdn.shopify.com/model.glb",
                            "parameters": []
                        }
                    ],
                    "userErrors": []
                }
            }
        }

        # Mock file upload
        mock_upload_response = Mock()
        mock_upload_response.status_code = 200
        mock_post.side_effect = [mock_staged_response, mock_upload_response]

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        # Mock status function
        mock_status_fn = Mock()

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg,
            status_fn=mock_status_fn
        )

        assert cdn_url == "https://cdn.shopify.com/model.glb"
        # Verify status function was called (for status_fn paths)
        assert mock_status_fn.call_count >= 1

    def test_upload_model_missing_credentials_with_status_fn(self):
        """Test missing credentials with status_fn."""
        cfg = {}
        mock_status_fn = Mock()

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg,
            status_fn=mock_status_fn
        )

        assert cdn_url is None
        assert file_id is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_network_error_with_status_fn(self, mock_get):
        """Test network error with status_fn."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Download failed")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg,
            status_fn=mock_status_fn
        )

        assert cdn_url is None
        assert file_id is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_generic_exception_with_status_fn(self, mock_get):
        """Test generic exception with status_fn."""
        mock_get.side_effect = RuntimeError("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg,
            status_fn=mock_status_fn
        )

        assert cdn_url is None
        assert file_id is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_staged_upload_errors_with_status_fn(self, mock_get, mock_post):
        """Test staged upload GraphQL errors with status_fn."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload with errors
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "errors": [{"message": "Invalid input"}]
        }
        mock_post.return_value = mock_staged_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg,
            status_fn=mock_status_fn
        )

        assert cdn_url is None
        assert file_id is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    @patch('uploader_modules.shopify_api.requests.get')
    def test_upload_model_no_staged_target_with_status_fn(self, mock_get, mock_post):
        """Test no staged target returned with status_fn."""
        # Mock model download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake_data"
        mock_get.return_value = mock_get_response

        # Mock staged upload with no targets
        mock_staged_response = Mock()
        mock_staged_response.status_code = 200
        mock_staged_response.json.return_value = {
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [],
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_staged_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()

        cdn_url, file_id = shopify_api.upload_model_to_shopify(
            "https://example.com/model.glb",
            "model.glb",
            cfg,
            status_fn=mock_status_fn
        )

        assert cdn_url is None
        assert file_id is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1


# ============================================================================
# ADDITIONAL ERROR PATH TESTS
# ============================================================================

class TestDeleteShopifyProductErrorPaths:
    """Additional error path tests for delete_shopify_product()."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_delete_product_http_error(self, mock_post, caplog):
        """Test handling of HTTP errors."""
        import requests
        mock_post.side_effect = requests.exceptions.HTTPError("403 Forbidden")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.delete_shopify_product(
                "gid://shopify/Product/123",
                cfg
            )

        assert result is False
        assert "Network error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_delete_product_generic_exception(self, mock_post, caplog):
        """Test handling of generic exceptions."""
        mock_post.side_effect = Exception("Unexpected error")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.delete_shopify_product(
                "gid://shopify/Product/123",
                cfg
            )

        assert result is False
        assert "Unexpected error" in caplog.text


class TestCreateCollectionErrorPaths:
    """Additional error path tests for create_collection()."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_create_collection_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network failed")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_collection(
                "Test Collection",
                [{"column": "TAG", "relation": "EQUALS", "condition": "test"}],
                cfg
            )

        assert result is None
        assert "Network error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_create_collection_generic_exception(self, mock_post, caplog):
        """Test handling of generic exceptions."""
        mock_post.side_effect = Exception("Unexpected")

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_collection(
                "Test Collection",
                [{"column": "TAG", "relation": "EQUALS", "condition": "test"}],
                cfg
            )

        assert result is None
        assert "Unexpected error" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_create_collection_with_user_errors(self, mock_post, caplog):
        """Test handling of user errors in collection creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "collectionCreate": {
                    "collection": None,
                    "userErrors": [
                        {"field": "title", "message": "Title already exists"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_collection(
                "Duplicate Collection",
                [{"column": "TAG", "relation": "EQUALS", "condition": "test"}],
                cfg
            )

        assert result is None
        assert "Collection creation user errors" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_create_collection_graphql_errors(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        with caplog.at_level(logging.ERROR):
            result = shopify_api.create_collection(
                "Test Collection",
                [{"column": "TAG", "relation": "EQUALS", "condition": "test"}],
                cfg
            )

        assert result is None
        assert "GraphQL errors" in caplog.text


class TestMetafieldDefinitionStatusFn:
    """Tests for create_metafield_definition() with status_fn."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_with_status_fn(self, mock_post):
        """Test successful creation with status function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "createdDefinition": {
                        "id": "gid://shopify/MetafieldDefinition/123",
                        "name": "Test Field",
                        "namespace": "custom",
                        "key": "test_field"
                    },
                    "userErrors": []
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()

        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is True
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_metafield_exists_with_status_fn(self, mock_post):
        """Test already exists case with status function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "metafieldDefinitionCreate": {
                    "userErrors": [
                        {"code": "TAKEN", "message": "Already exists"}
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        cfg = {
            "SHOPIFY_STORE_URL": "test-store.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test_token"
        }

        mock_status_fn = Mock()

        result = shopify_api.create_metafield_definition(
            "custom",
            "existing_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is True
        assert mock_status_fn.call_count >= 1

    def test_metafield_missing_credentials_with_status_fn(self):
        """Test missing credentials with status function."""
        cfg = {}
        mock_status_fn = Mock()

        result = shopify_api.create_metafield_definition(
            "custom",
            "test_field",
            "single_line_text_field",
            "PRODUCT",
            cfg,
            status_fn=mock_status_fn
        )

        assert result is False
        assert mock_status_fn.call_count >= 1


class TestTaxonomySearchStatusFn:
    """Tests for search_shopify_taxonomy() with status_fn."""

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_with_status_fn(self, mock_post):
        """Test taxonomy search with status function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/123",
                                    "fullName": "Pet Supplies > Dog Food",
                                    "name": "Dog Food"
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "Dog Food",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result is not None
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_contains_match(self, mock_post):
        """Test taxonomy search with contains match (Strategy 2)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/123",
                                    "fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Food & Treats",
                                    "name": "Dog Food & Treats"
                                },
                                "cursor": "cursor1"
                            },
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/456",
                                    "fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies",
                                    "name": "Dog Supplies"
                                },
                                "cursor": "cursor2"
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        # Search for "Dog" which should match multiple categories, picking shortest
        result = shopify_api.search_shopify_taxonomy(
            "Dog",
            api_url,
            headers
        )

        assert result is not None
        # Should pick the shortest match (Dog Supplies)
        assert result == "gid://shopify/TaxonomyCategory/456"

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_graphql_errors_with_status_fn(self, mock_post):
        """Test GraphQL errors with status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "Test",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_network_error_with_status_fn(self, mock_post):
        """Test network error with status_fn."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "Test",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_no_results_with_status_fn(self, mock_post):
        """Test no results with status_fn."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "Test",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result is None
        # Verify status_fn was called
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_no_results_without_status_fn(self, mock_post, caplog):
        """Test no results without status_fn."""
        import logging

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result = shopify_api.search_shopify_taxonomy(
                "Test",
                api_url,
                headers
            )

        assert result is None
        assert "No taxonomy results" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_exact_match_with_status_fn(self, mock_post):
        """Test exact match with status_fn to cover lines 1029-1030, 1035-1038."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/exact",
                                    "fullName": "Dog Food",
                                    "name": "Dog Food"
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "Dog Food",  # Exact match
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result == "gid://shopify/TaxonomyCategory/exact"
        # Verify status_fn was called with exact match message
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_exact_match_without_status_fn(self, mock_post, caplog):
        """Test exact match without status_fn to cover lines 1037-1038."""
        import logging

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/exact",
                                    "fullName": "Dog Food",
                                    "name": "Dog Food"
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result = shopify_api.search_shopify_taxonomy(
                "Dog Food",  # Exact match
                api_url,
                headers
            )

        assert result == "gid://shopify/TaxonomyCategory/exact"
        assert "Found exact taxonomy match" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_keyword_match_with_separators_and_status_fn(self, mock_post):
        """Test keyword search with separators and status_fn to cover lines 1067-1069, 1088, 1092-1101."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/keyword",
                                    "fullName": "Pet Supplies > Dog Supplies",
                                    "name": "Dog Supplies"
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        # Use category with separator to trigger keyword extraction
        result = shopify_api.search_shopify_taxonomy(
            "Pet > Dog",  # Has " > " separator
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result == "gid://shopify/TaxonomyCategory/keyword"
        # Verify status_fn was called
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_keyword_match_without_status_fn(self, mock_post, caplog):
        """Test keyword match without status_fn to cover lines 1099-1100."""
        import logging

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/keyword",
                                    "fullName": "Pet Supplies > Dog Supplies",
                                    "name": "Dog Supplies"
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result = shopify_api.search_shopify_taxonomy(
                "Pet > Dog",  # Has " > " separator
                api_url,
                headers
            )

        assert result == "gid://shopify/TaxonomyCategory/keyword"
        assert "Found keyword match" in caplog.text

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_no_match_with_status_fn(self, mock_post):
        """Test no match found with status_fn to cover line 1105."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/other",
                                    "fullName": "Completely Different Category",
                                    "name": "Different"
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False}
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "ZZZZZ_NONEXISTENT",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result is None
        # Verify status_fn was called with no match message
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_generic_exception_with_status_fn(self, mock_post):
        """Test generic exception with status_fn to cover lines 1116-1121."""
        mock_post.side_effect = RuntimeError("Unexpected error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        mock_status_fn = Mock()

        result = shopify_api.search_shopify_taxonomy(
            "Test",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert result is None
        # Verify status_fn was called with error
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.requests.post')
    def test_taxonomy_search_generic_exception_without_status_fn(self, mock_post, caplog):
        """Test generic exception without status_fn to cover lines 1119-1120."""
        import logging

        mock_post.side_effect = RuntimeError("Unexpected error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = shopify_api.search_shopify_taxonomy(
                "Test",
                api_url,
                headers
            )

        assert result is None
        assert "Unexpected error" in caplog.text


class TestGetTaxonomyIdStatusFn:
    """Tests for get_taxonomy_id() with status_fn."""

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_get_taxonomy_id_with_status_fn(self, mock_save, mock_search):
        """Test get_taxonomy_id with status function."""
        mock_search.return_value = "gid://shopify/TaxonomyCategory/123"
        mock_status_fn = Mock()

        result_id, cache = shopify_api.get_taxonomy_id(
            "Dog Food",
            {},
            "https://test-store.myshopify.com/admin/api/2025-10/graphql.json",
            {"X-Shopify-Access-Token": "test_token"},
            status_fn=mock_status_fn
        )

        assert result_id is not None
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_get_taxonomy_id_cached_with_status_fn(self, mock_save, mock_search):
        """Test cached taxonomy ID retrieval with status function."""
        cache = {"Dog Food": "gid://shopify/TaxonomyCategory/cached"}
        mock_status_fn = Mock()

        result_id, updated_cache = shopify_api.get_taxonomy_id(
            "Dog Food",
            cache,
            "https://test-store.myshopify.com/admin/api/2025-10/graphql.json",
            {"X-Shopify-Access-Token": "test_token"},
            status_fn=mock_status_fn
        )

        assert result_id == "gid://shopify/TaxonomyCategory/cached"
        assert mock_status_fn.call_count >= 1
        mock_search.assert_not_called()

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_get_taxonomy_id_hierarchical_with_status_fn(self, mock_save, mock_search):
        """Test hierarchical fallback with status function."""
        mock_search.side_effect = [None, "gid://shopify/TaxonomyCategory/456"]
        mock_status_fn = Mock()

        result_id, cache = shopify_api.get_taxonomy_id(
            "Pet Supplies > Dog Food",
            {},
            "https://test-store.myshopify.com/admin/api/2025-10/graphql.json",
            {"X-Shopify-Access-Token": "test_token"},
            status_fn=mock_status_fn
        )

        assert result_id is not None
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.shopify_api.search_shopify_taxonomy')
    @patch('uploader_modules.shopify_api.save_taxonomy_cache')
    def test_get_taxonomy_id_last_word_with_status_fn(self, mock_save, mock_search):
        """Test last word fallback with status function."""
        mock_search.side_effect = [None, "gid://shopify/TaxonomyCategory/789"]
        mock_status_fn = Mock()

        result_id, cache = shopify_api.get_taxonomy_id(
            "Premium Dog Food",
            {},
            "https://test-store.myshopify.com/admin/api/2025-10/graphql.json",
            {"X-Shopify-Access-Token": "test_token"},
            status_fn=mock_status_fn
        )

        assert result_id is not None
        assert mock_status_fn.call_count >= 1

