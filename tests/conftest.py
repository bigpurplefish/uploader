"""
Pytest configuration and shared fixtures for Shopify Product Uploader tests.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_products():
    """Sample product data for testing."""
    return [
        {
            "title": "Techo-Bloc Aberdeen Slab",
            "product_type": "Landscape and Construction",
            "tags": ["Pavers and Hardscaping", "Slabs"],
            "body_html": "<p>Premium concrete paver slab for patios and walkways</p>",
            "variants": [
                {
                    "sku": "50000",
                    "price": "12.99",
                    "weight": 0,
                    "grams": 0,
                    "option1": "Rock Garden Brown",
                    "metafields": [
                        {
                            "namespace": "custom",
                            "key": "size_info",
                            "value": "20 × 10 × 2 ¼ in (508 × 254 × 57 mm)",
                            "type": "single_line_text_field"
                        }
                    ]
                }
            ],
            "options": [
                {"name": "Color"}
            ]
        },
        {
            "title": "Premium Dog Food 50lb Bag",
            "product_type": "Pet Supplies",
            "tags": ["Dogs", "Food"],
            "body_html": "<p>High-quality 50 lb bag of dog food</p>",
            "variants": [
                {
                    "sku": "DOG-001",
                    "price": "49.99",
                    "weight": 50,
                    "grams": 22680,
                    "metafields": []
                }
            ],
            "options": []
        },
        {
            "title": "Concrete Sealer 5 Gallon",
            "product_type": "Paving & Construction Supplies",
            "tags": ["Paving & Construction Supplies", "Sealers"],
            "body_html": "<p>Professional grade concrete sealer, 5 gallon container</p>",
            "variants": [
                {
                    "sku": "SEAL-5GAL",
                    "price": "89.99",
                    "weight": 0,
                    "grams": 0,
                    "metafields": []
                }
            ],
            "options": []
        }
    ]


@pytest.fixture
def sample_product_no_weight():
    """Sample product without weight information."""
    return {
        "title": "Garden Gnome Statue",
        "product_type": "Home and Gift",
        "tags": ["Home Decor"],
        "body_html": "<p>Decorative garden gnome</p>",
        "variants": [
            {
                "sku": "GNOME-001",
                "price": "24.99",
                "weight": 0,
                "grams": 0,
                "metafields": []
            }
        ],
        "options": []
    }


@pytest.fixture
def sample_taxonomy():
    """Sample taxonomy structure for testing."""
    return {
        "Landscape And Construction": {
            "Aggregates": ["Stone", "Soil", "Mulch", "Sand"],
            "Pavers And Hardscaping": ["Slabs", "Pavers", "Retaining Walls"],
            "Paving Tools & Equipment": ["Hand Tools", "Compactors"],
            "Paving & Construction Supplies": ["Edging", "Adhesives", "Sealers"]
        },
        "Pet Supplies": {
            "Dogs": ["Food", "Toys", "Bedding"],
            "Cats": ["Food", "Toys", "Litter"]
        },
        "Home And Gift": {
            "Home Decor": ["Candles", "Wall Art", "Statues"]
        },
        "Lawn And Garden": {
            "Garden Tools": ["Shovels", "Pruners"],
            "Garden Supplies": ["Fertilizers", "Planters"]
        }
    }


@pytest.fixture
def sample_ai_response():
    """Sample AI API response with taxonomy, weight, and purchase options."""
    return {
        "department": "Landscape and Construction",
        "category": "Pavers and Hardscaping",
        "subcategory": "Slabs",
        "reasoning": "Concrete paver slab for outdoor hardscaping",
        "weight_estimation": {
            "original_weight": 0,
            "product_weight": 39.0,
            "product_packaging_weight": 3.9,
            "shipping_packaging_weight": 5.0,
            "calculated_shipping_weight": 47.9,
            "final_shipping_weight": 52.7,
            "confidence": "high",
            "source": "calculated_from_dimensions",
            "reasoning": "Calculated from dimensions 20×10×2.25 inches"
        },
        "purchase_options": [1, 2],
        "needs_review": False
    }


# ============================================================================
# TEMPORARY FILE FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir):
    """Create a temporary config.json file."""
    config_path = temp_dir / "config.json"
    config_data = {
        "SHOPIFY_STORE_URL": "test-store.myshopify.com",
        "SHOPIFY_ACCESS_TOKEN": "test_token_12345",
        "USE_AI_ENHANCEMENT": False,
        "PRODUCT_INPUT_FILE": "",
        "PRODUCT_OUTPUT_FILE": "",
        "COLLECTIONS_OUTPUT_FILE": "",
        "LOG_FILE": str(temp_dir / "test.log")
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=4)
    return config_path


@pytest.fixture
def temp_taxonomy_file(temp_dir, sample_taxonomy):
    """Create a temporary PRODUCT_TAXONOMY.md file."""
    taxonomy_path = temp_dir / "PRODUCT_TAXONOMY.md"

    # Generate markdown content from sample taxonomy
    content = "# Product Taxonomy\n\n"
    for idx, (dept, categories) in enumerate(sample_taxonomy.items(), 1):
        content += f"### {idx}. {dept.upper()}\n\n"
        for category, subcategories in categories.items():
            content += f"#### {category}\n\n"
            for sub_idx, subcat in enumerate(subcategories, 1):
                content += f"  {sub_idx}. **{subcat}** - Options: 1, 3, 5\n"
            content += "\n"

    with open(taxonomy_path, 'w') as f:
        f.write(content)

    return taxonomy_path


@pytest.fixture
def temp_products_json(temp_dir, sample_products):
    """Create temporary products.json file."""
    products_path = temp_dir / "products.json"
    products_data = {
        "products": sample_products,
        "last_updated": "2025-11-12T10:00:00"
    }
    with open(products_path, 'w') as f:
        json.dump(products_data, f, indent=4)
    return products_path


# ============================================================================
# MOCK API FIXTURES
# ============================================================================

@pytest.fixture
def mock_shopify_product_create():
    """Mock successful Shopify product create response."""
    return {
        "data": {
            "productCreate": {
                "product": {
                    "id": "gid://shopify/Product/7891234567890",
                    "title": "Test Product"
                },
                "userErrors": []
            }
        }
    }


@pytest.fixture
def mock_shopify_variant_create():
    """Mock successful Shopify variant bulk create response."""
    return {
        "data": {
            "productVariantsBulkCreate": {
                "productVariants": [
                    {"id": "gid://shopify/ProductVariant/123", "sku": "TEST-001"}
                ],
                "userErrors": []
            }
        }
    }


@pytest.fixture
def mock_shopify_collection_search():
    """Mock Shopify collection search response."""
    return {
        "data": {
            "collections": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Collection/123456",
                            "title": "Test Collection",
                            "handle": "test-collection"
                        }
                    }
                ]
            }
        }
    }


@pytest.fixture
def mock_openai_response(sample_ai_response):
    """Mock OpenAI API response."""
    class MockResponse:
        def __init__(self):
            self.id = "chatcmpl-test123"
            self.model = "gpt-4o"
            self.choices = [
                type('obj', (object,), {
                    'message': type('obj', (object,), {
                        'content': json.dumps(sample_ai_response)
                    }),
                    'finish_reason': 'stop'
                })
            ]
            self.usage = type('obj', (object,), {
                'prompt_tokens': 500,
                'completion_tokens': 200,
                'total_tokens': 700
            })

    return MockResponse()


# ============================================================================
# PATH FIXTURES
# ============================================================================

@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def uploader_modules_path(project_root):
    """Get uploader_modules directory path."""
    return project_root / "uploader_modules"


# ============================================================================
# MONKEYPATCH FIXTURES FOR STATE FILES
# ============================================================================

@pytest.fixture
def mock_state_files(monkeypatch, temp_dir):
    """Mock all state file paths to use temp directory."""
    import uploader_modules.state as state_module

    monkeypatch.setattr(state_module, 'STATE_FILE', str(temp_dir / 'upload_state.json'))
    monkeypatch.setattr(state_module, 'COLLECTIONS_FILE', str(temp_dir / 'collections.json'))
    monkeypatch.setattr(state_module, 'PRODUCTS_FILE', str(temp_dir / 'products.json'))
    monkeypatch.setattr(state_module, 'TAXONOMY_FILE', str(temp_dir / 'product_taxonomy.json'))

    return temp_dir


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def capture_logs(caplog):
    """Capture log output for testing."""
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def mock_status_fn():
    """Mock status function that collects status messages."""
    messages = []

    def status_fn(msg):
        messages.append(msg)

    status_fn.messages = messages
    return status_fn
