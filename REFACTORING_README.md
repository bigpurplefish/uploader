# Shopify Product Uploader - Refactored Structure

## Overview

The Shopify Product Uploader has been refactored from a single monolithic file (`uploader.py` - 3434 lines) into a well-organized modular package structure for better maintainability, testability, and code organization.

## New File Structure

```
uploader/
├── uploader_modules/           # Main package directory
│   ├── __init__.py            # Package initialization
│   ├── config.py              # Configuration and logging management
│   ├── state.py               # State file management (JSON files)
│   ├── utils.py               # Utility functions
│   ├── shopify_api.py         # Shopify GraphQL API operations
│   ├── product_processing.py  # Product and collection processing logic
│   └── gui.py                 # Tkinter/ttkbootstrap GUI implementation
├── uploader_new.py            # New simplified main entry point
├── uploader_original.py       # Backup of original monolithic file
├── extract_api_functions.py   # Extraction script (can be deleted)
├── extract_processing_functions.py  # Extraction script (can be deleted)
├── extract_gui.py             # Extraction script (can be deleted)
└── [other existing files...]
```

## Module Descriptions

### 1. `config.py` - Configuration & Logging
**Functions:**
- `load_config()` - Load configuration from config.json
- `save_config(config)` - Save configuration to config.json
- `setup_logging(log_path, level)` - Configure file and console logging
- `install_global_exception_logging()` - Set up global exception handler
- `log_and_status(status_fn, msg, level, ui_msg)` - Log to file, console, and GUI

**Responsibilities:**
- Configuration file (config.json) management
- Logging setup and management
- Exception handling configuration
- Cross-cutting logging utility for UI updates

### 2. `state.py` - State File Management
**Functions:**
- `load_state()` / `save_state(state)` - Upload state (upload_state.json)
- `load_collections()` / `save_collections(data)` - Collections tracking (collections.json)
- `load_products()` / `save_products(data)` - Products restore point (products.json)
- `load_taxonomy_cache()` / `save_taxonomy_cache(cache)` - Taxonomy cache (product_taxonomy.json)
- `update_product_in_restore(restore, product)` - Update product in restore data

**Responsibilities:**
- All JSON state file operations
- Resume capability data
- Collection and product tracking
- Taxonomy caching

### 3. `utils.py` - Utility Functions
**Functions:**
- `is_shopify_cdn_url(url)` - Validate Shopify CDN URLs
- `key_to_label(key)` - Convert metafield keys to human-readable labels
- `extract_category_subcategory(product)` - Extract collection taxonomy from products
- `extract_unique_option_values(product)` - Extract variant options from products

**Responsibilities:**
- URL validation
- Data extraction and transformation
- String formatting utilities
- Product data parsing

### 4. `shopify_api.py` - Shopify API Operations
**Functions (10 total):**
- `get_sales_channel_ids(cfg)` - Retrieve sales channel publication IDs
- `publish_collection_to_channels(collection_id, channel_ids, cfg)` - Publish collections
- `publish_product_to_channels(product_id, channel_ids, cfg)` - Publish products
- `delete_shopify_product(product_id, cfg)` - Delete products
- `search_collection(name, cfg)` - Search for collections by name
- `create_collection(name, rules, cfg)` - Create automated collections
- `create_metafield_definition(namespace, key, type, owner, cfg, pin, status_fn)` - Create metafield definitions
- `upload_model_to_shopify(model_url, filename, cfg, status_fn)` - Upload 3D models (GLB/USDZ)
- `search_shopify_taxonomy(category_name, api_url, headers, status_fn)` - Search product taxonomy
- `get_taxonomy_id(category_name, cache, api_url, headers, status_fn)` - Get/cache taxonomy IDs

**Responsibilities:**
- All Shopify GraphQL API interactions
- Authentication and request handling
- API error handling and logging
- 3D model upload workflow

### 5. `product_processing.py` - Business Logic
**Functions (3 major):**
- `process_collections(products, cfg, status_fn)` - Create department/category/subcategory collections
- `ensure_metafield_definitions(products, cfg, status_fn)` - Auto-create metafield definitions
- `process_products(cfg, status_fn, execution_mode)` - Main product upload orchestration

**Responsibilities:**
- Collection creation workflow
- Product upload workflow
- Metafield definition management
- Resume and overwrite modes
- Integration of all API operations

### 6. `gui.py` - GUI Implementation
**Functions:**
- `build_gui()` - Main GUI construction and event loop

**Responsibilities:**
- Tkinter/ttkbootstrap GUI layout
- Settings dialog
- File browser dialogs
- Input field management
- Status log display
- Threading for background processing
- Button states and event handlers

## How to Use the Refactored Version

### Running the Application

**Option 1: Use the new entry point (recommended)**
```bash
python3 uploader_new.py
```

**Option 2: Import and run programmatically**
```python
from uploader_modules.gui import build_gui

if __name__ == "__main__":
    build_gui()
```

### Importing Specific Modules

```python
# Configuration
from uploader_modules.config import load_config, setup_logging, log_and_status

# State management
from uploader_modules.state import load_state, save_state, load_products

# API operations
from uploader_modules.shopify_api import create_collection, upload_model_to_shopify

# Processing logic
from uploader_modules.product_processing import process_products, process_collections

# Utilities
from uploader_modules.utils import extract_category_subcategory, key_to_label
```

## Benefits of Refactoring

### 1. **Maintainability**
- Each module has a single, well-defined responsibility
- Easier to locate and modify specific functionality
- Reduced coupling between components

### 2. **Testability**
- Individual modules can be unit tested in isolation
- Mock dependencies easily for testing
- Clear interfaces between modules

### 3. **Readability**
- Smaller, focused files (largest module is ~850 lines vs original 3434)
- Clear naming and organization
- Better documentation structure

### 4. **Reusability**
- API functions can be used independently
- Utilities can be reused in other projects
- Processing logic separated from UI

### 5. **Collaboration**
- Multiple developers can work on different modules simultaneously
- Reduced merge conflicts
- Easier code reviews (review module by module)

## Module Dependencies

```
uploader_new.py
    └── gui.py
        ├── config.py
        └── product_processing.py
            ├── config.py (log_and_status, setup_logging)
            ├── state.py (all state functions)
            ├── shopify_api.py (all API functions)
            └── utils.py (extraction and formatting functions)

shopify_api.py
    ├── config.py (log_and_status)
    ├── state.py (save_taxonomy_cache)
    └── utils.py (key_to_label)
```

## Migration Notes

### For Users
- **No action required**: The new `uploader_new.py` works identically to the original
- All existing configuration files (config.json, etc.) remain compatible
- GUI looks and behaves exactly the same

### For Developers
- The original `uploader.py` has been backed up as `uploader_original.py`
- Extraction scripts (`extract_*.py`) can be deleted after verification
- All tests should be updated to import from `uploader_modules`

## Testing the Refactored Version

### Import Tests
```bash
# Test all modules import successfully
python3 -c "from uploader_modules import config, state, utils, shopify_api, product_processing, gui; print('All modules OK')"
```

### Functional Tests
1. Run the new entry point: `python3 uploader_new.py`
2. Verify GUI loads correctly
3. Test a small product upload (5-10 products)
4. Verify collections are created
5. Test resume functionality
6. Test metafield creation

## Future Improvements

1. **Add unit tests** for each module
2. **Add type hints** throughout the codebase
3. **Create async API module** for better performance
4. **Separate GUI components** into smaller files (dialogs, widgets, etc.)
5. **Add CLI interface** as alternative to GUI
6. **Create setup.py** for proper package installation

## Questions or Issues?

If you encounter any issues with the refactored version:
1. Check that all modules are present in `uploader_modules/`
2. Verify imports are working: run the import tests above
3. Compare behavior with `uploader_original.py` for any discrepancies
4. Review logs for detailed error information

---

**Version:** 2.6.0 (Refactored)
**Date:** 2025-10-27
**API Version:** Shopify GraphQL Admin API 2025-10
