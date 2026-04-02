"""
Tests for the per-variant inventory quantity feature.

Tests cover:
1. Config reading: USE_INPUT_QUANTITIES flag controls inventory source
2. Inventory quantity building: per-variant quantities from input JSON
3. CLI flag: --use-input-quantities sets config correctly
4. Skipping variants with 0 or missing inventory_quantity
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestInventoryQuantityConfig:
    """Test that USE_INPUT_QUANTITIES config flag is read correctly."""

    def test_use_input_quantities_default_false(self):
        """When USE_INPUT_QUANTITIES is not in config, defaults to False."""
        cfg = {"INVENTORY_QUANTITY": "10"}
        use_input = cfg.get("USE_INPUT_QUANTITIES", False)
        assert use_input is False

    def test_use_input_quantities_true(self):
        """When USE_INPUT_QUANTITIES is True, it should be read as True."""
        cfg = {"USE_INPUT_QUANTITIES": True, "INVENTORY_QUANTITY": "10"}
        use_input = cfg.get("USE_INPUT_QUANTITIES", False)
        assert use_input is True

    def test_use_input_quantities_false_explicit(self):
        """When USE_INPUT_QUANTITIES is explicitly False."""
        cfg = {"USE_INPUT_QUANTITIES": False, "INVENTORY_QUANTITY": "10"}
        use_input = cfg.get("USE_INPUT_QUANTITIES", False)
        assert use_input is False


class TestBuildInventoryQuantitiesFromInput:
    """Test building per-variant inventory quantities from input JSON."""

    def _build_inventory_quantities(self, created_variants, input_variants, use_input_quantities, global_quantity, location_id):
        """
        Helper that mirrors the logic we will implement in product_processing.py.
        Builds the inventory_quantities_input list.
        """
        from uploader_modules.product_processing import build_inventory_quantities
        return build_inventory_quantities(
            created_variants=created_variants,
            input_variants=input_variants,
            use_input_quantities=use_input_quantities,
            global_quantity=global_quantity,
            location_id=location_id,
        )

    def test_global_quantity_mode(self):
        """When use_input_quantities=False, all variants get the global quantity."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
            {"sku": "SKU-002", "inventoryItem": {"id": "gid://shopify/InventoryItem/2"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 50},
            {"sku": "SKU-002", "inventory_quantity": 25},
        ]
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=False, global_quantity=10, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 2
        assert all(item["quantity"] == 10 for item in result)

    def test_input_quantities_mode(self):
        """When use_input_quantities=True, each variant gets its own quantity from input."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
            {"sku": "SKU-002", "inventoryItem": {"id": "gid://shopify/InventoryItem/2"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 50},
            {"sku": "SKU-002", "inventory_quantity": 25},
        ]
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=True, global_quantity=None, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 2
        # Find each by inventoryItemId
        qty_by_id = {item["inventoryItemId"]: item["quantity"] for item in result}
        assert qty_by_id["gid://shopify/InventoryItem/1"] == 50
        assert qty_by_id["gid://shopify/InventoryItem/2"] == 25

    def test_input_quantities_skip_zero(self):
        """Variants with inventory_quantity=0 should be skipped in input mode."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
            {"sku": "SKU-002", "inventoryItem": {"id": "gid://shopify/InventoryItem/2"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 50},
            {"sku": "SKU-002", "inventory_quantity": 0},
        ]
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=True, global_quantity=None, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 1
        assert result[0]["inventoryItemId"] == "gid://shopify/InventoryItem/1"
        assert result[0]["quantity"] == 50

    def test_input_quantities_skip_missing(self):
        """Variants missing inventory_quantity should be skipped in input mode."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
            {"sku": "SKU-002", "inventoryItem": {"id": "gid://shopify/InventoryItem/2"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 50},
            {"sku": "SKU-002"},  # no inventory_quantity key
        ]
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=True, global_quantity=None, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 1
        assert result[0]["quantity"] == 50

    def test_input_quantities_no_matching_sku(self):
        """Variants in Shopify with no matching input SKU get skipped."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
            {"sku": "SKU-UNKNOWN", "inventoryItem": {"id": "gid://shopify/InventoryItem/2"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 50},
        ]
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=True, global_quantity=None, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 1
        assert result[0]["quantity"] == 50

    def test_input_quantities_empty_returns_empty(self):
        """When all input quantities are 0 or missing, returns empty list."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 0},
        ]
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=True, global_quantity=None, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 0

    def test_global_quantity_skips_missing_inventory_item_id(self):
        """Variants without inventoryItem.id should be skipped in global mode too."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
            {"sku": "SKU-002", "inventoryItem": {}},  # no id
            {"sku": "SKU-003"},  # no inventoryItem at all
        ]
        input_variants = []
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=False, global_quantity=10, location_id="gid://shopify/Location/1"
        )
        assert len(result) == 1
        assert result[0]["quantity"] == 10

    def test_location_id_set_correctly(self):
        """All entries should have the correct locationId."""
        created_variants = [
            {"sku": "SKU-001", "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}},
        ]
        input_variants = [
            {"sku": "SKU-001", "inventory_quantity": 50},
        ]
        location = "gid://shopify/Location/99"
        result = self._build_inventory_quantities(
            created_variants, input_variants,
            use_input_quantities=True, global_quantity=None, location_id=location
        )
        assert result[0]["locationId"] == location


class TestCLIFlag:
    """Test that --use-input-quantities CLI flag works."""

    def test_cli_flag_sets_config(self):
        """The --use-input-quantities flag should set USE_INPUT_QUANTITIES in config."""
        from uploader_modules.cli_utils import apply_cli_overrides
        cfg = {}
        args = MagicMock()
        args.use_input_quantities = True
        apply_cli_overrides(cfg, args)
        assert cfg["USE_INPUT_QUANTITIES"] is True

    def test_cli_flag_default_false(self):
        """Without the flag, USE_INPUT_QUANTITIES should not be set."""
        from uploader_modules.cli_utils import apply_cli_overrides
        cfg = {}
        args = MagicMock()
        args.use_input_quantities = False
        apply_cli_overrides(cfg, args)
        assert cfg.get("USE_INPUT_QUANTITIES", False) is False
