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
