# Input File Format Requirements

**Version:** 1.0
**Last Updated:** 2025-12-02

This document defines the expected JSON input format for the Shopify Product Uploader.

## File Structure

The input file must be a valid JSON file containing either:
- A JSON array of product objects: `[{product1}, {product2}, ...]`
- A JSON object with a `products` key: `{"products": [{product1}, {product2}, ...]}`

## Product Object Schema

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Product title |
| `descriptionHtml` | string | HTML-formatted product description |
| `vendor` | string | Product vendor/manufacturer name |
| `product_type` | string | Product type (used for department-level collections) |
| `status` | string | Product status: `"ACTIVE"` or `"DRAFT"` |
| `variants` | array | Array of variant objects (at least one required) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `shopify_category_id` | string | Shopify taxonomy category GID (e.g., `"gid://shopify/TaxonomyCategory/ha-1-5"`) |
| `shopify_category` | string | Human-readable category path (e.g., `"Hardware > Building Consumables"`) |
| `tags` | array | Array of tag strings for categorization |
| `options` | array | Array of option objects defining product variants |
| `metafields` | array | Array of product-level metafield objects |
| `images` | array | Array of image objects |

## Options Array Schema

Each option object defines a product variant dimension:

```json
{
  "name": "Color",
  "position": 1,
  "values": ["Red", "Blue", "Green"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Option name (e.g., "Color", "Size", "Unit of Sale") |
| `position` | integer | Display order (1-based) |
| `values` | array | Array of possible values for this option |

## Variant Object Schema

### Required Variant Fields

| Field | Type | Description |
|-------|------|-------------|
| `sku` | string | Stock Keeping Unit identifier |
| `price` | string | Variant price (as string, e.g., `"4.14"`) |
| `option1` | string | Value for first option |

### Optional Variant Fields

| Field | Type | Description |
|-------|------|-------------|
| `option2` | string | Value for second option (if applicable) |
| `option3` | string | Value for third option (if applicable) |
| `cost` | string | Cost of goods (as string) |
| `barcode` | string | Barcode/UPC |
| `compare_at_price` | string/null | Original price for sale display |
| `inventory_quantity` | integer | Stock quantity |
| `inventory_policy` | string | `"deny"` or `"continue"` (sell when out of stock) |
| `inventory_management` | string | `"shopify"` for tracked inventory |
| `taxable` | boolean | Whether variant is taxable |
| `weight` | float | Variant weight |
| `weight_unit` | string | Weight unit: `"lb"`, `"kg"`, `"oz"`, `"g"` |
| `grams` | integer | Weight in grams (alternative to weight/weight_unit) |
| `requires_shipping` | boolean | Whether variant requires shipping |
| `metafields` | array | Array of variant-level metafield objects |

## Metafield Object Schema

Both product and variant metafields use the same structure:

```json
{
  "namespace": "custom",
  "key": "color_swatch_image",
  "value": "https://cdn.shopify.com/...",
  "type": "single_line_text_field"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `namespace` | string | Metafield namespace (typically `"custom"`) |
| `key` | string | Metafield key identifier |
| `value` | string | Metafield value |
| `type` | string | Shopify metafield type |

### Common Metafield Types

- `single_line_text_field` - Short text
- `multi_line_text_field` - Long text
- `boolean` - `"true"` or `"false"` (as string)
- `json` - JSON-formatted string
- `number_integer` - Integer value
- `number_decimal` - Decimal value

### Standard Variant Metafields

| Key | Type | Description |
|-----|------|-------------|
| `color_swatch_image` | single_line_text_field | URL to color swatch image (must be Shopify CDN) |
| `texture_swatch_image` | single_line_text_field | URL to texture swatch image |
| `finish_swatch_image` | single_line_text_field | URL to finish swatch image |
| `model_number` | single_line_text_field | Manufacturer model number |
| `unit_of_sale` | single_line_text_field | Unit of sale description |

### Standard Product Metafields

| Key | Type | Description |
|-----|------|-------------|
| `hide_online_price` | boolean | Hide price on online store |
| `purchase_options` | json | JSON object with purchase options |

## Image Object Schema

```json
{
  "position": 1,
  "src": "https://cdn.shopify.com/s/files/...",
  "alt": "Product image description #Color_Red"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `position` | integer | Display order (1-based) |
| `src` | string | Image URL (must be Shopify CDN URL) |
| `alt` | string | Alt text (may include filter hashtags) |

### Image Alt Text Format

Alt text can include hashtags for variant-specific image filtering:

```
Product Name #Color_Red #Size_Large
```

Format: `#OptionName_OptionValue` (spaces in values replaced with underscores)

## URL Requirements

**All image URLs must be pre-uploaded to Shopify CDN.**

Valid URL patterns:
- `https://cdn.shopify.com/s/files/...`

The uploader validates all URLs before processing and will reject files containing non-Shopify CDN URLs in:
- Product images (`images[].src`)
- Metafields with type `url` or `file_reference`
- Known image metafield keys (`color_swatch_image`, `texture_swatch_image`, `finish_swatch_image`)

## Complete Example

```json
[
  {
    "title": "Example Product",
    "descriptionHtml": "<p>Product description with <strong>HTML</strong> formatting.</p>",
    "vendor": "Brand Name",
    "status": "ACTIVE",
    "product_type": "Category Name",
    "shopify_category_id": "gid://shopify/TaxonomyCategory/xx-1-2",
    "shopify_category": "Category > Subcategory",
    "tags": ["Tag1", "Tag2"],
    "options": [
      {
        "name": "Color",
        "position": 1,
        "values": ["Red", "Blue"]
      },
      {
        "name": "Size",
        "position": 2,
        "values": ["Small", "Large"]
      }
    ],
    "metafields": [
      {
        "namespace": "custom",
        "key": "hide_online_price",
        "value": "true",
        "type": "boolean"
      }
    ],
    "variants": [
      {
        "sku": "PROD-RED-SM",
        "price": "29.99",
        "cost": "15.00",
        "barcode": "123456789",
        "inventory_quantity": 100,
        "position": 1,
        "option1": "Red",
        "option2": "Small",
        "inventory_policy": "deny",
        "inventory_management": "shopify",
        "taxable": true,
        "weight": 1.5,
        "weight_unit": "lb",
        "requires_shipping": true,
        "metafields": [
          {
            "namespace": "custom",
            "key": "model_number",
            "value": "MN-001",
            "type": "single_line_text_field"
          }
        ]
      }
    ],
    "images": [
      {
        "position": 1,
        "src": "https://cdn.shopify.com/s/files/1/xxxx/files/image.jpg",
        "alt": "Product front view #Color_Red"
      }
    ]
  }
]
```

## Legacy Field Support

For backwards compatibility, the following legacy field names are also supported:

| Legacy Field | Current Field | Notes |
|--------------|---------------|-------|
| `body_html` | `descriptionHtml` | Both accepted, `descriptionHtml` preferred |

## Validation Rules

1. **Required fields**: `title`, `variants` (with at least one variant)
2. **URL validation**: All image URLs must be Shopify CDN URLs
3. **Option consistency**: Variant `option1`/`option2`/`option3` must match defined options
4. **Price format**: Prices should be strings (e.g., `"29.99"`)
5. **Weight units**: Must be valid Shopify units (`lb`, `kg`, `oz`, `g`)
