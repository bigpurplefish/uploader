"""
Tests for taxonomy validation functionality.

Tests the complete taxonomy validation workflow including loading taxonomy
structure from markdown files and validating product assignments against it.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules.utils import (
    load_taxonomy_structure,
    validate_taxonomy_assignment
)


# ============================================================================
# TAXONOMY STRUCTURE LOADING TESTS
# ============================================================================

class TestTaxonomyStructureLoading:
    """Tests for loading and parsing taxonomy structure from markdown."""

    def test_load_taxonomy_from_valid_file(self, temp_taxonomy_file):
        """Test loading taxonomy from a valid markdown file."""
        taxonomy = load_taxonomy_structure(str(temp_taxonomy_file))

        assert isinstance(taxonomy, dict)
        assert len(taxonomy) > 0

    def test_taxonomy_has_correct_departments(self, temp_taxonomy_file):
        """Test that all departments are loaded correctly."""
        taxonomy = load_taxonomy_structure(str(temp_taxonomy_file))

        expected_departments = [
            "Landscape And Construction",
            "Pet Supplies",
            "Home And Gift",
            "Lawn And Garden"
        ]

        for dept in expected_departments:
            assert dept in taxonomy

    def test_taxonomy_has_correct_categories(self, temp_taxonomy_file):
        """Test that categories are nested under departments."""
        taxonomy = load_taxonomy_structure(str(temp_taxonomy_file))

        # Check Landscape and Construction categories
        assert "Aggregates" in taxonomy["Landscape And Construction"]
        assert "Pavers And Hardscaping" in taxonomy["Landscape And Construction"]

        # Check Pet Supplies categories
        assert "Dogs" in taxonomy["Pet Supplies"]
        assert "Cats" in taxonomy["Pet Supplies"]

    def test_taxonomy_has_correct_subcategories(self, temp_taxonomy_file):
        """Test that subcategories are nested under categories."""
        taxonomy = load_taxonomy_structure(str(temp_taxonomy_file))

        # Check Aggregates subcategories
        aggregates_subs = taxonomy["Landscape And Construction"]["Aggregates"]
        assert "Stone" in aggregates_subs
        assert "Soil" in aggregates_subs
        assert "Mulch" in aggregates_subs
        assert "Sand" in aggregates_subs

        # Check Dogs subcategories
        dogs_subs = taxonomy["Pet Supplies"]["Dogs"]
        assert "Food" in dogs_subs
        assert "Toys" in dogs_subs

    def test_load_nonexistent_file_returns_empty_dict(self):
        """Test that loading a nonexistent file returns empty dict."""
        taxonomy = load_taxonomy_structure("/nonexistent/path/taxonomy.md")
        assert taxonomy == {}

    def test_load_invalid_path_returns_empty_dict(self):
        """Test that loading with invalid path returns empty dict."""
        # Use a path that definitely doesn't exist
        taxonomy = load_taxonomy_structure("/this/path/definitely/does/not/exist/taxonomy.md")
        assert taxonomy == {}


# ============================================================================
# VALID TAXONOMY ASSIGNMENT TESTS
# ============================================================================

class TestValidTaxonomyAssignments:
    """Tests for valid taxonomy assignments that should pass validation."""

    def test_valid_full_assignment(self, temp_taxonomy_file):
        """Test valid assignment with department, category, and subcategory."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Pavers And Hardscaping",
            "Slabs",
            str(temp_taxonomy_file)
        )

        assert is_valid is True
        assert error_msg == ""
        assert suggestions == {}

    def test_valid_assignment_without_subcategory(self, temp_taxonomy_file):
        """Test valid assignment with only department and category."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Pet Supplies",
            "Dogs",
            "",
            str(temp_taxonomy_file)
        )

        assert is_valid is True
        assert error_msg == ""

    def test_valid_assignment_aggregates_stone(self, temp_taxonomy_file):
        """Test specific valid assignment: Aggregates > Stone."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Aggregates",
            "Stone",
            str(temp_taxonomy_file)
        )

        assert is_valid is True

    def test_valid_assignment_pet_supplies_dogs_food(self, temp_taxonomy_file):
        """Test specific valid assignment: Pet Supplies > Dogs > Food."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Pet Supplies",
            "Dogs",
            "Food",
            str(temp_taxonomy_file)
        )

        assert is_valid is True


# ============================================================================
# INVALID DEPARTMENT TESTS
# ============================================================================

class TestInvalidDepartmentAssignments:
    """Tests for invalid department assignments."""

    def test_invalid_department(self, temp_taxonomy_file):
        """Test that invalid department is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Invalid Department",
            "Some Category",
            "",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid department" in error_msg
        assert "valid_departments" in suggestions
        assert len(suggestions["valid_departments"]) > 0

    def test_invalid_department_provides_suggestions(self, temp_taxonomy_file):
        """Test that invalid department provides list of valid departments."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Nonexistent Department",
            "Category",
            "",
            str(temp_taxonomy_file)
        )

        assert "valid_departments" in suggestions
        valid_depts = suggestions["valid_departments"]
        assert "Landscape And Construction" in valid_depts
        assert "Pet Supplies" in valid_depts

    def test_typo_in_department(self, temp_taxonomy_file):
        """Test that typo in department name is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscap and Construction",  # typo
            "Aggregates",
            "Stone",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid department" in error_msg


# ============================================================================
# INVALID CATEGORY TESTS
# ============================================================================

class TestInvalidCategoryAssignments:
    """Tests for invalid category assignments."""

    def test_invalid_category(self, temp_taxonomy_file):
        """Test that invalid category is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Invalid Category",
            "",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid category" in error_msg
        assert "valid_categories" in suggestions

    def test_invalid_category_provides_suggestions(self, temp_taxonomy_file):
        """Test that invalid category provides list of valid categories."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Nonexistent Category",
            "",
            str(temp_taxonomy_file)
        )

        assert "valid_categories" in suggestions
        valid_cats = suggestions["valid_categories"]
        assert "Aggregates" in valid_cats
        assert "Pavers And Hardscaping" in valid_cats

    def test_category_from_wrong_department(self, temp_taxonomy_file):
        """Test that category from wrong department is caught."""
        # "Dogs" is valid but under Pet Supplies, not Landscape
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Dogs",
            "",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid category" in error_msg


# ============================================================================
# INVALID SUBCATEGORY TESTS
# ============================================================================

class TestInvalidSubcategoryAssignments:
    """Tests for invalid subcategory assignments."""

    def test_invalid_subcategory(self, temp_taxonomy_file):
        """Test that invalid subcategory is caught."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Aggregates",
            "Invalid Subcategory",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid subcategory" in error_msg
        assert "valid_subcategories" in suggestions

    def test_invalid_subcategory_provides_suggestions(self, temp_taxonomy_file):
        """Test that invalid subcategory provides list of valid subcategories."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Aggregates",
            "Nonexistent Subcategory",
            str(temp_taxonomy_file)
        )

        assert "valid_subcategories" in suggestions
        valid_subs = suggestions["valid_subcategories"]
        assert "Stone" in valid_subs
        assert "Soil" in valid_subs
        assert "Mulch" in valid_subs

    def test_subcategory_from_wrong_category(self, temp_taxonomy_file):
        """Test that subcategory from wrong category is caught."""
        # "Slabs" is valid but under Pavers and Hardscaping, not Aggregates
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Aggregates",
            "Slabs",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid subcategory" in error_msg


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestTaxonomyValidationEdgeCases:
    """Tests for edge cases in taxonomy validation."""

    def test_empty_strings(self, temp_taxonomy_file):
        """Test validation with empty strings."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "",
            "",
            "",
            str(temp_taxonomy_file)
        )

        assert is_valid is False

    def test_case_sensitivity(self, temp_taxonomy_file):
        """Test that taxonomy validation is case-sensitive."""
        # Lowercase version should fail
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "landscape and construction",  # lowercase
            "Aggregates",
            "Stone",
            str(temp_taxonomy_file)
        )

        assert is_valid is False
        assert "Invalid department" in error_msg

    def test_whitespace_handling(self, temp_taxonomy_file):
        """Test handling of whitespace in taxonomy names."""
        # Extra whitespace should not cause validation to fail
        # (assuming the taxonomy file has the correct spacing)
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Landscape And Construction",
            "Aggregates",
            "Stone",
            str(temp_taxonomy_file)
        )

        assert is_valid is True

    def test_validation_without_taxonomy_file(self):
        """Test validation when taxonomy file doesn't exist."""
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            "Any Department",
            "Any Category",
            "",
            "/nonexistent/taxonomy.md"
        )

        assert is_valid is False
        assert "Failed to load taxonomy" in error_msg


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestTaxonomyValidationIntegration:
    """Integration tests for complete taxonomy validation workflow."""

    def test_complete_workflow_valid_product(self, temp_taxonomy_file):
        """Test complete workflow with valid product taxonomy."""
        # Simulate AI assigning taxonomy to a product
        ai_department = "Pet Supplies"
        ai_category = "Dogs"
        ai_subcategory = "Food"

        # Validate the assignment
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            ai_department,
            ai_category,
            ai_subcategory,
            str(temp_taxonomy_file)
        )

        # Should pass validation
        assert is_valid is True

        # Product should be allowed to proceed to Shopify
        # (in real code, this would trigger product upload)

    def test_complete_workflow_invalid_product_stops_processing(self, temp_taxonomy_file):
        """Test that invalid taxonomy stops processing."""
        # Simulate AI assigning invalid taxonomy
        ai_department = "Pet Supplies"
        ai_category = "Reptiles"  # Not in taxonomy
        ai_subcategory = ""

        # Validate the assignment
        is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            ai_department,
            ai_category,
            ai_subcategory,
            str(temp_taxonomy_file)
        )

        # Should fail validation
        assert is_valid is False
        assert error_msg != ""

        # In real code, this would:
        # 1. Stop processing immediately
        # 2. Log detailed error message
        # 3. Show suggestions to user
        # 4. Require user to update taxonomy file or fix product data

    def test_multiple_products_with_mixed_validity(self, temp_taxonomy_file):
        """Test validating multiple products with mixed validity."""
        products_to_validate = [
            ("Landscape And Construction", "Aggregates", "Stone"),      # Valid
            ("Pet Supplies", "Dogs", "Food"),                           # Valid
            ("Home And Gift", "Invalid Category", ""),                  # Invalid
            ("Lawn And Garden", "Garden Tools", "Shovels"),            # Valid
        ]

        results = []
        for dept, cat, subcat in products_to_validate:
            is_valid, _, _ = validate_taxonomy_assignment(
                dept, cat, subcat, str(temp_taxonomy_file)
            )
            results.append(is_valid)

        # Should have 3 valid, 1 invalid
        assert results.count(True) == 3
        assert results.count(False) == 1

        # In real processing, the invalid one should stop the entire batch
