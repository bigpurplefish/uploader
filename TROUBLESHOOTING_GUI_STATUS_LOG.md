# Troubleshooting: GUI Status Log Not Displaying

## Issue
User-friendly log entries are not appearing in the Status Log field in the GUI during script execution.

## Fixes Applied

### 1. Improved `log_and_status()` function (config.py)
- **Change**: Reordered operations to log to file/console FIRST, then update UI
- **Reason**: Ensures logging happens even if UI update fails
- **Added**: None-check for status_fn to prevent crashes
- **Added**: Console fallback if status_fn raises exception

### 2. Enhanced GUI `status()` function (gui.py)
- **Added**: Better error handling with full exception logging
- **Added**: Debug print statement to track when function is called
- **Added**: Try-catch around `app.after()` call
- **Added**: Initial test messages when GUI loads

### 3. Added Debug Output
- **Location**: gui.py line 490
- **Purpose**: Prints "DEBUG: status() called with: <message>" to console
- **Usage**: Run the application and watch console output to confirm status function is being called

## Testing Steps

### Step 1: Verify GUI Status Widget Works
1. Launch the application: `python3 uploader_new.py`
2. **Check the Status Log field** at the bottom of the GUI window
3. **Expected**: You should immediately see:
   ```
   ================================================================================
   2.6.0 - Shopify Product Uploader (API 2025-10 Fix - No Duplicate Variants)
   GUI loaded successfully
   ================================================================================
   ```
4. **If you see these messages**: ✅ The status widget itself is working
5. **If you don't see these messages**: ❌ There's an issue with the Text widget

### Step 2: Verify Status Function Is Called During Processing
1. Configure your settings (Shopify credentials, input file, etc.)
2. Click "Start Processing"
3. **Watch the terminal/console** where you launched the application
4. **Expected**: You should see many lines like:
   ```
   DEBUG: status() called with: ================================================================================
   DEBUG: status() called with: Shopify Product Uploader - 2.6.0...
   DEBUG: status() called with: Loading input file: /path/to/file.json
   ```
5. **If you see debug messages**: ✅ Status function IS being called
6. **If you don't see debug messages**: ❌ Status function is NOT being called

### Step 3: Check for Threading Issues
If status function is being called (Step 2 passes) but messages still don't appear in GUI:

1. Check console for error messages like:
   ```
   ERROR updating GUI status: ...
   ERROR scheduling GUI update: ...
   ```
2. Check log file for warnings:
   ```
   grep "Failed to update status" your_log_file.log
   ```

## Common Issues and Solutions

### Issue 1: Status Widget Not Visible
**Symptom**: Can't see the Status Log field in the GUI

**Solution**:
- Resize the window - the Status Log is at the bottom
- Check if you're running the correct script: `uploader_new.py`

### Issue 2: Initial Messages Appear, But Processing Messages Don't
**Symptom**: See test messages when GUI loads, but nothing during processing

**Possible Causes**:
1. **Threading issue**: `app.after()` not working from background thread
2. **Exception in status function**: Check console for errors
3. **Text widget state issue**: Widget might be locked

**Solution**:
```python
# Temporary fix: In gui.py, replace the status function with this:
def status(msg):
    """Update status with auto-scroll to bottom. Thread-safe."""
    print(f"CONSOLE STATUS: {msg}")  # Temporary: see all messages in console

    def _update_status():
        try:
            status_log.config(state="normal")
            status_log.insert("end", msg + "\n")
            status_log.see("end")
            status_log.config(state="disabled")
            status_log.update_idletasks()  # Force immediate update
        except Exception as e:
            logging.error(f"Failed to update status UI: {e}", exc_info=True)
            print(f"ERROR updating GUI status: {e}")

    try:
        app.after(0, _update_status)
    except Exception as e:
        logging.error(f"Failed to schedule status update: {e}", exc_info=True)
        print(f"ERROR scheduling GUI update: {e}")
```

### Issue 3: No Debug Messages in Console
**Symptom**: Console stays silent, no "DEBUG: status() called" messages

**Possible Causes**:
1. **Status function not being passed**: Check process_products call in gui.py line 409
2. **log_and_status not being used**: Check product_processing.py uses log_and_status, not raw logging

**Solution**: Verify the call chain:
```python
# In gui.py line 409:
process_products(cfg, status, execution_mode=execution_mode)
                     ^^^^^^ Must pass status function

# In product_processing.py:
log_and_status(status_fn, "Your message here")
               ^^^^^^^^^ Must use status_fn parameter
```

### Issue 4: Messages Appear in Log File But Not GUI
**Symptom**: Log file contains all messages, but GUI Status Log is empty

**This means**: `log_and_status` is logging to file but status_fn isn't working

**Solution**: Check that status_fn is not None:
```python
# In config.py, the log_and_status function should check:
if status_fn is not None:
    try:
        status_fn(ui_msg)
    except Exception as e:
        logging.warning(f"status_fn raised: {e}", exc_info=True)
```

## Diagnostic Commands

### Check if modules import correctly:
```bash
python3 -c "from uploader_modules.config import log_and_status; print('✅ Import OK')"
```

### Test log_and_status function:
```bash
python3 test_gui_status.py
```

### Check for Python/tkinter issues:
```bash
python3 -c "import tkinter; import ttkbootstrap; print('✅ GUI libraries OK')"
```

## Debug Mode

To enable maximum debugging, edit gui.py and change line 490 to:
```python
print(f"DEBUG: status() called with: {msg}")  # Print FULL message
```

And in config.py, edit log_and_status to add:
```python
def log_and_status(status_fn, msg: str, level: str = "info", ui_msg: str = None):
    print(f"DEBUG log_and_status: status_fn={status_fn}, msg={msg[:50]}")
    # ... rest of function
```

## Still Not Working?

If none of the above helps:

1. **Capture full console output**:
   ```bash
   python3 uploader_new.py 2>&1 | tee debug_output.txt
   ```

2. **Check log file** for detailed errors:
   ```bash
   tail -f your_log_file.log
   ```

3. **Test with minimal script**:
   Create a simple test that calls process_products directly

4. **Compare with original**:
   Run `python3 uploader_original.py` to see if the original version works

## Rollback if Needed

If the refactored version doesn't work for you:
```bash
# Use the original version
python3 uploader_original.py
```

The original monolithic version should work as expected.

---

**Updated**: 2025-10-27
**Fixes Applied**:
- Improved error handling in log_and_status
- Added debug output to status function
- Added initial test messages
- Reordered logging operations
