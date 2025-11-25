"""
Tests for uploader_modules/openai_api.py

Tests OpenAI API integration including model detection, pricing,
category matching, product enhancement, and collection descriptions.
"""

import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules import openai_api


# ============================================================================
# MODEL DETECTION TESTS
# ============================================================================

class TestIsReasoningModel:
    """Tests for is_reasoning_model() function."""

    def test_gpt5_is_reasoning_model(self):
        """Test that GPT-5 models are detected as reasoning models."""
        assert openai_api.is_reasoning_model("gpt-5") is True
        assert openai_api.is_reasoning_model("gpt-5-mini") is True
        assert openai_api.is_reasoning_model("gpt-5-nano") is True
        assert openai_api.is_reasoning_model("GPT-5") is True  # Case insensitive

    def test_o_series_is_reasoning_model(self):
        """Test that o-series models are detected as reasoning models."""
        assert openai_api.is_reasoning_model("o1") is True
        assert openai_api.is_reasoning_model("o1-preview") is True
        assert openai_api.is_reasoning_model("o1-mini") is True
        assert openai_api.is_reasoning_model("o3") is True
        assert openai_api.is_reasoning_model("o4") is True
        assert openai_api.is_reasoning_model("O1") is True  # Case insensitive

    def test_gpt4o_is_not_reasoning_model(self):
        """Test that GPT-4o is NOT a reasoning model."""
        assert openai_api.is_reasoning_model("gpt-4o") is False
        assert openai_api.is_reasoning_model("gpt-4o-mini") is False

    def test_gpt4_is_not_reasoning_model(self):
        """Test that GPT-4 is NOT a reasoning model."""
        assert openai_api.is_reasoning_model("gpt-4") is False
        assert openai_api.is_reasoning_model("gpt-4-turbo") is False
        assert openai_api.is_reasoning_model("gpt-4-1106-preview") is False

    def test_gpt35_is_not_reasoning_model(self):
        """Test that GPT-3.5 is NOT a reasoning model."""
        assert openai_api.is_reasoning_model("gpt-3.5-turbo") is False


class TestUsesMaxCompletionTokens:
    """Tests for uses_max_completion_tokens() function."""

    def test_reasoning_models_use_max_completion_tokens(self):
        """Test that reasoning models use max_completion_tokens."""
        assert openai_api.uses_max_completion_tokens("gpt-5") is True
        assert openai_api.uses_max_completion_tokens("o1-preview") is True

    def test_non_reasoning_models_use_max_tokens(self):
        """Test that non-reasoning models use max_tokens."""
        assert openai_api.uses_max_completion_tokens("gpt-4o") is False
        assert openai_api.uses_max_completion_tokens("gpt-4") is False


# ============================================================================
# PRICING TESTS
# ============================================================================

class TestGetOpenAIModelPricing:
    """Tests for get_openai_model_pricing() function."""

    def test_gpt5_pricing(self):
        """Test GPT-5 model pricing."""
        input_cost, output_cost = openai_api.get_openai_model_pricing("gpt-5")
        assert input_cost == 1.25
        assert output_cost == 10.00

    def test_gpt5_mini_pricing(self):
        """Test GPT-5-mini has same pricing as GPT-5."""
        input_cost, output_cost = openai_api.get_openai_model_pricing("gpt-5-mini")
        assert input_cost == 1.25
        assert output_cost == 10.00

    def test_gpt4o_pricing(self):
        """Test GPT-4o model pricing."""
        input_cost, output_cost = openai_api.get_openai_model_pricing("gpt-4o")
        assert input_cost == 2.50
        assert output_cost == 10.00

    def test_gpt4_turbo_pricing(self):
        """Test GPT-4 Turbo pricing."""
        input_cost, output_cost = openai_api.get_openai_model_pricing("gpt-4-turbo")
        assert input_cost == 10.00
        assert output_cost == 30.00

    def test_gpt4_turbo_variants(self):
        """Test various GPT-4 Turbo model names."""
        for model in ["gpt-4-1106-preview", "gpt-4-0125-preview"]:
            input_cost, output_cost = openai_api.get_openai_model_pricing(model)
            assert input_cost == 10.00
            assert output_cost == 30.00

    def test_gpt4_pricing(self):
        """Test GPT-4 base model pricing."""
        input_cost, output_cost = openai_api.get_openai_model_pricing("gpt-4")
        assert input_cost == 30.00
        assert output_cost == 60.00

    def test_unknown_model_defaults_to_gpt5(self):
        """Test unknown models default to GPT-5 pricing."""
        input_cost, output_cost = openai_api.get_openai_model_pricing("unknown-model")
        assert input_cost == 1.25
        assert output_cost == 10.00


# ============================================================================
# PROMPT BUILDER TESTS
# ============================================================================

class TestBuildTaxonomyPrompt:
    """Tests for _build_taxonomy_prompt() function."""

    def test_basic_prompt_structure(self):
        """Test that taxonomy prompt has expected structure."""
        taxonomy_doc = "Department: Pet Supplies\nCategory: Dogs"
        prompt = openai_api._build_taxonomy_prompt(
            title="Dog Food Premium",
            body_html="<p>High-quality dog food</p>",
            taxonomy_doc=taxonomy_doc
        )

        assert "Dog Food Premium" in prompt
        assert "High-quality dog food" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_with_weight_data(self):
        """Test prompt includes weight information when provided."""
        taxonomy_doc = "Department: Pet Supplies"
        prompt = openai_api._build_taxonomy_prompt(
            title="Test Product",
            body_html="<p>Description</p>",
            taxonomy_doc=taxonomy_doc,
            current_weight=25.5
        )

        assert "25.5" in prompt
        assert "weight" in prompt.lower()

    def test_prompt_with_variant_data(self):
        """Test prompt includes variant information when provided."""
        taxonomy_doc = "Department: Pet Supplies"
        variant_data = {
            "Color": ["Red", "Blue"],
            "Size": ["Small", "Large"]
        }
        prompt = openai_api._build_taxonomy_prompt(
            title="Test Product",
            body_html="<p>Description</p>",
            taxonomy_doc=taxonomy_doc,
            variant_data=variant_data
        )

        assert "Test Product" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestBuildDescriptionPrompt:
    """Tests for _build_description_prompt() function."""

    def test_basic_description_prompt(self):
        """Test basic description prompt structure."""
        voice_doc = "Voice: Professional and friendly"
        prompt = openai_api._build_description_prompt(
            title="Test Product",
            body_html="<p>Old description</p>",
            department="Pet Supplies",
            voice_tone_doc=voice_doc
        )

        assert "Test Product" in prompt
        assert "Old description" in prompt
        assert "Pet Supplies" in prompt
        assert "Voice: Professional and friendly" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_description_prompt_with_audience(self):
        """Test description prompt includes audience information."""
        voice_doc = "Voice: Professional"
        prompt = openai_api._build_description_prompt(
            title="Test Product",
            body_html="<p>Description</p>",
            department="Pet Supplies",
            voice_tone_doc=voice_doc,
            audience_name="Professionals"
        )

        assert "Professionals" in prompt
        assert "audience" in prompt.lower()


class TestBuildCollectionDescriptionPrompt:
    """Tests for _build_collection_description_prompt() function."""

    def test_collection_prompt_structure(self):
        """Test collection description prompt structure."""
        voice_doc = "Voice: Professional"
        product_samples = [
            "Product 1: Dog Food",
            "Product 2: Dog Treats",
            "Product 3: Dog Toys"
        ]

        prompt = openai_api._build_collection_description_prompt(
            collection_title="Dog Supplies",
            department="Pet Supplies",
            product_samples=product_samples,
            voice_tone_doc=voice_doc
        )

        assert "Dog Supplies" in prompt
        assert "Pet Supplies" in prompt
        assert "Dog Food" in prompt
        assert "Dog Treats" in prompt
        assert "Dog Toys" in prompt
        assert "100 words" in prompt or "100-word" in prompt

    def test_collection_prompt_with_empty_products(self):
        """Test collection prompt with no product samples."""
        voice_doc = "Voice: Professional"

        prompt = openai_api._build_collection_description_prompt(
            collection_title="Test Collection",
            department="Test Department",
            product_samples=[],
            voice_tone_doc=voice_doc
        )

        assert "Test Collection" in prompt
        assert "Test Department" in prompt


# ============================================================================
# CATEGORY MATCHING TESTS
# ============================================================================

class TestMatchShopifyCategoryWithOpenAI:
    """Tests for match_shopify_category_with_openai() function."""

    @patch('uploader_modules.openai_api.OpenAI')
    def test_successful_category_match(self, mock_openai_class):
        """Test successful category matching."""
        # Mock OpenAI client and response
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"category_fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies", "reasoning": "Product is dog food"}'''
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/123", "fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies"},
            {"id": "gid://shopify/TaxonomyCategory/456", "fullName": "Home & Garden"}
        ]

        result = openai_api.match_shopify_category_with_openai(
            product_title="Premium Dog Food",
            product_description="High-quality nutrition for dogs",
            shopify_categories=shopify_categories,
            api_key="test_api_key",
            model="gpt-4o"
        )

        assert result == "gid://shopify/TaxonomyCategory/123"
        assert mock_client.chat.completions.create.called

    @patch('uploader_modules.openai_api.OpenAI')
    def test_category_match_with_status_fn(self, mock_openai_class):
        """Test category matching with status function."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"category_fullName": "Home & Garden", "reasoning": "Garden product"}'''
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/789", "fullName": "Home & Garden"}
        ]

        mock_status_fn = Mock()

        result = openai_api.match_shopify_category_with_openai(
            product_title="Garden Tool",
            product_description="Tool for gardening",
            shopify_categories=shopify_categories,
            api_key="test_api_key",
            model="gpt-4o",
            status_fn=mock_status_fn
        )

        assert result == "gid://shopify/TaxonomyCategory/789"
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.openai_api.OpenAI')
    def test_category_match_no_match_found(self, mock_openai_class):
        """Test when AI returns null category."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"category_fullName": null, "reasoning": "No suitable category"}'''
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/123", "fullName": "Test Category"}
        ]

        result = openai_api.match_shopify_category_with_openai(
            product_title="Test Product",
            product_description="Test description",
            shopify_categories=shopify_categories,
            api_key="test_api_key",
            model="gpt-4o"
        )

        assert result is None

    @patch('uploader_modules.openai_api.OpenAI', None)
    def test_openai_not_installed(self):
        """Test handling when OpenAI package is not installed."""
        with pytest.raises(ImportError, match="openai package not installed"):
            openai_api.match_shopify_category_with_openai(
                product_title="Test",
                product_description="Test",
                shopify_categories=[],
                api_key="test",
                model="gpt-4o"
            )

    @patch('uploader_modules.openai_api.OpenAI')
    def test_category_match_invalid_json(self, mock_openai_class, caplog):
        """Test handling of invalid JSON response."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response"
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/123", "fullName": "Test"}
        ]

        with caplog.at_level(logging.ERROR):
            result = openai_api.match_shopify_category_with_openai(
                product_title="Test",
                product_description="Test",
                shopify_categories=shopify_categories,
                api_key="test_api_key",
                model="gpt-4o"
            )

        assert result is None
        assert "Failed to parse" in caplog.text

    @patch('uploader_modules.openai_api.OpenAI')
    def test_category_match_api_error(self, mock_openai_class, caplog):
        """Test handling of API errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception("API Error")

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/123", "fullName": "Test"}
        ]

        with caplog.at_level(logging.ERROR):
            result = openai_api.match_shopify_category_with_openai(
                product_title="Test",
                product_description="Test",
                shopify_categories=shopify_categories,
                api_key="test_api_key",
                model="gpt-4o"
            )

        # Function catches exception and returns None
        assert result is None
        assert "Error matching Shopify category" in caplog.text

    @patch('uploader_modules.openai_api.OpenAI')
    def test_uses_temperature_for_non_reasoning_models(self, mock_openai_class):
        """Test that temperature is used for non-reasoning models."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"category_fullName": "Test", "reasoning": "Test"}'''
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/123", "fullName": "Test"}
        ]

        openai_api.match_shopify_category_with_openai(
            product_title="Test",
            product_description="Test",
            shopify_categories=shopify_categories,
            api_key="test_api_key",
            model="gpt-4o"  # Non-reasoning model
        )

        # Check that temperature was passed
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" in call_kwargs
        assert call_kwargs["temperature"] == 0.3

    @patch('uploader_modules.openai_api.OpenAI')
    def test_no_temperature_for_reasoning_models(self, mock_openai_class):
        """Test that temperature is NOT used for reasoning models."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"category_fullName": "Test", "reasoning": "Test"}'''
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        shopify_categories = [
            {"id": "gid://shopify/TaxonomyCategory/123", "fullName": "Test"}
        ]

        openai_api.match_shopify_category_with_openai(
            product_title="Test",
            product_description="Test",
            shopify_categories=shopify_categories,
            api_key="test_api_key",
            model="gpt-5"  # Reasoning model
        )

        # Check that temperature was NOT passed
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" not in call_kwargs

# ============================================================================
# PRODUCT ENHANCEMENT TESTS
# ============================================================================

class TestEnhanceProductWithOpenAI:
    """Tests for enhance_product_with_openai() function."""

    @patch('uploader_modules.openai_api.OpenAI')
    def test_successful_product_enhancement(self, mock_openai_class):
        """Test successful product enhancement with taxonomy and description."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock two API responses: taxonomy assignment and description rewriting
        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Pet Supplies", "category": "Dogs", "subcategory": "Treats", "reasoning": "This is dog treats", "weight_estimation": {"estimated_shipping_weight_lbs": 25.5, "confidence": "high", "reasoning": "Heavy bag"}, "purchase_options": {"primary_consideration": "quality"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        description_response = Mock()
        description_response.choices = [Mock()]
        description_response.choices[0].message.content = "<p>Enhanced product description</p>"
        description_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.side_effect = [taxonomy_response, description_response]

        product = {
            "title": "Premium Dog Food",
            "body_html": "<p>Old description</p>",
            "variants": [{"weight": 25}]
        }

        result = openai_api.enhance_product_with_openai(
            product=product,
            taxonomy_doc="Department: Pet Supplies",
            voice_tone_doc="Voice: Professional",
            shopify_categories=[],
            api_key="test_key",
            model="gpt-4o"
        )

        assert result["title"] == "Premium Dog Food"
        assert result["body_html"] == "<p>Enhanced product description</p>"
        assert "tags" in result
        assert "Dogs" in result["tags"]
        assert "Treats" in result["tags"]

    @patch('uploader_modules.openai_api.OpenAI', None)
    def test_openai_not_installed_error(self):
        """Test error when OpenAI package not installed."""
        product = {"title": "Test", "body_html": "Test"}

        with pytest.raises(ImportError, match="openai package not installed"):
            openai_api.enhance_product_with_openai(
                product=product,
                taxonomy_doc="",
                voice_tone_doc="",
                shopify_categories=[],
                api_key="test",
                model="gpt-4o"
            )

    @patch('uploader_modules.openai_api.OpenAI')
    def test_product_without_title_error(self, mock_openai_class):
        """Test error when product has no title."""
        product = {"body_html": "Description"}

        with pytest.raises(ValueError, match="Product has no title"):
            openai_api.enhance_product_with_openai(
                product=product,
                taxonomy_doc="",
                voice_tone_doc="",
                shopify_categories=[],
                api_key="test",
                model="gpt-4o"
            )

    @patch('uploader_modules.openai_api.OpenAI')
    def test_enhancement_with_status_fn(self, mock_openai_class):
        """Test enhancement with status function."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Pet Supplies", "category": "Dogs", "subcategory": "", "reasoning": "Test", "weight_estimation": {"estimated_shipping_weight_lbs": 10, "confidence": "medium", "reasoning": "Test"}, "purchase_options": {"primary_consideration": "price"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        description_response = Mock()
        description_response.choices = [Mock()]
        description_response.choices[0].message.content = "<p>Description</p>"
        description_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.side_effect = [taxonomy_response, description_response]

        product = {"title": "Test Product", "body_html": "Old"}
        mock_status_fn = Mock()

        result = openai_api.enhance_product_with_openai(
            product=product,
            taxonomy_doc="",
            voice_tone_doc="",
            shopify_categories=[],
            api_key="test",
            model="gpt-4o",
            status_fn=mock_status_fn
        )

        assert result is not None
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.openai_api.OpenAI')
    def test_enhancement_with_audience_config(self, mock_openai_class):
        """Test enhancement with multiple audience descriptions."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Pet Supplies", "category": "Dogs", "subcategory": "", "reasoning": "Test", "weight_estimation": {"estimated_shipping_weight_lbs": 5, "confidence": "medium", "reasoning": "Test"}, "purchase_options": {"primary_consideration": "quality"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        desc_response_1 = Mock()
        desc_response_1.choices = [Mock()]
        desc_response_1.choices[0].message.content = "<p>Description for audience 1</p>"
        desc_response_1.usage = Mock(prompt_tokens=100, completion_tokens=50)

        desc_response_2 = Mock()
        desc_response_2.choices = [Mock()]
        desc_response_2.choices[0].message.content = "<p>Description for audience 2</p>"
        desc_response_2.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.side_effect = [taxonomy_response, desc_response_1, desc_response_2]

        product = {"title": "Test Product", "body_html": "Old"}
        audience_config = {
            "count": 2,
            "audience_1_name": "Professionals",
            "audience_2_name": "Homeowners",
            "tab_1_label": "For Professionals",
            "tab_2_label": "For Homeowners"
        }

        result = openai_api.enhance_product_with_openai(
            product=product,
            taxonomy_doc="",
            voice_tone_doc="",
            shopify_categories=[],
            api_key="test",
            model="gpt-4o",
            audience_config=audience_config
        )

        # Should have metafields for both audiences
        assert "metafields" in result
        metafields = result["metafields"]
        
        # Find audience description metafields
        audience_metafields = [mf for mf in metafields if "audience" in mf.get("key", "").lower() or "description" in mf.get("key", "").lower()]
        assert len(audience_metafields) >= 2

    @patch('uploader_modules.openai_api.OpenAI')
    def test_enhancement_uses_reasoning_model_params(self, mock_openai_class):
        """Test that reasoning models use correct parameters."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Pet Supplies", "category": "Dogs", "subcategory": "", "reasoning": "Test", "weight_estimation": {"estimated_shipping_weight_lbs": 1, "confidence": "low", "reasoning": "Test"}, "purchase_options": {"primary_consideration": "price"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        description_response = Mock()
        description_response.choices = [Mock()]
        description_response.choices[0].message.content = "<p>Description</p>"
        description_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.side_effect = [taxonomy_response, description_response]

        product = {"title": "Test", "body_html": "Old"}

        openai_api.enhance_product_with_openai(
            product=product,
            taxonomy_doc="",
            voice_tone_doc="",
            shopify_categories=[],
            api_key="test",
            model="gpt-5"  # Reasoning model
        )

        # First call (taxonomy) should not have temperature
        first_call_kwargs = mock_client.chat.completions.create.call_args_list[0][1]
        assert "temperature" not in first_call_kwargs


# ============================================================================
# COLLECTION DESCRIPTION TESTS
# ============================================================================

class TestGenerateCollectionDescription:
    """Tests for generate_collection_description() function."""

    @patch('uploader_modules.openai_api.OpenAI')
    def test_successful_collection_description(self, mock_openai_class):
        """Test successful collection description generation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "<p>This is a great collection of products for your needs.</p>"
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        product_samples = [
            "Product 1: High-quality product with great features",
            "Product 2: Another amazing product for your needs"
        ]

        result = openai_api.generate_collection_description(
            collection_title="Test Collection",
            department="Pet Supplies",
            product_samples=product_samples,
            voice_tone_doc="Voice: Professional",
            api_key="test_key",
            model="gpt-4o"
        )

        assert result == "<p>This is a great collection of products for your needs.</p>"
        assert mock_client.chat.completions.create.called

    @patch('uploader_modules.openai_api.OpenAI', None)
    def test_collection_openai_not_installed(self):
        """Test error when OpenAI not installed."""
        with pytest.raises(ImportError, match="openai package not installed"):
            openai_api.generate_collection_description(
                collection_title="Test",
                department="Test",
                product_samples=[],
                voice_tone_doc="",
                api_key="test",
                model="gpt-4o"
            )

    @patch('uploader_modules.openai_api.OpenAI')
    def test_collection_with_status_fn(self, mock_openai_class):
        """Test collection description with status function."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "<p>Collection description</p>"
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        mock_status_fn = Mock()

        result = openai_api.generate_collection_description(
            collection_title="Test",
            department="Test",
            product_samples=[],
            voice_tone_doc="",
            api_key="test",
            model="gpt-4o",
            status_fn=mock_status_fn
        )

        assert result is not None
        assert mock_status_fn.call_count >= 1

    @patch('uploader_modules.openai_api.OpenAI')
    def test_collection_with_many_products(self, mock_openai_class):
        """Test that only first 5 products are sampled."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "<p>Description</p>"
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        # Create 10 products
        product_samples = [
            f"Product {i}: Description for product {i}"
            for i in range(10)
        ]

        result = openai_api.generate_collection_description(
            collection_title="Test",
            department="Test",
            product_samples=product_samples,
            voice_tone_doc="",
            api_key="test",
            model="gpt-4o"
        )

        assert result is not None
        # Check that API was called with only first 5 products in the prompt
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        prompt_content = call_kwargs["messages"][0]["content"]
        assert "Product 0" in prompt_content
        assert "Product 4" in prompt_content
        # Products 5-9 should not be in first 5
        assert "Product 9" not in prompt_content or "Product 5" in prompt_content[:1000]

    @patch('uploader_modules.openai_api.OpenAI')
    def test_collection_uses_temperature_for_non_reasoning(self, mock_openai_class):
        """Test that temperature is used for non-reasoning models."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "<p>Description</p>"
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = mock_response

        openai_api.generate_collection_description(
            collection_title="Test",
            department="Test",
            product_samples=[],
            voice_tone_doc="",
            api_key="test",
            model="gpt-4o"  # Non-reasoning model
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" in call_kwargs
        assert call_kwargs["temperature"] == 0.7


class TestEnhanceProductTaxonomyValidation:
    """Tests for taxonomy validation in enhance_product_with_openai()."""

    @patch('uploader_modules.openai_api.OpenAI')
    def test_taxonomy_validation_failure_with_status_fn(self, mock_openai_class, caplog):
        """Test detailed error logging when taxonomy validation fails with status_fn."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Return invalid department that will fail validation
        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Invalid Department", "category": "Invalid Category", "subcategory": "", "reasoning": "Test", "weight_estimation": {"estimated_shipping_weight_lbs": 10, "confidence": "medium", "reasoning": "Test"}, "purchase_options": {"primary_consideration": "price"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = taxonomy_response

        product = {"title": "Test Product", "body_html": "Old"}
        mock_status_fn = Mock()

        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception, match="Error enhancing product"):
                openai_api.enhance_product_with_openai(
                    product=product,
                    taxonomy_doc="",
                    voice_tone_doc="",
                    shopify_categories=[],
                    api_key="test",
                    model="gpt-4o",
                    status_fn=mock_status_fn
                )

        # Verify status_fn was called with error messages
        assert mock_status_fn.call_count >= 10  # Multiple error messages
        # Verify detailed error logging
        assert "TAXONOMY VALIDATION FAILED" in caplog.text
        assert "Invalid department" in caplog.text

    @patch('uploader_modules.openai_api.OpenAI')
    def test_taxonomy_validation_with_category_suggestions(self, mock_openai_class, caplog):
        """Test error logging with category suggestions."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Return valid department but invalid category
        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Pet Supplies", "category": "InvalidCat", "subcategory": "", "reasoning": "Test", "weight_estimation": {"estimated_shipping_weight_lbs": 10, "confidence": "medium", "reasoning": "Test"}, "purchase_options": {"primary_consideration": "price"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = taxonomy_response

        product = {"title": "Test Product", "body_html": "Old"}

        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception, match="Error enhancing product"):
                openai_api.enhance_product_with_openai(
                    product=product,
                    taxonomy_doc="",
                    voice_tone_doc="",
                    shopify_categories=[],
                    api_key="test",
                    model="gpt-4o"
                )

        # Should log valid categories
        assert "Valid categories" in caplog.text or "Invalid category" in caplog.text

    @patch('uploader_modules.openai_api.OpenAI')
    def test_taxonomy_validation_with_subcategory_suggestions(self, mock_openai_class, caplog):
        """Test error logging with subcategory suggestions."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Return valid department and category but invalid subcategory
        taxonomy_response = Mock()
        taxonomy_response.choices = [Mock()]
        taxonomy_response.choices[0].message.content = '''{"department": "Pet Supplies", "category": "Dogs", "subcategory": "InvalidSubcat", "reasoning": "Test", "weight_estimation": {"estimated_shipping_weight_lbs": 10, "confidence": "medium", "reasoning": "Test"}, "purchase_options": {"primary_consideration": "price"}, "needs_review": false}'''
        taxonomy_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        mock_client.chat.completions.create.return_value = taxonomy_response

        product = {"title": "Test Product", "body_html": "Old"}

        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception, match="Error enhancing product"):
                openai_api.enhance_product_with_openai(
                    product=product,
                    taxonomy_doc="",
                    voice_tone_doc="",
                    shopify_categories=[],
                    api_key="test",
                    model="gpt-4o"
                )

        # Should log valid subcategories
        assert "Valid subcategories" in caplog.text or "Invalid subcategory" in caplog.text
