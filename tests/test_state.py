"""
Tests for uploader_modules/state.py

Tests state file management including upload state, collections, products,
and taxonomy caching.
"""

import pytest
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules import state


# ============================================================================
# UPLOAD STATE TESTS
# ============================================================================

class TestUploadState:
    """Tests for upload state management (upload_state.json)."""

    def test_load_state_nonexistent(self, mock_state_files):
        """Test loading state when file doesn't exist returns empty dict."""
        result = state.load_state()
        assert result == {}

    def test_save_and_load_state(self, mock_state_files):
        """Test saving and loading state."""
        test_state = {
            "last_processed_index": 5,
            "results": [{"title": "Product 1", "status": "completed"}]
        }
        state.save_state(test_state)
        loaded_state = state.load_state()
        assert loaded_state["last_processed_index"] == 5
        assert len(loaded_state["results"]) == 1

    def test_save_state_with_complex_data(self, mock_state_files):
        """Test saving state with nested complex data."""
        test_state = {
            "last_processed_index": 10,
            "results": [
                {
                    "title": "Product 1",
                    "status": "completed",
                    "shopify_id": "gid://shopify/Product/123",
                    "variants_created": True
                },
                {
                    "title": "Product 2",
                    "status": "failed",
                    "error": "API timeout"
                }
            ],
            "timestamp": datetime.now().isoformat()
        }
        state.save_state(test_state)
        loaded_state = state.load_state()
        assert loaded_state["last_processed_index"] == 10
        assert len(loaded_state["results"]) == 2

    def test_load_state_corrupted_json(self, mock_state_files, monkeypatch):
        """Test loading state with corrupted JSON returns empty dict."""
        # Write corrupted JSON
        state_file = Path(state.STATE_FILE)
        state_file.write_text("{ invalid json }")

        result = state.load_state()
        assert result == {}


# ============================================================================
# COLLECTIONS STATE TESTS
# ============================================================================

class TestCollectionsState:
    """Tests for collections tracking (collections.json)."""

    def test_load_collections_nonexistent(self, mock_state_files):
        """Test loading collections when file doesn't exist."""
        result = state.load_collections()
        assert "collections" in result
        assert "last_updated" in result
        assert isinstance(result["collections"], list)

    def test_save_and_load_collections(self, mock_state_files):
        """Test saving and loading collections data."""
        test_collections = {
            "collections": [
                {
                    "title": "Landscape and Construction",
                    "id": "gid://shopify/Collection/123",
                    "handle": "landscape-and-construction"
                },
                {
                    "title": "Pet Supplies",
                    "id": "gid://shopify/Collection/456",
                    "handle": "pet-supplies"
                }
            ],
            "last_updated": datetime.now().isoformat()
        }
        state.save_collections(test_collections)
        loaded_collections = state.load_collections()
        assert len(loaded_collections["collections"]) == 2
        assert loaded_collections["collections"][0]["title"] == "Landscape and Construction"

    def test_save_collections_updates_timestamp(self, mock_state_files):
        """Test that saving collections updates timestamp."""
        test_collections = {"collections": []}
        state.save_collections(test_collections)
        loaded = state.load_collections()
        assert "last_updated" in loaded


# ============================================================================
# PRODUCTS STATE TESTS
# ============================================================================

class TestProductsState:
    """Tests for products restore points (products.json)."""

    def test_load_products_nonexistent(self, mock_state_files):
        """Test loading products when file doesn't exist."""
        result = state.load_products()
        assert "products" in result
        assert "products_dict" in result
        assert "last_updated" in result
        assert isinstance(result["products"], list)
        assert isinstance(result["products_dict"], dict)

    def test_save_and_load_products(self, mock_state_files, sample_products):
        """Test saving and loading products data."""
        test_products = {
            "products": sample_products,
            "last_updated": datetime.now().isoformat()
        }
        state.save_products(test_products)
        loaded_products = state.load_products()
        assert len(loaded_products["products"]) == len(sample_products)

    def test_load_products_builds_dict(self, mock_state_files, sample_products):
        """Test that loading products builds a lookup dictionary."""
        test_products = {
            "products": sample_products
        }
        state.save_products(test_products)
        loaded = state.load_products()

        # Check that dict was built
        assert "products_dict" in loaded
        assert len(loaded["products_dict"]) > 0

        # Check that dict keys are lowercase titles
        first_product_title = sample_products[0]["title"].strip().lower()
        assert first_product_title in loaded["products_dict"]

    def test_update_product_in_restore_new_product(self, mock_state_files):
        """Test adding a new product to restore data."""
        products_restore = {
            "products": [],
            "products_dict": {}
        }

        new_product = {
            "title": "New Product",
            "shopify_id": "gid://shopify/Product/789",
            "status": "completed"
        }

        updated = state.update_product_in_restore(products_restore, new_product)
        assert len(updated["products"]) == 1
        assert "new product" in updated["products_dict"]

    def test_update_product_in_restore_existing_product(self, mock_state_files):
        """Test updating an existing product in restore data."""
        existing_product = {
            "title": "Existing Product",
            "shopify_id": "gid://shopify/Product/123",
            "status": "pending"
        }

        products_restore = {
            "products": [existing_product],
            "products_dict": {"existing product": existing_product}
        }

        updated_product = {
            "title": "Existing Product",
            "shopify_id": "gid://shopify/Product/123",
            "status": "completed"
        }

        updated = state.update_product_in_restore(products_restore, updated_product)
        assert len(updated["products"]) == 1  # Still only 1 product
        assert updated["products"][0]["status"] == "completed"  # Status updated

    def test_update_product_no_title(self, mock_state_files):
        """Test updating product without title returns unchanged data."""
        products_restore = {"products": [], "products_dict": {}}
        product_no_title = {"shopify_id": "gid://shopify/Product/123"}

        updated = state.update_product_in_restore(products_restore, product_no_title)
        assert len(updated["products"]) == 0


# ============================================================================
# TAXONOMY CACHE TESTS
# ============================================================================

class TestTaxonomyCache:
    """Tests for taxonomy caching (product_taxonomy.json)."""

    def test_load_taxonomy_cache_nonexistent(self, mock_state_files):
        """Test loading taxonomy cache when file doesn't exist."""
        result = state.load_taxonomy_cache()
        assert result == {}

    def test_save_and_load_taxonomy_cache(self, mock_state_files):
        """Test saving and loading taxonomy cache."""
        test_cache = {
            "Pavers and Hardscaping": "gid://shopify/TaxonomyCategory/123",
            "Slabs": "gid://shopify/TaxonomyCategory/456"
        }
        state.save_taxonomy_cache(test_cache)
        loaded_cache = state.load_taxonomy_cache()
        assert loaded_cache["Pavers and Hardscaping"] == "gid://shopify/TaxonomyCategory/123"
        assert len(loaded_cache) == 2

    def test_taxonomy_cache_prevents_redundant_lookups(self, mock_state_files):
        """Test that taxonomy cache can be used to avoid API calls."""
        # First save a cache
        initial_cache = {
            "Test Category": "gid://shopify/TaxonomyCategory/789"
        }
        state.save_taxonomy_cache(initial_cache)

        # Load it back
        loaded = state.load_taxonomy_cache()

        # Verify we can check if category exists without API call
        assert "Test Category" in loaded
        assert loaded["Test Category"] == "gid://shopify/TaxonomyCategory/789"


# ============================================================================
# STATE FILE PERSISTENCE TESTS
# ============================================================================

class TestStateFilePersistence:
    """Tests for state file persistence and JSON formatting."""

    def test_state_files_are_json_formatted(self, mock_state_files):
        """Test that saved state files are properly JSON formatted."""
        test_state = {"test_key": "test_value"}
        state.save_state(test_state)

        # Read the file directly
        with open(state.STATE_FILE, 'r') as f:
            content = f.read()

        # Should be valid JSON
        parsed = json.loads(content)
        assert parsed["test_key"] == "test_value"

    def test_state_files_have_proper_indentation(self, mock_state_files):
        """Test that state files are saved with proper indentation for readability."""
        test_state = {"key1": "value1", "key2": {"nested": "value"}}
        state.save_state(test_state)

        with open(state.STATE_FILE, 'r') as f:
            content = f.read()

        # Should have indentation (not minified)
        assert '\n' in content
        assert '    ' in content or '\t' in content


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestStateErrorHandling:
    """Tests for error handling in state management."""

    def test_load_state_handles_permission_error(self, mock_state_files, monkeypatch):
        """Test that load_state handles permission errors gracefully."""
        def mock_open_error(*args, **kwargs):
            raise PermissionError("No permission")

        monkeypatch.setattr("builtins.open", mock_open_error)
        result = state.load_state()
        assert result == {}

    def test_load_state_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that load_state handles IO errors gracefully."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Disk read error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_state()

        assert result == {}
        assert "Failed to read upload_state.json" in caplog.text

    def test_save_state_logs_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that save_state logs IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Disk full")

        monkeypatch.setattr("builtins.open", mock_open_error)

        test_state = {"test": "data"}
        state.save_state(test_state)

        # Should log error but not crash
        assert "Failed to write" in caplog.text or "error" in caplog.text.lower()

    def test_load_state_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that load_state handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        # Make file exist so open() gets called
        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_state()

        assert result == {}
        assert "Unexpected error loading state" in caplog.text

    def test_save_state_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that save_state handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_state({"test": "data"})

        assert "Unexpected error saving state" in caplog.text

    def test_load_collections_handles_json_decode_error(self, mock_state_files, caplog):
        """Test that load_collections handles corrupted JSON."""
        # Create corrupted JSON
        with open(state.COLLECTIONS_FILE, 'w') as f:
            f.write("{ invalid json }")

        with caplog.at_level(logging.WARNING):
            result = state.load_collections()

        assert "collections" in result
        assert "Failed to parse collections.json" in caplog.text

    def test_load_collections_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that load_collections handles IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Read error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_collections()

        assert "collections" in result
        assert "Failed to read collections.json" in caplog.text

    def test_load_collections_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that load_collections handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_collections()

        assert "collections" in result
        assert "Unexpected error loading collections" in caplog.text

    def test_save_collections_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that save_collections handles IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Write error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_collections({"collections": []})

        assert "Failed to write collections.json" in caplog.text

    def test_save_collections_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that save_collections handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_collections({"collections": []})

        assert "Unexpected error saving collections" in caplog.text

    def test_load_products_handles_json_decode_error(self, mock_state_files, caplog):
        """Test that load_products handles corrupted JSON."""
        # Create corrupted JSON
        with open(state.PRODUCTS_FILE, 'w') as f:
            f.write("{ invalid json }")

        with caplog.at_level(logging.WARNING):
            result = state.load_products()

        assert "products" in result
        assert "Failed to parse products.json" in caplog.text

    def test_load_products_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that load_products handles IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Read error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_products()

        assert "products" in result
        assert "Failed to read products.json" in caplog.text

    def test_load_products_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that load_products handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_products()

        assert "products" in result
        assert "Unexpected error loading products" in caplog.text

    def test_save_products_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that save_products handles IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Write error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_products({"products": []})

        assert "Failed to write products.json" in caplog.text

    def test_save_products_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that save_products handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_products({"products": []})

        assert "Unexpected error saving products" in caplog.text

    def test_load_taxonomy_cache_handles_json_decode_error(self, mock_state_files, caplog):
        """Test that load_taxonomy_cache handles corrupted JSON."""
        # Create corrupted JSON
        with open(state.TAXONOMY_FILE, 'w') as f:
            f.write("{ invalid json }")

        with caplog.at_level(logging.WARNING):
            result = state.load_taxonomy_cache()

        assert result == {}
        assert "Failed to parse taxonomy file" in caplog.text

    def test_load_taxonomy_cache_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that load_taxonomy_cache handles IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Read error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_taxonomy_cache()

        assert result == {}
        assert "Failed to read taxonomy file" in caplog.text

    def test_load_taxonomy_cache_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that load_taxonomy_cache handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("os.path.exists", lambda x: True)
        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.WARNING):
            result = state.load_taxonomy_cache()

        assert result == {}
        assert "Unexpected error loading taxonomy" in caplog.text

    def test_save_taxonomy_cache_handles_io_error(self, mock_state_files, caplog, monkeypatch):
        """Test that save_taxonomy_cache handles IO errors."""
        def mock_open_error(*args, **kwargs):
            raise IOError("Write error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_taxonomy_cache({})

        assert "Failed to write taxonomy file" in caplog.text

    def test_save_taxonomy_cache_handles_generic_exception(self, mock_state_files, caplog, monkeypatch):
        """Test that save_taxonomy_cache handles unexpected exceptions."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            state.save_taxonomy_cache({})

        assert "Unexpected error saving taxonomy" in caplog.text
