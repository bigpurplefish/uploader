# Fix: SCRIPT_VERSION NameError

## Issue
When running `uploader_new.py`, the following error occurred:
```
NameError: name 'SCRIPT_VERSION' is not defined
```

This happened in `product_processing.py` when trying to use `SCRIPT_VERSION` in a log message.

## Root Cause
During the refactoring process, the `SCRIPT_VERSION` constant was defined in the original `uploader.py` file but was not properly exported to the extracted modules. Each module that needed it was trying to reference it without importing it.

## Solution
Centralized the `SCRIPT_VERSION` constant in `config.py` as the single source of truth, and updated all modules to import it from there.

### Changes Made:

1. **config.py**: Added `SCRIPT_VERSION` constant
   ```python
   SCRIPT_VERSION = "2.6.0 - Shopify Product Uploader (API 2025-10 Fix - No Duplicate Variants)"
   ```

2. **product_processing.py**: Updated import statement
   ```python
   from .config import log_and_status, setup_logging, SCRIPT_VERSION
   ```

3. **gui.py**: Removed duplicate definition, imported from config
   ```python
   # Before:
   SCRIPT_VERSION = "2.6.0 - ..."  # Duplicate definition

   # After:
   from .config import load_config, save_config, SCRIPT_VERSION
   ```

4. **uploader_new.py**: Updated to import from config
   ```python
   from uploader_modules.config import SCRIPT_VERSION
   print(f"Starting {SCRIPT_VERSION}")
   ```

## Verification

Tested all imports:
```bash
✅ python3 -c "from uploader_modules.config import SCRIPT_VERSION; print(SCRIPT_VERSION)"
✅ python3 -c "from uploader_modules.product_processing import SCRIPT_VERSION; print(SCRIPT_VERSION)"
✅ python3 -c "from uploader_modules.gui import SCRIPT_VERSION; print(SCRIPT_VERSION)"
```

All modules now correctly access `SCRIPT_VERSION` from the centralized location in `config.py`.

## Benefits of This Approach

1. **Single Source of Truth**: Version is defined in one place only
2. **Easy to Update**: Change version in one file (config.py) and it propagates everywhere
3. **No Duplication**: Eliminates risk of version mismatches between modules
4. **Clear Ownership**: config.py is the logical place for application-wide constants

## Status
✅ **Fixed and verified** - Script now runs without NameError
