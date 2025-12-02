# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python application for uploading products to Shopify using the GraphQL Admin API (2025-10). It handles products with variants, images, 3D models, metafields, and automated collection creation.

**Entry Points:**
- `main.py` - CLI entry point (command-line interface)
- `gui.py` - GUI entry point (graphical interface)

**Current Version:** 2.6.0
**API Version:** Shopify GraphQL Admin API 2025-10

**Important**: This tool expects PRE-CATEGORIZED product data from the categorizer project. Products should arrive with:
- Taxonomy already assigned (`product_type`, `tags`)
- Descriptions already rewritten (`body_html`)
- Weights already estimated (`weight` field)

The uploader focuses purely on Shopify upload operations and does not perform any content enhancement or categorization.

## 🚨 CRITICAL: Development Standards

**BEFORE writing or modifying ANY code, you MUST:**

### 1. Follow Shared Documentation Standards

This project follows organization-wide Python development standards located at:
```
/Users/moosemarketer/Code/shared-docs/python/
```

**Required Reading:**
- `COMPLIANCE_CHECKLIST.md` - Complete standards checklist
- `PROJECT_STRUCTURE_REQUIREMENTS.md` - Directory and file structure
- `LOGGING_REQUIREMENTS.md` - Logging patterns and standards
- `GRAPHQL_OUTPUT_REQUIREMENTS.md` - API output format requirements
- `GUI_DESIGN_REQUIREMENTS.md` - GUI design patterns (if applicable)
- `GIT_WORKFLOW.md` - Git commit and branching standards

**Before ANY code changes:**
1. Read relevant standards from shared-docs
2. Verify compliance with existing patterns
3. Update this CLAUDE.md if new patterns are established

### 2. Use Context7 for Library Documentation

When working with external libraries (Shopify API, requests, ttkbootstrap, etc.), you MUST use the Context7 MCP tools to fetch current documentation:

**Available Context7 Tools:**
- `mcp__context7__resolve-library-id` - Find the correct library ID
- `mcp__context7__get-library-docs` - Fetch up-to-date docs

**Example workflow:**
```
1. User asks to implement Shopify GraphQL mutation
2. Use resolve-library-id to find Shopify library
3. Use get-library-docs to fetch Shopify GraphQL docs
4. Implement using current API patterns from docs
5. Never guess API signatures or parameter names
```

**Why Context7 is mandatory:**
- Ensures code uses current API versions
- Prevents deprecated pattern usage
- Reduces bugs from outdated assumptions
- Provides accurate type signatures

### 3. Project-Specific Requirements

**Input Data Expectations:**
- Products arrive from categorizer project with taxonomy, descriptions, and weights already assigned
- Taxonomy structure follows 3-level hierarchy (Department → Category → Subcategory)
- All weights should include packaging estimates
- Product data should be complete and ready for upload

**Collection Structure:**
- Department level: Based on `product_type` field
- Category level: Based on primary tag
- Subcategory level: Based on compound tag rules

## Development Commands

### Running the Application

**GUI Mode:**
```bash
python3 gui.py
```

**CLI Mode:**
```bash
python3 main.py --input products.json --output results.json
python3 main.py --input products.json --output results.json --mode overwrite --verbose
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

## Git Workflow Preference

**Commit Strategy:** Proactive (Option 2)

When making changes to this project:
1. ✅ Make the code changes and test them
2. ✅ After completing a significant feature or set of changes, **ASK THE USER**: "Would you like me to commit and push these changes to GitHub?"
3. ⏸️ Wait for user approval before committing
4. ✅ If approved, create a meaningful commit with:
   - Descriptive commit message explaining what was changed and why
   - Group related changes together (don't commit every tiny change separately)
   - Include "🤖 Generated with Claude Code" footer and Co-Authored-By line
5. ✅ Push to GitHub remote: `git@github.com:bigpurplefish/uploader.git`

**What counts as "significant":**
- New feature added (e.g., collection descriptions, new API integration)
- Bug fix completed
- Documentation updates (major changes)
- Refactoring completed
- Multiple related changes that form a cohesive update

**Do NOT auto-commit:**
- Work in progress
- Experimental changes
- Small typo fixes (unless user requests)

**Repository:** https://github.com/bigpurplefish/uploader

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

### Input Data Format

Products should arrive from the categorizer project with the following structure:

**Required Pre-Processing (handled by categorizer)**:
- `product_type`: Department assignment (e.g., "Pet Supplies", "Landscape & Garden")
- `tags`: Array with Category and Subcategory tags (first tag = category, second tag = subcategory)
- `body_html`: Rewritten product description following voice and tone guidelines
- `weight`: Estimated shipping weight including packaging

**Upload Process**:
1. Validate that input data contains required taxonomy fields
2. Create collections based on taxonomy structure
3. Upload products with pre-assigned taxonomy
4. Create variants and metafields
5. Publish to configured sales channels

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
- `requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md`: Complete API compatibility analysis

**Note**: Product taxonomy and voice/tone guidelines are maintained in the categorizer project, as that tool handles content enhancement before upload.

### Data Files
- `config.json`: Application configuration (includes credentials - not committed)
- `upload_state.json`: Processing state (temporary, deleted on completion)
- `collections.json`: Collection registry (persistent)
- `products.json`: Product restore backup (created before uploads)
- `product_taxonomy.json`: Shopify taxonomy cache

### Shopify Theme Files

The `shopify/` directory contains Shopify theme files (Liquid templates, JavaScript, CSS) for debugging and reference. This mirrors the structure found in Shopify Admin → Online Store → Themes → Edit Code.

**Shopify Store URL:** c2280b-es.myshopify.com

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

## Entry Points

**GUI Mode (`gui.py`):**
- Calls `build_gui()` function which creates the tkinter application and enters the event loop
- Uses ttkbootstrap with "darkly" theme
- Thread-safe status updates via queue

**CLI Mode (`main.py`):**
- Uses argparse for command-line argument handling
- Supports `--input`, `--output`, `--mode`, `--verbose` options
- Same processing logic as GUI, different interface

**Sample Input File:**
`/Users/moosemarketer/Library/CloudStorage/GoogleDrive-dave@bigpurplefish.com/My Drive/Big Purple Fish/Clients/Garoppos/Inventory Cleanup/3.5) Voice and Tone/techo_bloc_products.json`

---

## Agent Delegation Strategy

You have access to specialized agents in `.claude/agents/`. **Automatically analyze each request and delegate to the appropriate specialist(s) without asking permission.**

### Available Agents

| Agent | Trigger Keywords | Use For |
|-------|------------------|---------|
| `requirements-analyst` | requirements, specifications, how should, verify against docs | Reading/interpreting requirements before implementation |
| `shopify-api-specialist` | shopify, graphql, mutation, product create, variant, collection, metafield, api error | All Shopify GraphQL API work |
| `gui-specialist` | gui, tkinter, ttkbootstrap, button, entry, tooltip, thread, queue | GUI development and threading |
| `ai-integration-specialist` | openai, claude, gpt, ai enhancement, taxonomy, audience | AI API integration (OpenAI, Claude) |
| `test-writer` | test, pytest, mock, fixture, coverage | Writing and running tests |
| `code-reviewer` | review, check code, verify, before commit | Code review before committing |
| `product-taxonomy-specialist` | taxonomy, category, subcategory, department, collection rules | Product categorization and collections |
| `shopify-theme-specialist` | liquid, theme, template, snippet, section, css | Shopify Liquid theme development |

### Delegation Rules

1. **Analyze the request** - Identify the domain, file types, and technical areas involved
2. **Match to specialists** - Check which agent descriptions match the task
3. **Delegate proactively** - Invoke the specialist automatically, don't ask first
4. **Coordinate multiple agents** - For complex tasks, orchestrate multiple specialists in sequence

### When to Delegate

- Starting new feature → `requirements-analyst` first, then domain specialist
- Shopify API work → `shopify-api-specialist`
- GUI changes → `gui-specialist`
- AI/OpenAI/Claude work → `ai-integration-specialist`
- After implementation → `test-writer` for tests, then `code-reviewer`
- Taxonomy/collections → `product-taxonomy-specialist`
- Theme/Liquid work → `shopify-theme-specialist`

### Orchestration Pattern for Features

For complex feature implementation:

1. **requirements-analyst** reads and clarifies requirements
2. **Domain specialist(s)** implement the feature
3. **test-writer** creates tests
4. **code-reviewer** validates quality

**Never implement Shopify API features without first consulting requirements documents.**

### Slash Commands

Custom commands are available in `.claude/commands/`:

| Command | Purpose |
|---------|---------|
| `/implement-feature` | Requirements-driven feature implementation |
| `/review` | Code review against requirements and standards |
| `/test` | Generate or run tests |
| `/document` | Update documentation |
| `/fix-api-error` | Diagnose and fix Shopify/OpenAI API errors |
| `/add-shopify-mutation` | Add new Shopify GraphQL mutation with proper patterns |
| `/debug-gui` | Diagnose and fix GUI issues |

---

## Quick Reference: Key Requirements Documents

**Always read these before making changes to related areas:**

| Area | Primary Document |
|------|------------------|
| Shopify API | `@requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md` |
| OpenAI/GPT-5 API | `@requirements/OPENAI_API_REQUIREMENTS.md` |
| GUI Design | `@docs/GUI_DESIGN_REQUIREMENTS.md` |
| Product Taxonomy | `@docs/PRODUCT_TAXONOMY.md` |
| Voice & Tone | `@docs/VOICE_AND_TONE_GUIDELINES.md` |
| Audience Feature | `@docs/AUDIENCE_DESCRIPTIONS_FEATURE.md` |
| Shared Standards | `/Users/moosemarketer/Code/shared-docs/python/COMPLIANCE_CHECKLIST.md` |