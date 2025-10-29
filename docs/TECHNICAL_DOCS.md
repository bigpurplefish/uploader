# Shopify Product Uploader - Technical Documentation

## Architecture Overview

This document provides technical details about the script's architecture, design decisions, and implementation details.

## Core Components

### 1. Configuration Management

**File**: `config.json` (auto-created)

**Purpose**: Stores all application settings including credentials and user preferences.

**Structure**:
```json
{
  "_SYSTEM SETTINGS": "Credentials and system-level config",
  "SHOPIFY_STORE_URL": "Store URL",
  "SHOPIFY_ACCESS_TOKEN": "API access token",
  "_USER SETTINGS": "User-specified file paths",
  "INPUT_FILE": "Path to input JSON",
  "OUTPUT_FILE": "Path to output JSON",
  "LOG_FILE": "Path to log file",
  "WINDOW_GEOMETRY": "Window size/position"
}
```

**Features**:
- Auto-save on every field change (using trace_add)
- Persistent across sessions
- Window geometry saved on exit

### 2. State Management

**File**: `upload_state.json` (auto-created during processing)

**Purpose**: Tracks processing progress for resume capability.

**Structure**:
```json
{
  "last_processed_index": 5,
  "results": [
    {
      "product_index": 0,
      "product_title": "Product Name",
      "success": true,
      "shopify_product_id": "gid://shopify/Product/123",
      "error": null,
      "processed_at": "2025-10-25T14:30:00"
    }
  ]
}
```

**Behavior**:
- Created on first product processing
- Updated after each product
- Deleted on successful completion
- Enables resume after interruption

### 3. Logging System

**Three-Level Logging Architecture**:

1. **File Logging (DEBUG)**:
   - Complete API requests/responses
   - Full error traces
   - Detailed processing steps
   - Format: `TIMESTAMP | LEVEL | LOGGER | MESSAGE`

2. **Console Logging (INFO)**:
   - Important events
   - Warnings and errors
   - Progress updates
   - Format: `TIMESTAMP | LEVEL | MESSAGE`

3. **UI Status Field**:
   - User-friendly messages
   - Simplified progress indicators
   - No technical details
   - Auto-scroll to bottom

**Implementation**:
```python
def log_and_status(status_fn, msg, level="info", ui_msg=None):
    # Simplifies technical messages for UI
    # Logs full details to file and console
    # Handles three outputs simultaneously
```

### 4. GUI Design

**Framework**: ttkbootstrap (modern themed tkinter)

**Theme**: `darkly` (dark mode)

**Layout Standards** (from GUI_DESIGN_REQUIREMENTS.md):
- Grid layout for forms (labels, entries, buttons in columns)
- Pack layout for buttons and status field
- Tooltips on ALL input fields
- Auto-save configuration
- Non-blocking threading for processing

**Required Components** (per design requirements):
- ✅ Log File field with Browse and Delete buttons
- ✅ Status field (100 lines minimum, cleared on start)
- ✅ Validate Settings button
- ✅ Start Processing button
- ✅ Exit button
- ✅ Settings dialog for credentials
- ✅ Menu option for Settings
- ✅ Toolbar button for Settings (⚙️)
- ✅ config.json file with auto-save
- ✅ Tooltips with friendly, jargon-free text

**Field Layout Pattern**:
```
Column 0: Labels with inline tooltip icons
Column 1: Input widgets (expandable)
Column 2: Action buttons (Browse)
Column 3: Additional buttons (Delete)
```

### 5. URL Validation

**Purpose**: Ensure all URLs (except media sources) are Shopify CDN URLs.

**Implementation**:
```python
def is_shopify_cdn_url(url):
    # Checks for 'cdn.shopify.com' in URL
    return 'cdn.shopify.com' in parsed.netloc

def scan_for_non_shopify_urls(products):
    # Scans all URLs in products
    # Excludes media.sources URLs (uploaded by script)
    # Returns list of issues found
```

**Checked Locations**:
- Product images (`images[].src`)
- Variant metafields (all types)
- Product metafields (including JSON arrays)

**Exception**: Media sources in `media[].sources[].url` are allowed to be external URLs because the script uploads them.

### 6. Shopify API Integration

**API Version**: 2024-01

**Protocol**: GraphQL Admin API

**Authentication**: Custom Access Token header

**Required Scopes**:
- `write_products` - Create products and variants
- `write_files` - Upload 3D models

#### API Workflows

**A. Upload 3D Model**:
```
1. Download model from external URL
2. Request staged upload target from Shopify
3. PUT model data to staged target
4. Create file record in Shopify
5. Return file ID for product association
```

**B. Create Product**:
```
1. Upload 3D models (if present)
2. Prepare product input (title, description, options, etc.)
3. Prepare media input (images + model file IDs)
4. Execute productCreate mutation
5. Return product ID
```

**C. Create Variants**:
```
For each variant:
1. Prepare variant input (SKU, price, options, etc.)
2. Add variant metafields
3. Execute productVariantCreate mutation
4. Log success/failure
```

#### GraphQL Mutations Used

1. **stagedUploadsCreate**: Prepare upload target for files
2. **fileCreate**: Register uploaded file in Shopify
3. **productCreate**: Create product with media
4. **productVariantCreate**: Create product variant

### 7. Processing Flow

```
START
  ↓
Load Configuration
  ↓
Validate Inputs (Validate Settings button)
  ↓
Load Input JSON
  ↓
Scan for Non-Shopify URLs
  ↓
[IF URLs FOUND] → Stop Processing
  ↓
Load Processing State (resume support)
  ↓
FOR EACH PRODUCT:
  ↓
  Upload 3D Models (if present)
  ↓
  Create Product (with images)
  ↓
  Create Variants (with metafields)
  ↓
  Save State (resume point)
  ↓
NEXT PRODUCT
  ↓
Generate Output JSON
  ↓
Delete State File
  ↓
Complete
```

### 8. Error Handling

**Levels of Error Handling**:

1. **Validation Errors** (before processing):
   - Missing required fields
   - Non-existent files
   - Missing credentials
   - Action: Show messagebox, don't start

2. **URL Validation Errors** (early stop):
   - Non-Shopify CDN URLs found
   - Action: Log all issues, stop processing

3. **API Errors** (during processing):
   - HTTP errors (timeout, 4xx, 5xx)
   - GraphQL errors
   - User errors from Shopify
   - Action: Log error, mark product as failed, continue

4. **Fatal Errors** (unexpected exceptions):
   - File I/O errors
   - JSON parsing errors
   - Action: Log with full trace, stop processing, state saved

**Resume Capability**:
- State saved after each product
- Automatic resume on next run
- No duplicate uploads

### 9. Thread Safety

**Main Thread**: GUI event loop (tkinter)

**Worker Thread**: Processing function (daemon thread)

**Thread Communication**:
- Status updates via `app.after(0, lambda: ...)` for thread-safe GUI updates
- No shared mutable state
- Configuration read-only during processing

**UI Locking**:
- Buttons disabled during processing
- Re-enabled in finally block
- Prevents concurrent processing

### 10. Data Structures

**Input Format**:
```json
{
  "products": [
    {
      "title": "string",
      "body_html": "string",
      "vendor": "string",
      "product_type": "string",
      "product_category": "string",
      "tags": "string",
      "published": boolean,
      "options": [
        {
          "name": "string",
          "position": number,
          "values": ["string"]
        }
      ],
      "variants": [
        {
          "sku": "string",
          "price": "string",
          "option1": "string",
          "option2": "string",
          "option3": "string",
          "barcode": "string",
          "weight": number,
          "weight_unit": "string",
          "metafields": [
            {
              "namespace": "string",
              "key": "string",
              "value": "string",
              "type": "string"
            }
          ]
        }
      ],
      "images": [
        {
          "position": number,
          "src": "string (Shopify CDN URL)",
          "alt": "string"
        }
      ],
      "media": [
        {
          "media_content_type": "MODEL_3D",
          "sources": [
            {
              "url": "string (external URL OK)",
              "format": "string",
              "mime_type": "string"
            }
          ]
        }
      ],
      "metafields": [...]
    }
  ]
}
```

**Output Format**:
```json
{
  "processed_at": "ISO timestamp",
  "total_products": number,
  "successful": number,
  "failed": number,
  "products": [
    {
      "...": "original product data",
      "_processing_status": {
        "success": boolean,
        "shopify_product_id": "string or null",
        "error": "string or null",
        "processed_at": "ISO timestamp or null"
      }
    }
  ]
}
```

## Design Decisions

### Why GraphQL instead of REST?

**Advantages**:
- Single request for product + media + options
- Precise field selection
- Better error handling with userErrors
- Modern API with ongoing support

**Trade-offs**:
- More complex mutation structure
- Requires understanding of GraphQL
- Larger request payloads

**Decision**: Use GraphQL for future-proofing and efficiency.

### Why Staged Uploads for Models?

**Shopify Requirement**: 3D models must be uploaded via staged uploads (cannot use direct URLs in productCreate).

**Process**:
1. Request staged target
2. Upload to Google Cloud Storage
3. Register file in Shopify

**Why Not for Images?**: Images already on Shopify CDN (pre-uploaded by upscaler.py), so we just reference them.

### Why Separate State File?

**Purpose**: Enable resume without modifying input file.

**Benefits**:
- Input file remains pristine
- Can retry multiple times
- State deleted on success (clean)

**Alternative Considered**: Modify input file with status - rejected because:
- Mutates source data
- Harder to restart from scratch
- Mixing data with state

### Why Three-Level Logging?

**Rationale**:
- **File**: Complete audit trail for debugging
- **Console**: Developer monitoring during execution
- **UI**: User-friendly progress updates

**Benefits**:
- Users see simple messages
- Developers see technical details
- Full history preserved in file

### Why Auto-Save Configuration?

**User Experience**: Changes saved immediately, no "Save" button needed.

**Implementation**: trace_add on StringVar/BooleanVar triggers save_config().

**Trade-off**: More disk I/O, but negligible impact and better UX.

## Performance Considerations

### API Rate Limits

**Shopify Limits**:
- GraphQL: 1000 points per second
- Calculated based on query complexity
- 50 points per product (typical)
- ~20 products per second theoretical max

**Script Behavior**:
- 0.5 second delay between products
- ~2 products per second
- Well below rate limits
- Can be adjusted if needed

### Memory Usage

**Bottleneck**: Loading entire JSON into memory.

**Current Approach**: Fine for <10,000 products.

**Future Enhancement**: Streaming JSON parser for huge files.

### Network Bandwidth

**Upload Sizes**:
- 3D models: 1-5 MB each
- API requests: 10-50 KB each

**Considerations**:
- Models downloaded then uploaded (2x bandwidth)
- Could optimize with direct transfer (future)

## Testing Recommendations

### Unit Testing

```python
# Test URL validation
def test_is_shopify_cdn_url():
    assert is_shopify_cdn_url("https://cdn.shopify.com/...")
    assert not is_shopify_cdn_url("https://example.com/...")

# Test state management
def test_state_save_load():
    state = {"last_processed_index": 5}
    save_state(state)
    loaded = load_state()
    assert loaded["last_processed_index"] == 5
```

### Integration Testing

1. **Small Batch Test**: 3-5 products
2. **Variant Test**: Product with multiple variants
3. **3D Model Test**: Product with GLB/USDZ models
4. **Resume Test**: Interrupt and resume
5. **Error Test**: Invalid credentials, bad data

### Load Testing

- Test with 100+ products
- Monitor memory usage
- Check API rate limit behavior
- Verify state persistence

## Security Considerations

### Credential Storage

**Current**: Plain text in config.json

**Considerations**:
- File permissions: 600 (user read/write only)
- Should not be committed to version control
- Add .gitignore for config.json

**Future Enhancement**: Encrypted credential storage

### API Token Permissions

**Principle of Least Privilege**:
- Only grant required scopes: `write_products`, `write_files`
- Don't use admin-level tokens
- Rotate tokens periodically

### Input Validation

**XSS Prevention**:
- All HTML in body_html passed as-is to Shopify
- Shopify handles sanitization
- No additional escaping needed

**Injection Prevention**:
- No SQL or shell commands executed
- GraphQL queries are parameterized
- Safe from injection attacks

## Maintenance and Updates

### Shopify API Version Updates

**Current**: 2024-01

**When to Update**:
- New API version released
- Current version deprecated
- New features needed

**How to Update**:
1. Change API URL: `/admin/api/YYYY-MM/graphql.json`
2. Review breaking changes in Shopify docs
3. Test thoroughly before deployment

### Adding New Features

**Product Categories**:
- Already supported via `product_category` field
- Maps to Shopify's product taxonomy

**Gift Cards**:
- Requires different productCreate mutation
- Check `product_type` and use appropriate mutation

**Bundles/Kits**:
- Requires Shopify Plus
- Different GraphQL structure
- Major enhancement needed

### Logging Enhancements

**Future Ideas**:
- Email notifications on completion
- Slack/Discord webhooks
- Progress percentage calculation
- Estimated time remaining

## Troubleshooting Guide for Developers

### Common Issues

1. **"No files data returned from Shopify"**
   - Check: API scopes include `write_files`
   - Check: File upload successful (200 status)
   - Check: GraphQL mutation syntax

2. **Variants not created**
   - Check: Option values match product options
   - Check: SKUs are unique
   - Check: Price is valid decimal string

3. **Models not appearing**
   - Check: Files uploaded successfully
   - Check: File IDs in product media
   - Shopify may process asynchronously (check later)

4. **State not loading**
   - Check: upload_state.json exists
   - Check: JSON is valid
   - Check: File permissions

### Debugging Tips

1. **Enable verbose logging**:
   ```python
   logging.root.setLevel(logging.DEBUG)
   ```

2. **Inspect API responses**:
   - Already logged at INFO level
   - Check log file for full JSON responses

3. **Test GraphQL queries**:
   - Use Shopify GraphQL Explorer
   - Verify mutations work manually
   - Copy query from logs

4. **Check Shopify Admin**:
   - Products created but invisible?
   - Check product status (draft vs published)
   - Check variant inventory

## Future Enhancements

### Priority 1 (High Value)

1. **Bulk Operations API**:
   - Use Shopify's bulk operations for large batches
   - Faster than individual mutations
   - Requires different approach

2. **Image Position Mapping**:
   - Associate variants with specific images
   - Use `image_id` from input data
   - Requires querying created product

3. **Inventory Management**:
   - Set initial inventory quantities
   - Configure inventory locations
   - Track inventory changes

### Priority 2 (Quality of Life)

1. **Dry Run Mode**:
   - Validate without creating
   - Preview what would be created
   - Estimate time and API calls

2. **Progress Bar**:
   - Visual progress indicator
   - Percentage complete
   - Estimated time remaining

3. **Export Templates**:
   - Generate empty input JSON template
   - Include all possible fields
   - With example values

### Priority 3 (Advanced Features)

1. **Update Existing Products**:
   - Match by SKU or handle
   - Update instead of create
   - Conflict resolution

2. **Product Relationships**:
   - Related products
   - Upsells/cross-sells
   - Requires additional metafields

3. **Multi-Language Support**:
   - Translate product data
   - Multiple languages in one upload
   - Requires Shopify Markets

## Conclusion

This script provides a robust, user-friendly solution for uploading products to Shopify with comprehensive error handling, resume capability, and detailed logging. It follows modern GUI design standards and leverages Shopify's GraphQL API for efficient product creation.

The architecture is modular and maintainable, with clear separation of concerns between configuration, state management, logging, GUI, and API integration. Future enhancements can be added incrementally without major refactoring.
