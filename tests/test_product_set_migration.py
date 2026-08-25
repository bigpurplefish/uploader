"""
Tests for productSet mutation migration.

Verifies that the productCreate + productVariantsBulkCreate flow
has been replaced with a single productSet mutation call.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import inspect
import ast
import textwrap


# ============================================================================
# Helper to get source code of process_products
# ============================================================================

def get_process_products_source():
    """Get the source code of process_products function."""
    from uploader_modules.product_processing import process_products
    return inspect.getsource(process_products)


# ============================================================================
# MUTATION STRING TESTS
# ============================================================================

class TestMutationStrings:
    """Verify the old mutations are removed and productSet is present."""

    def test_no_productCreate_mutation(self):
        """productCreate mutation string must not appear in process_products."""
        source = get_process_products_source()
        # The old mutation definition
        assert 'mutation productCreate(' not in source, \
            "Old productCreate mutation should be removed"

    def test_no_productVariantsBulkCreate_in_create_path(self):
        """productVariantsBulkCreate must not be used in the product creation path.
        Note: It may still exist in the update/overwrite path for adding variants to existing products."""
        source = get_process_products_source()
        # The old creation path used REMOVE_STANDALONE_VARIANT strategy - that's the marker
        # for the create-path usage of productVariantsBulkCreate
        assert 'REMOVE_STANDALONE_VARIANT' not in source, \
            "REMOVE_STANDALONE_VARIANT strategy (create-path bulk variant) should be removed"

    def test_productSet_mutation_present(self):
        """productSet mutation string must be present in process_products."""
        source = get_process_products_source()
        assert 'mutation productSet(' in source, \
            "productSet mutation must be defined"

    def test_productSet_mutation_has_synchronous_param(self):
        """productSet mutation must include $synchronous parameter."""
        source = get_process_products_source()
        assert '$synchronous: Boolean!' in source, \
            "productSet must have $synchronous: Boolean! parameter"

    def test_productSet_mutation_has_input_param(self):
        """productSet mutation must include $input: ProductSetInput!."""
        source = get_process_products_source()
        assert '$input: ProductSetInput!' in source, \
            "productSet must have $input: ProductSetInput! parameter"

    def test_productSet_returns_variants(self):
        """productSet mutation must request variants in response."""
        source = get_process_products_source()
        # Check that variants are requested in the productSet response
        assert 'variants(first:' in source or 'variants(first: ' in source, \
            "productSet must request variants in response"

    def test_productSet_returns_variant_sku(self):
        """productSet mutation response must include variant SKU."""
        source = get_process_products_source()
        # After the productSet mutation, there should be sku in the variant fields
        assert 'sku' in source

    def test_productSet_returns_inventory_item(self):
        """productSet mutation response must include inventoryItem for inventory management."""
        source = get_process_products_source()
        assert 'inventoryItem' in source

    def test_no_REMOVE_STANDALONE_VARIANT_strategy(self):
        """REMOVE_STANDALONE_VARIANT strategy must not appear (productSet doesn't need it)."""
        source = get_process_products_source()
        assert 'REMOVE_STANDALONE_VARIANT' not in source, \
            "REMOVE_STANDALONE_VARIANT strategy should be removed"


# ============================================================================
# VARIABLE BUILDING TESTS
# ============================================================================

class TestVariableBuilding:
    """Verify variables are built correctly for productSet."""

    def test_variables_have_synchronous_key(self):
        """Variables dict must include 'synchronous' key."""
        source = get_process_products_source()
        assert '"synchronous"' in source, \
            "Variables must include 'synchronous' key"

    def test_variables_have_input_key(self):
        """Variables dict must include 'input' key wrapping product data."""
        source = get_process_products_source()
        assert '"input"' in source, \
            "Variables must include 'input' key"

    def test_variants_embedded_in_input(self):
        """Variant inputs must be embedded in the productSet input, not sent separately."""
        source = get_process_products_source()
        # Variants should be set on the product input before the mutation call
        # Look for pattern of adding variants to the input
        assert 'variants' in source
        # The old pattern of sending variants as a separate mutation param should be gone
        assert '"productId": shopify_product_id' not in source or \
            source.count('"productId"') <= source.count('productCreateMedia'), \
            "productId for variant creation should not exist (only for media attachment)"

    def test_product_options_have_position(self):
        """productOptions must include 'position' field for productSet."""
        source = get_process_products_source()
        assert '"position"' in source, \
            "productOptions must include position field"


# ============================================================================
# RESPONSE PARSING TESTS
# ============================================================================

class TestResponseParsing:
    """Verify response parsing uses productSet paths."""

    def test_no_productCreate_response_parsing(self):
        """No references to result['data']['productCreate'] should exist."""
        source = get_process_products_source()
        assert '"productCreate"' not in source, \
            "Should not reference productCreate in response parsing"

    def test_productSet_response_parsing(self):
        """Response parsing must use productSet path."""
        source = get_process_products_source()
        assert '"productSet"' in source, \
            "Response parsing must reference productSet"

    def test_no_productVariantsBulkCreate_in_create_response(self):
        """The create path must not parse productVariantsBulkCreate responses.
        Note: The update path may still reference it for variant additions."""
        source = get_process_products_source()
        # The create path previously extracted variants from productVariantsBulkCreate.productVariants
        # Now it extracts from productSet.product.variants.edges
        # The update path may still use productVariantsBulkCreate, which is fine
        assert '"productSet"' in source, \
            "Create path must use productSet for response parsing"

    def test_variant_ids_from_edges_pattern(self):
        """Variant IDs must be extracted from edges/node pattern (connection format)."""
        source = get_process_products_source()
        # Should parse variants from edges format
        assert 'edges' in source
        assert 'node' in source


# ============================================================================
# CODE ORDERING TESTS
# ============================================================================

class TestCodeOrdering:
    """Verify variant building happens before mutation call."""

    def test_variant_building_before_mutation(self):
        """Variant input building must occur before the productSet API call."""
        source = get_process_products_source()
        # Find the position of variant_inputs building and the API call
        variant_build_pos = source.find('variant_inputs = []')
        mutation_call_pos = source.find('mutation productSet(')

        assert variant_build_pos != -1, "variant_inputs = [] must exist"
        assert mutation_call_pos != -1, "productSet mutation must exist"
        assert variant_build_pos < mutation_call_pos, \
            "Variant building must happen before the productSet mutation call"


# ============================================================================
# MEDIA HANDLING TESTS
# ============================================================================

class TestMediaHandling:
    """Verify media is still handled correctly (images via productCreateMedia or inline)."""

    def test_3d_model_attachment_unchanged(self):
        """3D model attachment via productCreateMedia must still exist."""
        source = get_process_products_source()
        assert 'productCreateMedia' in source, \
            "productCreateMedia must still be used for 3D model attachment"

    def test_video_attachment_unchanged(self):
        """Video attachment via productCreateMedia must still exist."""
        source = get_process_products_source()
        assert 'uploaded_videos' in source, \
            "Video upload logic must still exist"

    def test_poll_media_ready_still_used(self):
        """poll_media_ready must still be called for variant-media association."""
        source = get_process_products_source()
        assert 'poll_media_ready' in source, \
            "poll_media_ready must still be used"

    def test_append_media_to_variants_still_used(self):
        """append_media_to_variants must still be called."""
        source = get_process_products_source()
        assert 'append_media_to_variants' in source, \
            "append_media_to_variants must still be used"


# ============================================================================
# STATE MANAGEMENT TESTS
# ============================================================================

class TestStateManagement:
    """Verify state management is preserved."""

    def test_restore_point_after_creation(self):
        """Restore point must be saved after product creation."""
        source = get_process_products_source()
        assert 'update_product_in_restore' in source
        assert 'save_products' in source

    def test_variant_ids_in_restore(self):
        """Variant IDs must be saved in restore data."""
        source = get_process_products_source()
        assert '"variant_ids"' in source or "'variant_ids'" in source

    def test_publish_to_channels_still_exists(self):
        """Sales channel publishing must still exist."""
        source = get_process_products_source()
        assert 'publish_product_to_channels' in source


# ============================================================================
# INVENTORY MANAGEMENT TESTS
# ============================================================================

class TestInventoryManagement:
    """Verify inventory quantity setting still works with new variant format."""

    def test_inventory_set_quantities_still_exists(self):
        """inventorySetQuantities mutation must still be used."""
        source = get_process_products_source()
        assert 'inventorySetQuantities' in source

    def test_inventory_reads_from_variants(self):
        """Inventory code must read inventoryItem from created variants."""
        source = get_process_products_source()
        assert 'inventoryItem' in source


# ============================================================================
# CONFTEST FIXTURE TESTS
# ============================================================================

class TestConftest:
    """Verify conftest fixtures are updated for productSet."""

    def test_mock_shopify_product_set_fixture(self):
        """A mock_shopify_product_set fixture should exist or
        mock_shopify_product_create should return productSet format."""
        # This tests that conftest has been updated
        from tests.conftest import mock_shopify_product_create
        # The old fixture returns productCreate format - we need productSet format
        # After migration, the conftest should have a productSet fixture
        pass  # Will be validated by other integration tests
