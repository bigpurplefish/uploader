# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python GUI application for uploading products to Shopify using the GraphQL Admin API (2025-10). It handles products with variants, images, 3D models, metafields, and automated collection creation.

**Main Script:** `uploader.py` (~2670 lines)
**Current Version:** 2.6.0
**API Version:** Shopify GraphQL Admin API 2025-10

## Development Commands

### Running the Application
```bash
python3 uploader.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `ttkbootstrap>=1.10.0` - Modern themed tkinter GUI
- `requests>=2.28.0` - HTTP library for API calls

### Setup Script (First Time)
```bash
chmod +x setup.sh
./setup.sh
```
Creates directory structure, installs dependencies, moves docs to proper locations.

## Architecture

### Core Data Flow

```
Input JSON → URL Validation → Collections Processing → Products Processing → Output JSON
                                      ↓                        ↓
                              collections.json         products.json (restore)
                                                              ↓
                                                       upload_state.json
```

### Key Architectural Patterns

1. **Dual State Management**
   - `upload_state.json`: Tracks upload progress for resume capability
   - `products.json`: Full product data restore file (created before any deletions/modifications)
   - Both enable safe recovery from failures

2. **Three-Level Taxonomy Collections**
   - Department level: Based on `product_type` field
   - Category level: Based on primary tag
   - Subcategory level: Based on compound tag rules (parent + subcategory tags)
   - Collections are searched first (by exact title match) to avoid duplicates

3. **Bulk Operations Pattern**
   - Uses `productVariantsBulkCreate` instead of individual variant mutations
   - Reduces API calls by ~70% compared to one-by-one variant creation
   - Single mutation creates all variants for a product at once

4. **Staged Upload for 3D Models**
   - Three-step process: request staged target → upload file → create file record
   - Returns file IDs that are referenced in product media array
   - Images use existing Shopify CDN URLs (pre-uploaded)

5. **GraphQL Error Handling**
   - All mutations return `userErrors` array for validation issues
   - HTTP errors handled separately from GraphQL validation errors
   - Detailed logging at DEBUG level, user-friendly messages in GUI

### Configuration Architecture

**`config.json`** structure:
- System settings: `SHOPIFY_STORE_URL`, `SHOPIFY_ACCESS_TOKEN`
- User settings: File paths for input/output/logs
- Sales channel IDs: `SALES_CHANNEL_ONLINE_STORE`, `SALES_CHANNEL_POINT_OF_SALE`
- Window geometry for UI persistence
- Auto-saved on every field change via `trace_add` callbacks

### State Files

**`upload_state.json`**: Processing checkpoint
- Created when processing starts
- Updated after each product completes
- Deleted on successful completion
- Contains `last_processed_index` and results array

**`collections.json`**: Collection tracking registry
- Persists created collection IDs and handles
- Three-level structure: departments, categories, subcategories
- Prevents duplicate collection creation across runs

**`products.json`**: Full product restore backup
- Created before any product modifications
- Contains complete product data for restoration
- Used by restore functionality if uploads need to be reverted

**`product_taxonomy.json`**: Shopify taxonomy cache
- Caches category → taxonomy ID mappings
- Reduces redundant API calls for taxonomy lookups
- Format: `{"category_name": "gid://shopify/TaxonomyCategory/..."}`

### GUI Architecture

**Framework**: ttkbootstrap with `darkly` theme

**Threading model**:
- Main thread: tkinter event loop
- Worker thread: Processing functions (daemon thread)
- Communication: `app.after()` for thread-safe GUI updates

**Layout pattern**:
- Column 0: Labels with inline tooltip icons
- Column 1: Input fields (expandable)
- Column 2: Browse buttons
- Column 3: Delete buttons
- Tooltips on all input fields

### API Integration Patterns

**Base URL pattern**:
```python
f"https://{SHOPIFY_STORE_URL}/admin/api/2025-10/graphql.json"
```

**Headers**:
```python
{
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
}
```

**Request structure**:
```python
{
    "query": mutation_string,
    "variables": {...}
}
```

## Critical Implementation Details

### Product Creation Flow

The `process_products()` function (line 1346) orchestrates:

1. **Pre-upload validation**: Scan for non-Shopify CDN URLs
2. **Load state**: Check for existing `upload_state.json`
3. **Process each product**:
   - Extract taxonomy (category/subcategory)
   - Search Shopify taxonomy for category ID
   - Upload 3D models if present
   - Build product input with all fields
   - Create product via `productCreate` mutation
   - Publish to sales channels if configured
   - Create variants via `productVariantsBulkCreate`
   - Save state after each product
4. **Generate output**: Write results to output JSON

### Collection Creation Flow

The `process_collections()` function (line 815):

1. **Extract taxonomy** from all products
2. **Department collections**: Create from unique `product_type` values
3. **Category collections**: Create from primary category tags
4. **Subcategory collections**: Create with compound rules (category + subcategory tags)
5. **Search before create**: Check if collection exists by exact title match
6. **Save to `collections.json`**: Persist created collection data

### Variant Creation (Critical)

**Important**: Uses `productVariantsBulkCreate` mutation (API 2025-10):
- Takes array of variant inputs
- All variants created in single API call
- Each variant needs `optionValues` array matching product options
- Metafields attached directly in variant input

### URL Validation

Function: `is_shopify_cdn_url()` (line 1010)

**Critical rule**: All image and metafield URLs must be Shopify CDN URLs (`cdn.shopify.com`)

**Exception**: 3D model URLs in `media[].sources[].url` can be external (script uploads them)

### Taxonomy Integration

Functions: `search_shopify_taxonomy()` (line 1186), `get_taxonomy_id()` (line 1272)

- Searches Shopify's product taxonomy for category matches
- Uses fuzzy matching and hierarchy traversal
- Caches results in `product_taxonomy.json` to reduce API calls
- Falls back gracefully if no match found

### Claude API Integration (AI-Powered Content Enhancement)

**Purpose**: Uses Claude API to automatically assign products to internal taxonomy and rewrite descriptions according to voice and tone guidelines.

**Pre-Processing Steps** (before Shopify upload):

1. **Taxonomy Assignment**:
   - Analyzes product title, existing description, and metadata
   - Assigns Department → stored in `product_type`
   - Assigns Category → stored as first tag
   - Assigns Subcategory → stored as second tag
   - Follows structure defined in `docs/PRODUCT_TAXONOMY.md`

2. **Description Rewriting**:
   - Rewrites `body_html` content using voice and tone guidelines
   - Applies department-specific tone (Pet Supplies: empathetic, Landscape: professional, etc.)
   - Ensures second-person voice and imperative-first phrasing
   - Maintains uniqueness across similar products (no 7+ word repetitions)
   - Follows standards in `docs/VOICE_AND_TONE_GUIDELINES.md`

**Configuration**:
- `CLAUDE_API_KEY`: Stored in `config.json`
- `CLAUDE_MODEL`: Model version (e.g., "claude-3-5-sonnet-20241022")
- Enable/disable via GUI checkbox: "Use Claude AI for taxonomy and descriptions"

**API Flow**:
```
Input Product → Claude API Call → Enhanced Product → Shopify Upload
                     ↓
              (taxonomy + rewritten description)
```

**Benefits**:
- Consistent taxonomy across all products
- Professional, on-brand product descriptions
- Reduced manual categorization effort
- Improved SEO and customer experience

## Common Development Patterns

### Adding New Shopify Mutations

1. Define mutation string with typed parameters
2. Build variables object matching input types
3. Call API with `requests.post()`
4. Check for `userErrors` in response
5. Log response at DEBUG level
6. Handle errors gracefully, continue processing

### Modifying Product Input Structure

**Key constraint**: Must match `ProductCreateInput` type in API 2025-10

Critical fields:
- `title` (String, required)
- `descriptionHtml` (String, replaces deprecated `bodyHTML`)
- `productType` (String, used for department collections)
- `tags` ([String!], used for category collections)
- `productOptions` ([ProductOptionInput!], replaces deprecated `options`)
- `category` (String, Shopify taxonomy ID from search)

### Extending Collection Logic

Current structure in `process_collections()`:

1. Department rules: `PRODUCT_TYPE EQUALS <department>`
2. Category rules: `TAG EQUALS <category>`
3. Subcategory rules: `TAG EQUALS <category>` AND `TAG EQUALS <subcategory>`

To add new levels: Add rules array to `create_collection()` call with appropriate column/relation/condition.

### Working with State Files

**Resume pattern**:
```python
state = load_state()
start_index = state.get("last_processed_index", -1) + 1
# Process from start_index
# After each product:
save_state({"last_processed_index": index, "results": [...]})
```

**Restore pattern**:
```python
products_restore = load_products()  # From products.json
# Use products_restore for restoration operations
```

## Testing Guidelines

### Manual Testing Workflow

1. **Small batch test** (5-10 products):
   - Verify all mutations work
   - Check collections created correctly
   - Verify variants and metafields

2. **Interrupt test**:
   - Stop processing mid-batch
   - Restart, verify resume from correct point
   - Check no duplicate products/collections

3. **URL validation test**:
   - Include non-CDN URL in test data
   - Verify script stops before processing

4. **3D model test**:
   - Include GLB/USDZ media
   - Verify staged upload works
   - Check files appear in Shopify

### API Version Testing

When Shopify releases new API versions:
1. Change API URL: `/admin/api/YYYY-MM/graphql.json`
2. Review Shopify changelog for breaking changes
3. Test all mutations (product, variant, collection, file)
4. Update `SHOPIFY_API_2025-10_REQUIREMENTS.md`

## Important Files Reference

### Documentation
- `docs/README.md`: User guide and feature overview
- `docs/TECHNICAL_DOCS.md`: Architecture and design decisions
- `docs/QUICK_START.md`: Getting started guide
- `docs/PRODUCT_TAXONOMY.md`: Internal product taxonomy structure and mapping rules
- `docs/VOICE_AND_TONE_GUIDELINES.md`: Content standards for product descriptions
- `requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md`: Complete API compatibility analysis

### Data Files
- `config.json`: Application configuration (includes credentials - not committed)
- `upload_state.json`: Processing state (temporary, deleted on completion)
- `collections.json`: Collection registry (persistent)
- `products.json`: Product restore backup (created before uploads)
- `product_taxonomy.json`: Shopify taxonomy cache

### Shopify Theme Files

The `shopify/` directory contains Shopify theme files (Liquid templates, JavaScript, CSS) for debugging and reference. This mirrors the structure found in Shopify Admin → Online Store → Themes → Edit Code.

**Directory structure**:
```
shopify/
├── assets/          - JavaScript, CSS, images, fonts
├── config/          - Theme settings schema files
├── layout/          - Base theme templates (theme.liquid)
├── locales/         - Translation files (JSON)
├── sections/        - Reusable page sections (.liquid)
├── snippets/        - Reusable code snippets (.liquid)
└── templates/       - Page templates (.liquid, .json)
```

**Purpose**:
- Debug product gallery image filtering issues
- Review Liquid code for alt tag hashtag filtering logic
- Analyze JavaScript that shows/hides images based on variant selection
- Reference when troubleshooting theme-specific behavior

**Key files for image filtering**:
- `sections/` - Product page sections with image gallery markup
- `snippets/` - Image filtering and variant selection snippets
- `assets/` - JavaScript implementing multi-option filtering logic

## Known Constraints

1. **API Rate Limits**: Script includes 0.5s delays between products. GraphQL uses cost-based limiting.

2. **Memory Usage**: Entire input JSON loaded into memory. Fine for <10,000 products.

3. **Image URLs**: Must be pre-uploaded to Shopify CDN. Script doesn't upload images (only 3D models).

4. **Variant Limits**: Shopify limits products to 100 variants per product.

5. **API Version Support**: 2025-10 supported until October 2026. Plan to upgrade when new stable versions release.

6. **Sales Channel Publishing**: Requires channel IDs in config. Script publishes after product creation if configured.

## Shopify API Specifics

### API 2025-10 Changes

- Uses `ProductCreateInput` (not deprecated `ProductInput`)
- Parameter name is `product` (not `input`)
- Uses `descriptionHtml` (not `bodyHTML`)
- Uses `productOptions` (not `options`)
- Uses `productVariantsBulkCreate` for all variant operations

### GraphQL Mutation Signatures

**Product**:
```graphql
mutation productCreate($product: ProductCreateInput!, $media: [CreateMediaInput!])
```

**Variants**:
```graphql
mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!)
```

**Collections**:
```graphql
mutation collectionCreate($input: CollectionInput!)
```

**Staged Upload**:
```graphql
mutation stagedUploadsCreate($input: [StagedUploadInput!]!)
mutation fileCreate($files: [FileCreateInput!]!)
```

## Entry Point

Main execution starts at line 2247: `build_gui()` function creates the tkinter application and enters the event loop.
- The sample input file is located here: /Users/moosemarketer/Library/CloudStorage/GoogleDrive-dave@bigpurplefish.com/My\ Drive/Big\ Purple\ Fish/Clients/Garoppos/Inventory\ Cleanup/3.5\)\ Voice\ and\ Tone/techo_bloc_products.json