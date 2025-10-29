# GUI Design Requirements Document
## Python tkinter/ttkbootstrap Application Pattern

**Version:** 1.0
**Last Updated:** 2025-10-27
**Based On:** Shopify Product Uploader v2.6.0

---

## Table of Contents

1. [Overview](#overview)
2. [Design Philosophy](#design-philosophy)
3. [Framework and Theme](#framework-and-theme)
4. [Main Window Architecture](#main-window-architecture)
5. [Threading and Thread Safety](#threading-and-thread-safety)
6. [Configuration Management](#configuration-management)
7. [Input Field Patterns](#input-field-patterns)
8. [Tooltip System](#tooltip-system)
9. [Button Design and State Management](#button-design-and-state-management)
10. [Status Logging System](#status-logging-system)
11. [Settings Dialog](#settings-dialog)
12. [Window Management](#window-management)
13. [Validation Patterns](#validation-patterns)
14. [Implementation Checklist](#implementation-checklist)

---

## Overview

This document captures the GUI design patterns, threading mechanisms, and user experience decisions implemented in a production Python desktop application. These patterns ensure:

- **Thread-safe GUI updates** from background workers
- **Responsive user interface** during long-running operations
- **Persistent configuration** with auto-save
- **Professional appearance** with modern theming
- **Clear user feedback** via tooltips and status logging
- **Robust error handling** throughout the UI

---

## Design Philosophy

### Core Principles

1. **Thread Safety First**: All GUI updates from worker threads use queue-based communication
2. **Auto-save Everything**: No manual "Save Settings" button - changes persist immediately
3. **Progressive Disclosure**: Tooltips provide context without cluttering the interface
4. **Graceful Degradation**: GUI remains functional even if background tasks fail
5. **Visual Consistency**: Uniform spacing, alignment, and color schemes
6. **Accessibility**: Clear labels, tooltips, and status messages

### User Experience Goals

- **Minimize clicks**: Auto-save, persistent settings, resume capability
- **Clear feedback**: Every action has visible feedback
- **Prevent errors**: Validation before processing starts
- **Support interruption**: Background threads allow window interaction during processing
- **Professional polish**: Modern theme, proper spacing, hover effects

---

## Framework and Theme

### Required Libraries

```python
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from tkinter import filedialog, messagebox
import threading
import queue
import logging
```

### Installation

```bash
pip install ttkbootstrap>=1.10.0
```

### Theme Selection

**Theme:** `darkly` (dark mode with cyan accents)

```python
app = tb.Window(themename="darkly")
```

**Why this theme:**
- Modern, professional appearance
- Reduces eye strain for long sessions
- High contrast for readability
- Cyan accent color (#5BC0DE) for interactive elements

### Alternative Themes

For light mode applications, use: `flatly`, `litera`, or `cosmo`

---

## Main Window Architecture

### Window Setup

```python
def build_gui():
    app = tb.Window(themename="darkly")
    app.title("Application Name")
    app.geometry(cfg.get("WINDOW_GEOMETRY", "900x900"))

    # Setup menu bar, toolbar, container, etc.
    # ... (detailed below)

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
```

### Layout Structure

```
Window
├── Menu Bar (File, Settings, Help)
├── Toolbar (Quick access buttons)
├── Main Container (ttk.Frame)
│   ├── Title Label
│   ├── Input Fields (Grid Layout)
│   │   ├── Row 0: Input File
│   │   ├── Row 1: Output File
│   │   ├── Row 2: Log File
│   │   └── Row N: Additional fields
│   ├── Mode Selection (Radio buttons)
│   └── Button Frame (Horizontal)
├── Status Log Label
└── Status Text Widget (scrollable, read-only)
```

### Grid Layout Pattern

**Column Structure:**
- **Column 0**: Labels with inline tooltip icons (min width, left-aligned)
- **Column 1**: Input fields (expandable with weight=1)
- **Column 2**: Browse buttons (fixed width)
- **Column 3**: Action buttons (e.g., Delete) - optional

```python
container.columnconfigure(1, weight=1)  # Make input fields expandable

# Example row:
row = container.grid_size()[1]
label.grid(row=row, column=0, sticky="w", padx=5, pady=5)
entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
button.grid(row=row, column=2, padx=5, pady=5)
```

### Menu Bar Pattern

```python
menu_bar = tb.Menu(app)
app.config(menu=menu_bar)

settings_menu = tb.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Settings", menu=settings_menu)
settings_menu.add_command(label="System Settings", command=open_system_settings)
```

### Toolbar Pattern

```python
toolbar = tb.Frame(app)
toolbar.pack(side="top", fill="x", padx=5, pady=5)

settings_btn = tb.Button(
    toolbar,
    text="⚙️ Settings",
    command=open_system_settings,
    bootstyle="secondary-outline"
)
settings_btn.pack(side="left", padx=5)
```

---

## Threading and Thread Safety

### The Problem

Tkinter is **not thread-safe**. Direct widget updates from worker threads cause:
- Crashes and segfaults
- Frozen GUI
- Unpredictable behavior

### The Solution: Queue-Based Communication

**Pattern:** Worker threads add messages to queues, main thread processes queues periodically.

### Implementation

#### 1. Create Queues

```python
import queue

# In build_gui():
status_queue = queue.Queue()
button_control_queue = queue.Queue()
```

#### 2. Queue Processor (Main Thread)

```python
def process_queues():
    """Process all pending messages from queues. Runs in main thread."""
    try:
        # Process status messages
        messages = []
        while True:
            try:
                msg = status_queue.get_nowait()
                messages.append(msg)
            except queue.Empty:
                break

        if messages:
            status_log.config(state="normal")
            for msg in messages:
                status_log.insert("end", msg + "\n")
            status_log.see("end")
            status_log.config(state="disabled")
            status_log.update_idletasks()

        # Process button control signals
        while True:
            try:
                signal = button_control_queue.get_nowait()
                if signal == "enable_buttons":
                    start_btn.config(state="normal")
                    validate_btn.config(state="normal")
                    # Re-enable all buttons
            except queue.Empty:
                break

    except Exception as e:
        logging.error(f"Error processing queues: {e}", exc_info=True)

    # Schedule next check (50ms = 20 times per second)
    app.after(50, process_queues)
```

#### 3. Start Queue Processor

```python
# After creating all widgets, start the queue processor
app.after(50, process_queues)
```

#### 4. Thread-Safe Status Function

```python
def status(msg):
    """Update status log. Thread-safe - can be called from any thread."""
    try:
        status_queue.put(msg)
    except Exception as e:
        logging.error(f"Failed to queue status message: {e}")
```

#### 5. Worker Thread Pattern

```python
def start_processing():
    """Button click handler - runs in main thread."""
    # Disable buttons
    start_btn.config(state="disabled")

    def worker():
        """Background worker - runs in daemon thread."""
        try:
            # Do long-running work
            process_data(cfg, status)  # Pass status callback
        except Exception as e:
            status(f"❌ Error: {e}")
            logging.exception("Worker error:")
        finally:
            # Re-enable buttons via queue
            button_control_queue.put("enable_buttons")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
```

### Critical Rules

1. **Never call widget methods from worker threads** - always use queues
2. **Use daemon threads** - they terminate when main thread exits
3. **Always re-enable buttons in finally block** - ensures UI recovery on error
4. **Process queues frequently** - 50ms interval provides responsive feedback
5. **Update idle tasks after batch inserts** - forces display refresh

---

## Configuration Management

### Auto-Save Pattern

**Philosophy:** Save immediately on every change - no "Save" button needed.

### Configuration File Structure

```json
{
    "_SYSTEM SETTINGS": "Comment for organization",
    "SHOPIFY_STORE_URL": "mystore.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_...",

    "_USER SETTINGS": "Comment for organization",
    "INPUT_FILE": "/path/to/input.json",
    "PRODUCT_OUTPUT_FILE": "/path/to/output.json",
    "LOG_FILE": "/path/to/log.txt",
    "WINDOW_GEOMETRY": "900x900+100+100",
    "EXECUTION_MODE": "resume"
}
```

### Config Module Pattern

```python
# config.py
import json
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

def load_config():
    """Load config or create with defaults."""
    default = {
        "SHOPIFY_STORE_URL": "",
        "INPUT_FILE": "",
        "WINDOW_GEOMETRY": "900x900"
    }

    if not os.path.exists(CONFIG_FILE):
        save_config(default)
        return default

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Config load error: {e}")
        return default

def save_config(config):
    """Save config to JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.error(f"Config save error: {e}")
```

### Auto-Save Implementation

```python
# In build_gui():
input_var = tb.StringVar(value=cfg.get("INPUT_FILE", ""))

def on_input_change(*args):
    """Auto-save on every keystroke."""
    try:
        cfg["INPUT_FILE"] = input_var.get()
        save_config(cfg)
    except Exception:
        pass  # Fail silently - don't interrupt user

input_var.trace_add("write", on_input_change)
```

**Why this works:**
- `trace_add("write", callback)` fires on every change
- Silently fails if save fails - doesn't interrupt user
- Updates config dictionary and persists to disk
- No "Save" button needed - always current

---

## Input Field Patterns

### Standard File Input Pattern

```python
# Row counter
row = container.grid_size()[1]

# Label with tooltip
label_frame = tb.Frame(container)
label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

tb.Label(label_frame, text="Input File", anchor="w").pack(side="left")
help_icon = tb.Label(
    label_frame,
    text=" ⓘ ",
    font=("Arial", 9),
    foreground="#5BC0DE",
    cursor="hand2"
)
help_icon.pack(side="left")
tb.Label(label_frame, text=":", anchor="w").pack(side="left")

# Tooltip
tooltip_text = (
    "Select the JSON file containing your product data.\n\n"
    "This file should include product information, variants, images, "
    "and any other data you want to upload.\n\n"
    "Tip: Use the Browse button to easily find your file."
)
ToolTip(help_icon, text=tooltip_text, bootstyle="info")

# Entry field with StringVar
input_var = tb.StringVar(value=cfg.get("INPUT_FILE", ""))
tb.Entry(container, textvariable=input_var, width=50).grid(
    row=row, column=1, sticky="ew", padx=5, pady=5
)

# Browse button
def browse_input():
    try:
        filename = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            input_var.set(filename)
    except Exception as e:
        messagebox.showerror("Browse Failed", f"Failed to open file dialog:\n\n{str(e)}")

tb.Button(
    container,
    text="Browse",
    command=browse_input,
    bootstyle="info-outline"
).grid(row=row, column=2, padx=5, pady=5)

# Auto-save
def on_input_change(*args):
    try:
        cfg["INPUT_FILE"] = input_var.get()
        save_config(cfg)
    except Exception:
        pass

input_var.trace_add("write", on_input_change)
```

### Radio Button Group Pattern

```python
# Label with tooltip (same as above)

# Create frame for radio buttons
mode_frame = tb.Frame(container)
mode_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=5)

execution_mode_var = tb.StringVar(value=cfg.get("EXECUTION_MODE", "resume"))

resume_radio = tb.Radiobutton(
    mode_frame,
    text="Resume from Last Run",
    variable=execution_mode_var,
    value="resume",
    bootstyle="primary"
)
resume_radio.pack(side="left", padx=(0, 20))

overwrite_radio = tb.Radiobutton(
    mode_frame,
    text="Overwrite & Continue",
    variable=execution_mode_var,
    value="overwrite",
    bootstyle="warning"
)
overwrite_radio.pack(side="left")

# Auto-save
def on_mode_change(*args):
    try:
        cfg["EXECUTION_MODE"] = execution_mode_var.get()
        save_config(cfg)
    except Exception:
        pass

execution_mode_var.trace_add("write", on_mode_change)
```

---

## Tooltip System

### Design Decisions

1. **Circled info icon**: ⓘ (Unicode U+24D8)
2. **Cyan color**: #5BC0DE (matches theme accent)
3. **Small font**: 9pt Arial
4. **Hover cursor**: Changes to hand pointer
5. **Inline placement**: Between label and colon
6. **Comprehensive text**: 2-4 sentences with formatting

### Tooltip Icon Implementation

```python
help_icon = tb.Label(
    label_frame,
    text=" ⓘ ",           # Circled lowercase i
    font=("Arial", 9),     # Small, readable size
    foreground="#5BC0DE",  # Theme accent color
    cursor="hand2"         # Hand pointer on hover
)
help_icon.pack(side="left")
```

### Tooltip Text Guidelines

**Structure:**
1. **First line**: What this field does (1 sentence)
2. **Blank line**
3. **Details**: Additional context (2-3 sentences)
4. **Blank line**
5. **Tip**: Pro tip or best practice

**Example:**

```python
tooltip_text = (
    "Select the JSON file containing your product data.\n\n"
    "This file should include product information, variants, images, "
    "and any other data you want to upload.\n\n"
    "Tip: Use the Browse button to easily find your file."
)
ToolTip(help_icon, text=tooltip_text, bootstyle="info")
```

### Tooltip Style

```python
ToolTip(widget, text="...", bootstyle="info")
```

**Bootstyles available:**
- `info` (cyan - recommended)
- `primary` (blue)
- `success` (green)
- `warning` (yellow)
- `danger` (red)

---

## Button Design and State Management

### Button Layout

**Horizontal button frame at bottom:**

```python
button_frame = tb.Frame(app)
button_frame.pack(pady=10)

# Buttons pack left to right
test_btn.pack(side="left", padx=5)
validate_btn.pack(side="left", padx=5)
start_btn.pack(side="left", padx=5)
delete_btn.pack(side="left", padx=5)
exit_btn.pack(side="left", padx=5)
```

### Button Styles (Bootstyle)

| Button Type | Bootstyle | Use Case |
|-------------|-----------|----------|
| Primary action | `success` | Start Processing, Submit |
| Secondary action | `info` | Validate Settings, Preview |
| Destructive action | `danger-outline` | Delete, Clear |
| Neutral action | `secondary` | Exit, Cancel |
| Testing/Debug | `warning` | Test Status, Debug |

### Button State Management

**Problem:** Long-running operations should disable buttons to prevent re-entry.

**Solution:** Disable on start, re-enable via queue when done.

```python
def validate_and_start():
    """Button click handler."""
    if not validate_inputs():
        return

    # Disable buttons
    start_btn.config(state="disabled")
    validate_btn.config(state="disabled")

    def run_processing():
        try:
            process_products(cfg, status)
        except Exception as e:
            status(f"❌ Fatal error: {e}")
            logging.exception("Processing error:")
        finally:
            # ALWAYS re-enable buttons, even on error
            button_control_queue.put("enable_buttons")

    thread = threading.Thread(target=run_processing, daemon=True)
    thread.start()
```

**Critical:** Use `finally` block to ensure buttons re-enable even if processing crashes.

### Button with Confirmation Dialog

```python
def delete_log_file():
    """Delete log file after confirmation."""
    log_path = log_file_var.get().strip()

    if not log_path:
        messagebox.showwarning("No File", "No log file path specified.")
        return

    if not os.path.exists(log_path):
        messagebox.showwarning("File Not Found", f"Log file does not exist:\n{log_path}")
        return

    confirm = messagebox.askyesno(
        "Confirm Delete",
        f"Are you sure you want to delete this log file?\n\n{log_path}\n\nThis action cannot be undone."
    )

    if confirm:
        try:
            os.remove(log_path)
            messagebox.showinfo("Success", f"Log file deleted successfully:\n{log_path}")
        except PermissionError:
            messagebox.showerror("Delete Failed", "Permission denied. The log file may be in use.")
        except Exception as e:
            messagebox.showerror("Delete Failed", f"Failed to delete log file:\n\n{str(e)}")
```

---

## Status Logging System

### Status Text Widget Setup

```python
# Label
status_label = tb.Label(app, text="Status Log:", anchor="w")
status_label.pack(anchor="w", padx=10, pady=(10, 0))

# Text widget (starts enabled for initial messages)
status_log = tb.Text(app, height=100, state="normal")
status_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
```

### Clear Status Function

```python
def clear_status():
    """Clear status log before new operation."""
    try:
        status_log.config(state="normal")
        status_log.delete("1.0", "end")
        status_log.config(state="disabled")
    except Exception as e:
        logging.warning(f"Failed to clear status: {e}")
```

### Initial Welcome Messages

```python
# After starting queue processor
status("=" * 80)
status("Application Name v1.0.0")
status("GUI loaded successfully")
status("=" * 80)
status("")
```

### Status Message Patterns

**Section Headers:**
```python
status("")
status("=" * 80)
status("PROCESSING PRODUCTS")
status("=" * 80)
```

**Progress Updates:**
```python
status(f"[{index + 1}/{total}] Processing: {product_name}")
```

**Success Messages:**
```python
status(f"✅ Product created successfully")
status(f"  - Product ID: {product_id}")
status(f"  - Shopify URL: {url}")
```

**Warnings:**
```python
status(f"⚠ Warning: {warning_message}")
```

**Errors:**
```python
status(f"❌ Error: {error_message}")
```

**Completion Summary:**
```python
status("")
status("=" * 80)
status("PROCESSING COMPLETE")
status("=" * 80)
status(f"✅ Successful: {success_count}")
status(f"⚠ Skipped: {skip_count}")
status(f"❌ Failed: {fail_count}")
status(f"Total: {total_count}")
status("=" * 80)
```

### Integration with Python Logging

Use helper function to log to both file and UI:

```python
def log_and_status(status_fn, msg: str, level: str = "info", ui_msg: str = None):
    """Log to file and update UI."""
    if ui_msg is None:
        ui_msg = msg

    # Log to file
    if level == "error":
        logging.error(msg)
    elif level == "warning":
        logging.warning(msg)
    else:
        logging.info(msg)

    # Update UI
    if status_fn:
        try:
            status_fn(ui_msg)
        except Exception as e:
            logging.warning(f"Status update failed: {e}")
```

---

## Settings Dialog

### Requirements

The settings dialog should:
1. Open as a modal dialog (blocks main window)
2. Allow editing of system settings (API keys, URLs)
3. Validate inputs before saving
4. Support password masking for tokens
5. Save immediately on "Save" button click
6. Cancel without saving on "Cancel" button click

### Implementation Pattern

```python
def open_system_settings(cfg, parent):
    """Open modal settings dialog."""
    dialog = tb.Toplevel(parent)
    dialog.title("System Settings")
    dialog.geometry("600x400")
    dialog.transient(parent)  # Modal dialog
    dialog.grab_set()  # Block interaction with parent

    # Center dialog on parent
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (dialog.winfo_width() // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    # Container
    container = tb.Frame(dialog)
    container.pack(fill="both", expand=True, padx=20, pady=20)
    container.columnconfigure(1, weight=1)

    # Title
    tb.Label(
        container,
        text="System Settings",
        font=("Arial", 14, "bold")
    ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # Shopify Store URL
    row = 1
    tb.Label(container, text="Shopify Store URL:", anchor="w").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    store_var = tb.StringVar(value=cfg.get("SHOPIFY_STORE_URL", ""))
    tb.Entry(container, textvariable=store_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    # Shopify Access Token (masked)
    row += 1
    tb.Label(container, text="Shopify Access Token:", anchor="w").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    token_var = tb.StringVar(value=cfg.get("SHOPIFY_ACCESS_TOKEN", ""))
    tb.Entry(container, textvariable=token_var, show="*").grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    # Sales Channel IDs (if applicable)
    row += 1
    tb.Label(container, text="Online Store Channel ID:", anchor="w").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    online_store_var = tb.StringVar(value=cfg.get("SALES_CHANNEL_ONLINE_STORE", ""))
    tb.Entry(container, textvariable=online_store_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    # Button frame
    button_frame = tb.Frame(container)
    button_frame.grid(row=row + 1, column=0, columnspan=2, pady=(20, 0))

    def save_settings():
        """Validate and save settings."""
        # Validation
        store_url = store_var.get().strip()
        token = token_var.get().strip()

        if not store_url:
            messagebox.showerror("Validation Error", "Shopify Store URL is required.")
            return

        if not token:
            messagebox.showerror("Validation Error", "Shopify Access Token is required.")
            return

        # Save to config
        cfg["SHOPIFY_STORE_URL"] = store_url
        cfg["SHOPIFY_ACCESS_TOKEN"] = token
        cfg["SALES_CHANNEL_ONLINE_STORE"] = online_store_var.get().strip()
        save_config(cfg)

        messagebox.showinfo("Success", "Settings saved successfully.")
        dialog.destroy()

    def cancel_settings():
        """Close without saving."""
        dialog.destroy()

    tb.Button(
        button_frame,
        text="Save",
        command=save_settings,
        bootstyle="success"
    ).pack(side="left", padx=5)

    tb.Button(
        button_frame,
        text="Cancel",
        command=cancel_settings,
        bootstyle="secondary"
    ).pack(side="left", padx=5)

    dialog.wait_window()  # Wait for dialog to close
```

**Key Features:**
- Modal dialog with `transient()` and `grab_set()`
- Centered on parent window
- Password masking with `show="*"`
- Validation before save
- No auto-save (explicit Save button)

---

## Window Management

### Window Geometry Persistence

**Save on close:**

```python
def on_closing():
    """Handle window close event."""
    try:
        cfg["WINDOW_GEOMETRY"] = app.geometry()
        save_config(cfg)
    except Exception as e:
        logging.warning(f"Failed to save window geometry: {e}")
    app.quit()

app.protocol("WM_DELETE_WINDOW", on_closing)
```

**Restore on open:**

```python
app = tb.Window(themename="darkly")
app.geometry(cfg.get("WINDOW_GEOMETRY", "900x900"))
```

### Minimum Window Size (Optional)

```python
app.minsize(600, 400)
```

### Maximized State (Optional)

```python
# Start maximized
app.state("zoomed")  # Windows/Linux
# app.state("zoomed") doesn't work on macOS - use geometry instead
```

---

## Validation Patterns

### Pre-Flight Validation

**Validate all inputs before starting processing:**

```python
def validate_inputs():
    """Validate all required inputs."""
    try:
        if not input_var.get().strip():
            messagebox.showerror("Validation Error", "Input File is required.")
            return False

        if not os.path.exists(input_var.get()):
            messagebox.showerror("Validation Error", "Input File does not exist.")
            return False

        if not output_var.get().strip():
            messagebox.showerror("Validation Error", "Output File is required.")
            return False

        if not log_file_var.get().strip():
            messagebox.showerror("Validation Error", "Log File is required.")
            return False

        if not cfg.get("SHOPIFY_STORE_URL", "").strip():
            messagebox.showerror(
                "Validation Error",
                "Shopify Store URL is required.\n\nPlease configure it in Settings."
            )
            return False

        if not cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip():
            messagebox.showerror(
                "Validation Error",
                "Shopify Access Token is required.\n\nPlease configure it in Settings."
            )
            return False

        return True
    except Exception as e:
        messagebox.showerror("Validation Error", f"Unexpected error during validation:\n\n{str(e)}")
        return False
```

### Separate Validate Button (Optional)

Allow users to test settings without starting processing:

```python
validate_btn = tb.Button(
    button_frame,
    text="Validate Settings",
    command=validate_inputs,
    bootstyle="info"
)
validate_btn.pack(side="left", padx=5)
```

---

## Implementation Checklist

### Phase 1: Basic Structure

- [ ] Install ttkbootstrap: `pip install ttkbootstrap>=1.10.0`
- [ ] Create `build_gui()` function
- [ ] Set up main window with theme: `tb.Window(themename="darkly")`
- [ ] Create menu bar and toolbar
- [ ] Create main container with grid layout
- [ ] Set column 1 weight to 1: `container.columnconfigure(1, weight=1)`

### Phase 2: Configuration

- [ ] Create `config.py` module with `load_config()` and `save_config()`
- [ ] Define default configuration dictionary
- [ ] Load config at startup: `cfg = load_config()`
- [ ] Test config file creation in app directory

### Phase 3: Input Fields

- [ ] Create label frames with tooltips
- [ ] Add circled info icons: `text=" ⓘ "`, `font=("Arial", 9)`, `foreground="#5BC0DE"`
- [ ] Create StringVars bound to config: `tb.StringVar(value=cfg.get("KEY", ""))`
- [ ] Add Entry widgets with `sticky="ew"`
- [ ] Add Browse buttons with file dialogs
- [ ] Implement auto-save callbacks: `var.trace_add("write", on_change)`

### Phase 4: Tooltips

- [ ] Write comprehensive tooltip text for each field
- [ ] Attach tooltips to info icons: `ToolTip(help_icon, text=..., bootstyle="info")`
- [ ] Test tooltip appearance and formatting

### Phase 5: Buttons

- [ ] Create horizontal button frame at bottom
- [ ] Add buttons with appropriate bootstyles
- [ ] Implement validation function
- [ ] Add confirmation dialogs for destructive actions

### Phase 6: Status Logging

- [ ] Create status Text widget
- [ ] Implement `clear_status()` function
- [ ] Add initial welcome messages

### Phase 7: Threading (CRITICAL)

- [ ] Create status queue: `status_queue = queue.Queue()`
- [ ] Create button control queue: `button_control_queue = queue.Queue()`
- [ ] Implement `process_queues()` function
- [ ] Start queue processor: `app.after(50, process_queues)`
- [ ] Create thread-safe `status()` function
- [ ] Implement worker thread pattern with daemon threads
- [ ] Test button re-enabling via queue
- [ ] Add comprehensive error handling in `finally` blocks

### Phase 8: Settings Dialog

- [ ] Implement `open_system_settings()` function
- [ ] Create modal dialog with `transient()` and `grab_set()`
- [ ] Add system settings fields (API keys, URLs)
- [ ] Use `show="*"` for password fields
- [ ] Add Save and Cancel buttons
- [ ] Validate settings before saving

### Phase 9: Window Management

- [ ] Implement `on_closing()` to save geometry
- [ ] Register close handler: `app.protocol("WM_DELETE_WINDOW", on_closing)`
- [ ] Set minimum window size (optional)
- [ ] Test geometry persistence across restarts

### Phase 10: Polish

- [ ] Test all tooltips for clarity
- [ ] Verify all buttons have proper states
- [ ] Test thread safety with long-running operations
- [ ] Test error handling (force failures)
- [ ] Verify config auto-save on every field
- [ ] Test settings dialog validation
- [ ] Check spacing and alignment consistency

### Phase 11: Testing

- [ ] Test on target OS (Windows/macOS/Linux)
- [ ] Test with missing config file
- [ ] Test with corrupted config file
- [ ] Test interrupting long-running operations
- [ ] Test clicking Start multiple times rapidly
- [ ] Test closing window during processing
- [ ] Test validation with invalid inputs
- [ ] Test all file dialogs
- [ ] Test all confirmation dialogs

---

## Common Pitfalls and Solutions

### Pitfall 1: Widgets Don't Update During Processing

**Problem:** Text widget doesn't show new messages until processing completes.

**Solution:**
1. Use queue-based communication
2. Call `widget.update_idletasks()` after batch inserts
3. Process queues every 50ms with `app.after(50, process_queues)`

### Pitfall 2: GUI Freezes During Long Operations

**Problem:** Window becomes unresponsive.

**Solution:** Run processing in daemon thread, never block main thread.

### Pitfall 3: Buttons Don't Re-enable After Error

**Problem:** Worker crashes, buttons stay disabled forever.

**Solution:** Use `finally` block to always send re-enable signal via queue.

### Pitfall 4: Can't Update Text Widget

**Problem:** Text widget is in "disabled" state, inserts silently fail.

**Solution:** Toggle state in queue processor:
```python
status_log.config(state="normal")
status_log.insert("end", msg + "\n")
status_log.config(state="disabled")
```

### Pitfall 5: Config Not Persisting

**Problem:** Changes don't save to disk.

**Solution:** Ensure `trace_add()` callback calls `save_config(cfg)` on every change.

### Pitfall 6: Race Conditions in Threading

**Problem:** Unpredictable behavior when threads interact.

**Solution:**
- Never share mutable state between threads
- Use queues for all cross-thread communication
- Make worker threads daemon threads

---

## Advanced Patterns

### Pattern: Progress Bar

```python
progress = tb.Progressbar(
    app,
    mode="determinate",
    maximum=100,
    bootstyle="success"
)
progress.pack(fill="x", padx=10, pady=5)

# Update via queue
progress_queue = queue.Queue()

def update_progress():
    try:
        while True:
            try:
                value = progress_queue.get_nowait()
                progress["value"] = value
            except queue.Empty:
                break
    except Exception as e:
        logging.error(f"Progress update error: {e}")
    app.after(50, update_progress)

# From worker thread:
progress_queue.put(50)  # 50% complete
```

### Pattern: Dynamically Enable/Disable Fields

```python
def on_mode_change(*args):
    """Enable/disable fields based on selected mode."""
    mode = mode_var.get()
    if mode == "simple":
        advanced_entry.config(state="disabled")
    else:
        advanced_entry.config(state="normal")
```

### Pattern: Real-Time Field Validation

```python
def validate_url(*args):
    """Validate URL as user types."""
    url = url_var.get()
    if url and not url.startswith(("http://", "https://")):
        url_entry.config(bootstyle="danger")
    else:
        url_entry.config(bootstyle="default")

url_var.trace_add("write", validate_url)
```

---

## Performance Considerations

1. **Queue Processing Frequency:** 50ms (20 Hz) provides responsive feedback without excessive CPU usage
2. **Batch Status Updates:** Collect multiple messages, insert all at once, reduce widget redraws
3. **Lazy Tooltip Creation:** ToolTip objects are lightweight, create at widget creation time
4. **Config Save Throttling:** Consider debouncing if saving is slow (e.g., remote config)
5. **Large Status Logs:** Limit Text widget to last N lines, trim old content periodically

---

## Accessibility Recommendations

1. **Keyboard Navigation:** Ensure all buttons and fields are accessible via Tab key
2. **Clear Labels:** Every input should have a descriptive label
3. **Tooltips for Context:** Use tooltips to explain every non-obvious field
4. **Status Messages:** Provide clear, actionable feedback for every operation
5. **Error Messages:** Show errors in both UI status log and modal dialogs
6. **Confirmation Dialogs:** Always confirm destructive actions

---

## Security Considerations

1. **Mask Sensitive Fields:** Use `show="*"` for passwords and API tokens
2. **Config File Permissions:** Store config.json with restricted permissions (not world-readable)
3. **Logging:** Don't log API tokens or passwords to status log or file logs
4. **Validation:** Validate all user inputs before use
5. **Error Messages:** Don't expose sensitive data in error messages

---

## Conclusion

This document captures a battle-tested pattern for building professional, thread-safe Python desktop applications with tkinter/ttkbootstrap. Key takeaways:

1. **Queue-based threading is essential** for thread-safe GUI updates
2. **Auto-save configuration** provides seamless user experience
3. **Comprehensive tooltips** reduce support burden
4. **Proper error handling** ensures graceful degradation
5. **Consistent styling** creates professional appearance

Use this document as a reference when building new Python GUIs. Copy the patterns that apply to your use case, adapt as needed, and maintain consistency across your applications.

---

**Document Version:** 1.0
**Created:** 2025-10-27
**Author:** Derived from Shopify Product Uploader v2.6.0
**License:** Use freely for any project
