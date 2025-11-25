# Debug GUI Command

Diagnose and fix GUI-related issues.

## Usage
```
/debug-gui <issue description>
```

## Common Issues and Solutions

### 1. GUI Freezes During Processing

**Symptoms:**
- Window becomes unresponsive
- "Not Responding" in title bar
- Buttons don't react to clicks

**Cause:** Processing running in main thread instead of worker thread.

**Solution:**
```python
# WRONG - blocks main thread
def start_processing():
    process_products(cfg, status)  # This blocks!

# CORRECT - runs in worker thread
def start_processing():
    def worker():
        try:
            process_products(cfg, status)
        finally:
            button_control_queue.put("enable_buttons")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
```

### 2. Status Log Not Updating

**Symptoms:**
- Status field stays blank during processing
- Messages appear all at once at the end

**Cause:** Direct widget updates from worker thread.

**Solution:**
```python
# WRONG - direct update from worker
status_log.insert("end", message)

# CORRECT - use queue
def status(msg):
    status_queue.put(msg)

# In main thread (process_queues function):
def process_queues():
    try:
        while True:
            msg = status_queue.get_nowait()
            status_log.config(state="normal")
            status_log.insert("end", msg + "\n")
            status_log.config(state="disabled")
    except queue.Empty:
        pass
    app.after(50, process_queues)
```

### 3. Buttons Don't Re-enable After Error

**Symptoms:**
- Buttons stay disabled after processing fails
- Must restart application

**Cause:** Missing finally block in worker thread.

**Solution:**
```python
def worker():
    try:
        # Processing code
        process_products(cfg, status)
    except Exception as e:
        status(f"❌ Error: {e}")
    finally:
        # ALWAYS re-enable buttons
        button_control_queue.put("enable_buttons")
```

### 4. Configuration Not Saving

**Symptoms:**
- Settings lost after restart
- Changes not persisted

**Cause:** Missing trace_add callback.

**Solution:**
```python
field_var = tb.StringVar(value=cfg.get("FIELD_KEY", ""))

def on_change(*args):
    cfg["FIELD_KEY"] = field_var.get()
    save_config(cfg)

field_var.trace_add("write", on_change)
```

### 5. Tooltips Not Appearing

**Symptoms:**
- Info icon shows but no tooltip on hover

**Cause:** ToolTip not attached properly.

**Solution:**
```python
from ttkbootstrap.tooltip import ToolTip

help_icon = tb.Label(frame, text=" ⓘ ", font=("Arial", 9),
                     foreground="#5BC0DE", cursor="hand2")
help_icon.pack(side="left")

# Must attach tooltip to the icon
ToolTip(help_icon, text="Tooltip text here", bootstyle="info")
```

### 6. Fields Not Enabling/Disabling

**Symptoms:**
- Fields should toggle based on radio selection but don't

**Cause:** Missing trace callback or wrong state logic.

**Solution:**
```python
def update_field_states(*args):
    if mode_var.get() == "multiple":
        field2.config(state="normal")
    else:
        field2.config(state="disabled")

mode_var.trace_add("write", update_field_states)
# Also call once initially
update_field_states()
```

## Debugging Steps

1. **Check threading** - Is the operation running in a daemon thread?
2. **Check queues** - Is queue processor running? (50ms interval)
3. **Check state** - Is widget in correct state? ("normal" vs "disabled")
4. **Check callbacks** - Are trace_add callbacks registered?
5. **Check logs** - Look for exceptions in log file

## Testing GUI Changes
```bash
# Run the application in debug mode
python3 uploader.py 2>&1 | tee gui_debug.log
```

## Examples
```
/debug-gui status log not showing messages
/debug-gui buttons stay disabled after error
/debug-gui configuration not saving
```
