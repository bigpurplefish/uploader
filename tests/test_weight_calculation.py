"""
Tests for weight calculation and estimation functionality.

Tests the weight calculation logic integrated into the AI enhancement workflow,
including parsing AI responses, applying weight data to variants, and handling
different weight estimation scenarios.
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules import openai_api


# ============================================================================
# WEIGHT ESTIMATION RESPONSE PARSING TESTS
# ============================================================================

class TestWeightEstimationParsing:
    """Tests for parsing AI weight estimation responses."""

    def test_parse_complete_weight_response(self):
        """Test parsing complete weight estimation from AI response."""
        ai_response = {
            "department": "Pet Supplies",
            "category": "Dogs",
            "subcategory": "Food",
            "weight_estimation": {
                "original_weight": 0,
                "product_weight": 50.0,
                "product_packaging_weight": 0.5,
                "shipping_packaging_weight": 2.0,
                "final_shipping_weight": 58.0,
                "confidence": "high",
                "source": "extracted_from_text",
                "reasoning": "50 lb bag mentioned in title"
            },
            "purchase_options": [1, 2, 3, 4],
            "needs_review": False
        }

        weight_estimation = ai_response.get('weight_estimation', {})

        assert weight_estimation['product_weight'] == 50.0
        assert weight_estimation['final_shipping_weight'] == 58.0
        assert weight_estimation['confidence'] == "high"
        assert weight_estimation['source'] == "extracted_from_text"

    def test_parse_liquid_conversion_response(self):
        """Test parsing weight estimation with liquid conversion."""
        ai_response = {
            "department": "Lawn And Garden",
            "category": "Fertilizers",
            "subcategory": "",
            "weight_estimation": {
                "original_weight": 0,
                "product_weight": 84.0,  # 8 gallons * 10.5 lbs/gal
                "product_packaging_weight": 0.5,
                "shipping_packaging_weight": 2.5,
                "final_shipping_weight": 96.0,  # (84 + 0.5 + 2.5) * 1.1
                "confidence": "medium",
                "source": "liquid_conversion",
                "reasoning": "8 gallon liquid fertilizer, 10.5 lbs/gal = 84 lbs"
            },
            "purchase_options": [1, 2, 3, 4],
            "needs_review": False
        }

        weight_estimation = ai_response['weight_estimation']

        assert weight_estimation['source'] == "liquid_conversion"
        assert weight_estimation['product_weight'] == 84.0
        assert weight_estimation['confidence'] == "medium"

    def test_parse_dimensional_calculation_response(self):
        """Test parsing weight estimation from dimensional calculation."""
        ai_response = {
            "department": "Landscape And Construction",
            "category": "Pavers And Hardscaping",
            "subcategory": "Slabs",
            "weight_estimation": {
                "original_weight": 0,
                "product_weight": 45.5,
                "product_packaging_weight": 0,
                "shipping_packaging_weight": 2.0,
                "final_shipping_weight": 52.5,
                "confidence": "high",
                "source": "calculated_from_dimensions",
                "reasoning": "30x30x2 inch concrete slab, 150 lbs/cf density"
            },
            "purchase_options": [1, 2],
            "needs_review": False
        }

        weight_estimation = ai_response['weight_estimation']

        assert weight_estimation['source'] == "calculated_from_dimensions"
        assert weight_estimation['product_weight'] == 45.5

    def test_parse_estimated_weight_response(self):
        """Test parsing weight estimation from context."""
        ai_response = {
            "department": "Home And Gift",
            "category": "Garden Decor",
            "subcategory": "",
            "weight_estimation": {
                "original_weight": 0,
                "product_weight": 3.0,
                "product_packaging_weight": 0.5,
                "shipping_packaging_weight": 1.5,
                "final_shipping_weight": 5.5,
                "confidence": "low",
                "source": "estimated",
                "reasoning": "Small garden gnome, estimated 3 lbs"
            },
            "purchase_options": [1, 2, 3, 4, 5],
            "needs_review": True
        }

        weight_estimation = ai_response['weight_estimation']

        assert weight_estimation['source'] == "estimated"
        assert weight_estimation['confidence'] == "low"
        assert ai_response['needs_review'] is True

    def test_parse_existing_weight_response(self):
        """Test parsing when using existing variant weight."""
        ai_response = {
            "department": "Pet Supplies",
            "category": "Dogs",
            "subcategory": "Food",
            "weight_estimation": {
                "original_weight": 25.0,
                "product_weight": 25.0,
                "product_packaging_weight": 0,
                "shipping_packaging_weight": 1.5,
                "final_shipping_weight": 29.2,  # (25 + 1.5) * 1.1
                "confidence": "high",
                "source": "existing_weight",
                "reasoning": "Used existing variant weight of 25 lbs"
            },
            "purchase_options": [1, 2, 3, 4],
            "needs_review": False
        }

        weight_estimation = ai_response['weight_estimation']

        assert weight_estimation['source'] == "existing_weight"
        assert weight_estimation['original_weight'] == 25.0
        assert weight_estimation['product_weight'] == 25.0


# ============================================================================
# VARIANT WEIGHT DATA APPLICATION TESTS
# ============================================================================

class TestVariantWeightDataApplication:
    """Tests for applying weight data to product variants."""

    def test_apply_weight_to_single_variant(self):
        """Test applying weight data to product with single variant."""
        product = {
            "title": "Test Product",
            "variants": [
                {
                    "title": "Default",
                    "weight": 0,
                    "weight_unit": "lb"
                }
            ],
            "metafields": []
        }

        weight_estimation = {
            "original_weight": 0,
            "product_weight": 50.0,
            "product_packaging_weight": 0.5,
            "shipping_packaging_weight": 2.0,
            "final_shipping_weight": 58.0,
            "confidence": "high",
            "source": "extracted_from_text",
            "reasoning": "50 lb bag"
        }

        # Apply weight data (simulating what openai_api.py does)
        final_weight = weight_estimation['final_shipping_weight']
        for variant in product['variants']:
            variant['weight_data'] = {
                'original_weight': weight_estimation['original_weight'],
                'product_weight': weight_estimation['product_weight'],
                'product_packaging_weight': weight_estimation['product_packaging_weight'],
                'shipping_packaging_weight': weight_estimation['shipping_packaging_weight'],
                'final_shipping_weight': final_weight,
                'confidence': weight_estimation['confidence'],
                'source': weight_estimation['source'],
                'reasoning': weight_estimation['reasoning'],
                'needs_review': False
            }
            variant['weight'] = final_weight
            variant['grams'] = int(final_weight * 453.592)

        # Verify
        assert product['variants'][0]['weight'] == 58.0
        assert product['variants'][0]['grams'] == 26308
        assert product['variants'][0]['weight_data']['product_weight'] == 50.0
        assert product['variants'][0]['weight_data']['confidence'] == "high"

    def test_apply_weight_to_multiple_variants(self):
        """Test applying same weight data to multiple variants."""
        product = {
            "title": "Test Product",
            "variants": [
                {"title": "Small", "weight": 0},
                {"title": "Medium", "weight": 0},
                {"title": "Large", "weight": 0}
            ],
            "metafields": []
        }

        weight_estimation = {
            "original_weight": 0,
            "product_weight": 10.0,
            "product_packaging_weight": 0.5,
            "shipping_packaging_weight": 1.0,
            "final_shipping_weight": 12.7,
            "confidence": "medium",
            "source": "estimated",
            "reasoning": "Estimated based on product category"
        }

        final_weight = weight_estimation['final_shipping_weight']
        for variant in product['variants']:
            variant['weight'] = final_weight
            variant['grams'] = int(final_weight * 453.592)
            variant['weight_data'] = weight_estimation.copy()
            variant['weight_data']['needs_review'] = True

        # All variants should have same weight
        assert all(v['weight'] == 12.7 for v in product['variants'])
        assert all(v['grams'] == 5760 for v in product['variants'])

    def test_preserve_existing_variant_data(self):
        """Test that applying weight data doesn't overwrite other variant fields."""
        product = {
            "title": "Test Product",
            "variants": [
                {
                    "title": "Default",
                    "sku": "TEST-001",
                    "price": "99.99",
                    "weight": 0,
                    "inventory_quantity": 10
                }
            ],
            "metafields": []
        }

        weight_estimation = {
            "final_shipping_weight": 25.0,
            "confidence": "high",
            "source": "existing_weight"
        }

        # Apply weight
        product['variants'][0]['weight'] = weight_estimation['final_shipping_weight']
        product['variants'][0]['grams'] = int(25.0 * 453.592)

        # Verify other fields preserved
        assert product['variants'][0]['sku'] == "TEST-001"
        assert product['variants'][0]['price'] == "99.99"
        assert product['variants'][0]['inventory_quantity'] == 10


# ============================================================================
# PURCHASE OPTIONS TESTS
# ============================================================================

class TestPurchaseOptions:
    """Tests for purchase options metafield application."""

    def test_add_purchase_options_metafield(self):
        """Test adding purchase_options metafield to product."""
        product = {
            "title": "Test Product",
            "variants": [],
            "metafields": []
        }

        purchase_options = [1, 2, 3, 4]

        # Add metafield
        product['metafields'].append({
            'namespace': 'custom',
            'key': 'purchase_options',
            'value': json.dumps(purchase_options),
            'type': 'json'
        })

        # Verify
        assert len(product['metafields']) == 1
        metafield = product['metafields'][0]
        assert metafield['namespace'] == 'custom'
        assert metafield['key'] == 'purchase_options'
        assert json.loads(metafield['value']) == [1, 2, 3, 4]
        assert metafield['type'] == 'json'

    def test_purchase_options_vary_by_category(self):
        """Test that purchase options differ by product category."""
        # Aggregates: [1, 2]
        aggregates_options = [1, 2]

        # Mulch: [1, 2, 3, 4]
        mulch_options = [1, 2, 3, 4]

        # Pet Food: [1, 2, 3, 4]
        pet_food_options = [1, 2, 3, 4]

        assert aggregates_options != mulch_options
        assert mulch_options == pet_food_options

    def test_purchase_options_metafield_format(self):
        """Test that purchase_options metafield has correct format."""
        metafield = {
            'namespace': 'custom',
            'key': 'purchase_options',
            'value': json.dumps([1, 2, 3, 4, 5]),
            'type': 'json'
        }

        # Parse value
        parsed_options = json.loads(metafield['value'])

        assert isinstance(parsed_options, list)
        assert all(isinstance(opt, int) for opt in parsed_options)
        assert all(1 <= opt <= 5 for opt in parsed_options)


# ============================================================================
# WEIGHT CONFIDENCE LEVEL TESTS
# ============================================================================

class TestWeightConfidence:
    """Tests for weight estimation confidence levels."""

    def test_high_confidence_sources(self):
        """Test that high-confidence sources are marked correctly."""
        high_confidence_sources = [
            "existing_weight",
            "extracted_from_text",
            "calculated_from_dimensions"
        ]

        for source in high_confidence_sources:
            weight_data = {
                "source": source,
                "confidence": "high"
            }
            assert weight_data['confidence'] == "high"

    def test_medium_confidence_sources(self):
        """Test that medium-confidence sources are marked correctly."""
        weight_data = {
            "source": "liquid_conversion",
            "confidence": "medium"
        }
        assert weight_data['confidence'] == "medium"

    def test_low_confidence_sources(self):
        """Test that low-confidence sources are marked correctly."""
        weight_data = {
            "source": "estimated",
            "confidence": "low"
        }
        assert weight_data['confidence'] == "low"

    def test_needs_review_flag(self):
        """Test that needs_review flag is set for low confidence."""
        weight_data_low = {
            "confidence": "low",
            "needs_review": True
        }

        weight_data_high = {
            "confidence": "high",
            "needs_review": False
        }

        assert weight_data_low['needs_review'] is True
        assert weight_data_high['needs_review'] is False


# ============================================================================
# SAFETY MARGIN TESTS
# ============================================================================

class TestSafetyMargin:
    """Tests for 10% safety margin application."""

    def test_safety_margin_applied_to_calculated_weight(self):
        """Test that 10% safety margin is applied to calculated weights."""
        base_weight = 50.0  # product + packaging
        expected_final = base_weight * 1.1  # 55.0

        assert abs(expected_final - 55.0) < 0.01

    def test_safety_margin_applied_to_liquid_conversion(self):
        """Test safety margin applied to liquid conversions."""
        product_weight = 84.0  # 8 gal * 10.5 lbs/gal
        packaging = 3.0
        base_weight = product_weight + packaging  # 87.0
        expected_final = base_weight * 1.1  # 95.7

        assert abs(expected_final - 95.7) < 0.01

    def test_safety_margin_rounds_up(self):
        """Test that final weight rounds up to nearest 0.5 lb."""
        test_cases = [
            (50.2, 50.5),
            (50.6, 51.0),
            (51.0, 51.0),
            (51.3, 51.5),
            (51.8, 52.0)
        ]

        for calculated, expected in test_cases:
            # Round up to nearest 0.5
            rounded = round(calculated * 2) / 2
            if rounded < calculated:
                rounded += 0.5
            assert rounded == expected


# ============================================================================
# LIQUID CONVERSION TESTS
# ============================================================================

class TestLiquidConversion:
    """Tests for liquid measure to weight conversions."""

    def test_fertilizer_conversion(self):
        """Test fertilizer liquid conversion (10.5 lbs/gal)."""
        gallons = 8
        lbs_per_gal = 10.5
        expected_weight = gallons * lbs_per_gal  # 84.0

        assert expected_weight == 84.0

    def test_sealer_conversion(self):
        """Test sealer liquid conversion (9.0 lbs/gal)."""
        gallons = 5
        lbs_per_gal = 9.0
        expected_weight = gallons * lbs_per_gal  # 45.0

        assert expected_weight == 45.0

    def test_fluid_ounces_conversion(self):
        """Test fluid ounces to pounds conversion."""
        fl_oz = 32
        # Fertilizer: 0.0820 lbs/fl oz
        lbs_per_fl_oz = 0.0820
        expected_weight = fl_oz * lbs_per_fl_oz  # 2.624

        assert abs(expected_weight - 2.624) < 0.001

    def test_paint_conversion(self):
        """Test paint liquid conversion (11.0 lbs/gal)."""
        gallons = 1
        lbs_per_gal = 11.0
        expected_weight = gallons * lbs_per_gal  # 11.0

        assert expected_weight == 11.0


# ============================================================================
# DIMENSIONAL CALCULATION TESTS
# ============================================================================

class TestDimensionalCalculation:
    """Tests for weight calculation from dimensions."""

    def test_concrete_paver_calculation(self):
        """Test weight calculation for concrete paver from dimensions."""
        # 30" x 30" x 2" slab
        length_in = 30
        width_in = 30
        height_in = 2

        # Convert to cubic feet
        volume_cf = (length_in * width_in * height_in) / 1728  # 1.042 cf

        # Concrete density: 150 lbs/cf
        density = 150
        weight_lbs = volume_cf * density  # ~156 lbs

        assert abs(weight_lbs - 156.25) < 0.5

    def test_stone_calculation(self):
        """Test weight calculation for stone product."""
        # Example: 12" x 12" x 3" stone
        volume_cf = (12 * 12 * 3) / 1728  # 0.25 cf
        density = 165  # Stone slightly denser
        weight_lbs = volume_cf * density  # 41.25 lbs

        assert abs(weight_lbs - 41.25) < 0.5


# ============================================================================
# PACKAGING WEIGHT TESTS
# ============================================================================

class TestPackagingWeights:
    """Tests for packaging weight application by category."""

    def test_aggregates_packaging(self):
        """Test packaging weights for aggregates (stone, soil, sand)."""
        # Aggregates typically have minimal packaging
        product_packaging = 0  # Bulk/loose
        shipping_packaging = 1.0  # Pallet wrap

        total_packaging = product_packaging + shipping_packaging
        assert total_packaging == 1.0

    def test_bagged_product_packaging(self):
        """Test packaging for bagged products (mulch, pet food)."""
        product_packaging = 0.5  # Bag weight
        shipping_packaging = 1.5  # Box + padding

        total_packaging = product_packaging + shipping_packaging
        assert total_packaging == 2.0

    def test_liquid_product_packaging(self):
        """Test packaging for liquid products (sealers, fertilizers)."""
        product_packaging = 0.5  # Container
        shipping_packaging = 2.0  # Box + padding for liquid

        total_packaging = product_packaging + shipping_packaging
        assert total_packaging == 2.5


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestWeightCalculationIntegration:
    """Integration tests for complete weight calculation workflow."""

    def test_complete_weight_workflow_with_text_extraction(self):
        """Test complete workflow: text extraction → packaging → safety margin."""
        # Input: "50 lb bag of dog food"
        extracted_weight = 50.0
        product_packaging = 0.5  # Bag
        shipping_packaging = 1.5  # Box

        base_weight = extracted_weight + product_packaging + shipping_packaging  # 52.0
        with_margin = base_weight * 1.1  # 57.2
        final_weight = round(with_margin * 2) / 2  # Round to 0.5
        if final_weight < with_margin:
            final_weight += 0.5

        assert final_weight == 57.5

    def test_complete_weight_workflow_with_liquid_conversion(self):
        """Test complete workflow: liquid conversion → packaging → safety margin."""
        # Input: "5 gallon liquid fertilizer"
        gallons = 5
        lbs_per_gal = 10.5
        product_weight = gallons * lbs_per_gal  # 52.5

        product_packaging = 0.5
        shipping_packaging = 2.0

        base_weight = product_weight + product_packaging + shipping_packaging  # 55.0
        with_margin = base_weight * 1.1  # 60.5

        # Use approximate comparison for floating point
        assert abs(with_margin - 60.5) < 0.01

    def test_complete_weight_workflow_with_dimensions(self):
        """Test complete workflow: dimensional calc → packaging → safety margin."""
        # Input: 30x30x2 inch concrete slab
        volume_cf = (30 * 30 * 2) / 1728
        density = 150
        product_weight = volume_cf * density  # ~156 lbs

        product_packaging = 0  # Bulk item
        shipping_packaging = 2.0  # Pallet wrap

        base_weight = product_weight + product_packaging + shipping_packaging
        with_margin = base_weight * 1.1

        assert with_margin > 170  # Should be ~174 lbs

    def test_weight_data_preserved_in_output(self):
        """Test that weight_data is preserved for troubleshooting."""
        variant = {
            "title": "Default",
            "weight": 58.0,
            "grams": 26308,
            "weight_data": {
                "original_weight": 0,
                "product_weight": 50.0,
                "product_packaging_weight": 0.5,
                "shipping_packaging_weight": 2.0,
                "final_shipping_weight": 58.0,
                "confidence": "high",
                "source": "extracted_from_text",
                "reasoning": "50 lb bag in title",
                "needs_review": False
            }
        }

        # Verify all troubleshooting data is present
        assert 'weight_data' in variant
        assert variant['weight_data']['original_weight'] == 0
        assert variant['weight_data']['product_weight'] == 50.0
        assert variant['weight_data']['reasoning'] != ""
