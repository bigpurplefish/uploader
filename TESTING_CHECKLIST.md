# Testing Checklist - Refactored Uploader

## Quick Import Test

```bash
# Test all modules import without errors
python3 -c "from uploader_modules import config, state, utils, shopify_api, product_processing, gui; print('✅ All modules import successfully')"

# Test the main entry point
python3 uploader_new.py
```

## Functional Testing Checklist

### 1. GUI Launch
- [ ] GUI window opens without errors
- [ ] All input fields are visible
- [ ] All buttons are present and enabled
- [ ] Settings dialog opens correctly
- [ ] Tooltips appear on hover

### 2. Configuration
- [ ] Settings dialog loads existing config
- [ ] Can update Shopify store URL
- [ ] Can update access token
- [ ] Settings save correctly to config.json
- [ ] Window geometry persists between sessions

### 3. File Selection
- [ ] Browse button opens file dialog for input file
- [ ] Browse button opens file dialog for product output
- [ ] Browse button opens file dialog for collections output
- [ ] Browse button opens file dialog for log file
- [ ] Selected paths display correctly in fields
- [ ] Delete button clears field contents

### 4. Small Batch Test (5-10 Products)
- [ ] Validate button checks for non-CDN URLs
- [ ] Process button starts processing
- [ ] Status log displays real-time updates
- [ ] Products are created in Shopify
- [ ] Variants are created correctly
- [ ] Metafields are attached
- [ ] Product options are set correctly

### 5. Collection Creation
- [ ] Department collections are created (based on product_type)
- [ ] Category collections are created (based on tags)
- [ ] Subcategory collections are created (with compound rules)
- [ ] Collections are not duplicated on subsequent runs
- [ ] Collections are published to sales channels
- [ ] Collections data saved to collections.json

### 6. Taxonomy Integration
- [ ] Shopify taxonomy search works
- [ ] Taxonomy IDs are cached in product_taxonomy.json
- [ ] Cached taxonomy IDs are reused
- [ ] Product category field is populated in Shopify

### 7. Metafield Definitions
- [ ] Script auto-detects required metafield definitions
- [ ] Missing metafield definitions are created
- [ ] Existing metafield definitions are detected (no duplicates)
- [ ] Product metafields work
- [ ] Variant metafields work

### 8. 3D Model Upload (if applicable)
- [ ] GLB files are uploaded successfully
- [ ] USDZ files are uploaded successfully
- [ ] Staged upload process completes
- [ ] File records are created in Shopify
- [ ] Models appear in Shopify admin

### 9. Publishing
- [ ] Products are published to Online Store
- [ ] Products are published to Point of Sale
- [ ] Collections are published to channels

### 10. State Management
- [ ] upload_state.json is created during processing
- [ ] products.json is created as restore point
- [ ] State files contain correct data structure

### 11. Resume Functionality
- [ ] Stop processing mid-batch (close app or Ctrl+C)
- [ ] Restart application
- [ ] Click Process button
- [ ] Processing resumes from last completed product
- [ ] No duplicate products are created
- [ ] All remaining products are processed

### 12. Overwrite Mode
- [ ] Change execution mode to "overwrite" in config
- [ ] Run processing on already-uploaded products
- [ ] Existing products are deleted
- [ ] Products are recreated with updated data
- [ ] No duplicate variants appear

### 13. Error Handling
- [ ] Invalid Shopify credentials show error message
- [ ] Missing input file shows error message
- [ ] Network errors are logged and displayed
- [ ] GraphQL errors are caught and logged
- [ ] User errors (validation) are displayed clearly

### 14. Output Files
- [ ] Product output JSON is created
- [ ] Collections output JSON is created
- [ ] Output files contain correct data structure
- [ ] Output matches Shopify data

### 15. Logging
- [ ] Log file is created
- [ ] Status messages appear in GUI
- [ ] Status messages appear in console
- [ ] Status messages appear in log file
- [ ] DEBUG level details in log file
- [ ] INFO level in console and GUI

### 16. Data Validation
- [ ] Non-Shopify CDN URLs are detected and rejected
- [ ] Missing required fields are detected
- [ ] Invalid JSON input is handled gracefully

### 17. Large Batch Test (100+ Products)
- [ ] Script processes large batches without memory issues
- [ ] Processing can be resumed if interrupted
- [ ] Status updates remain responsive
- [ ] No rate limit issues with 0.5s delays

### 18. Comparison with Original
- [ ] Run same input file through `uploader_original.py`
- [ ] Run same input file through `uploader_new.py`
- [ ] Compare output JSON files
- [ ] Compare created products in Shopify
- [ ] Verify identical behavior

## Performance Testing

### Response Time
- [ ] GUI launches within 2 seconds
- [ ] Button clicks are responsive
- [ ] Status log updates smoothly
- [ ] File dialogs open quickly

### Processing Speed
- [ ] Similar processing speed to original
- [ ] API rate limits respected (0.5s between products)
- [ ] Memory usage remains stable

## Module-Specific Tests

### config.py
```python
from uploader_modules.config import load_config, save_config

# Test loading
cfg = load_config()
assert "SHOPIFY_STORE_URL" in cfg
print("✅ Config loads correctly")

# Test saving
cfg["TEST_KEY"] = "test_value"
save_config(cfg)
cfg2 = load_config()
assert cfg2.get("TEST_KEY") == "test_value"
print("✅ Config saves correctly")
```

### state.py
```python
from uploader_modules.state import load_state, save_state

# Test state management
state = {"test": "data"}
save_state(state)
loaded = load_state()
assert loaded == state
print("✅ State management works")
```

### utils.py
```python
from uploader_modules.utils import is_shopify_cdn_url, extract_category_subcategory

# Test URL validation
assert is_shopify_cdn_url("https://cdn.shopify.com/test.jpg") == True
assert is_shopify_cdn_url("https://example.com/test.jpg") == False
print("✅ URL validation works")

# Test category extraction
product = {"tags": ["Electronics", "Computers"]}
category, subcategory = extract_category_subcategory(product)
assert category == "Electronics"
assert subcategory == "Computers"
print("✅ Category extraction works")
```

### shopify_api.py
- Test individual API functions with mock data
- Verify proper error handling
- Check authentication flow

### product_processing.py
- Test with small sample dataset
- Verify workflow orchestration
- Check error recovery

### gui.py
- Manual GUI testing (see checklist above)
- Verify all widgets render correctly
- Test button state management

## Regression Testing

Compare outputs with original version:

```bash
# Run original version
python3 uploader_original.py
# Save outputs as *_original.json

# Run new version
python3 uploader_new.py
# Save outputs as *_new.json

# Compare
diff product_output_original.json product_output_new.json
diff collections_output_original.json collections_output_new.json
```

## Success Criteria

✅ All checkboxes above are checked
✅ No errors in console or log file
✅ Output matches original version
✅ Products appear correctly in Shopify
✅ All features work as expected
✅ Performance is acceptable

## Rollback Plan

If issues are found:
1. Stop using `uploader_new.py`
2. Revert to `uploader_original.py`
3. Document the issue
4. Fix the issue in the module
5. Re-test

## Sign-off

- [ ] All functional tests passed
- [ ] All module tests passed
- [ ] Comparison with original successful
- [ ] Ready for production use

**Tested by:** _______________
**Date:** _______________
**Version:** 2.6.0 (Refactored)
**Notes:** _______________

---

**Next Steps After Testing:**
1. If all tests pass, rename `uploader_new.py` → `uploader.py`
2. Delete extraction scripts (`extract_*.py`)
3. Keep `uploader_original.py` as backup for one release cycle
4. Update any documentation or launch scripts
5. Consider adding unit tests for critical functions
