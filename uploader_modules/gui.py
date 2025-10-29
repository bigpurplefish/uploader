"""
GUI implementation for Shopify Product Uploader.

This module contains the tkinter/ttkbootstrap GUI code.
"""

import os
import threading
import logging
import queue
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip

from .config import load_config, save_config, SCRIPT_VERSION
from .product_processing import process_products


# Claude model options
CLAUDE_MODELS = [
    ("Claude Sonnet 4.5 (Recommended)", "claude-sonnet-4-5-20250929"),
    ("Claude Opus 3.5", "claude-opus-3-5-20241022"),
    ("Claude Sonnet 3.5", "claude-3-5-sonnet-20241022"),
    ("Claude Haiku 3.5", "claude-3-5-haiku-20241022")
]


def get_model_id_from_display(display_name):
    """Convert display name to model ID."""
    for display, model_id in CLAUDE_MODELS:
        if display == display_name:
            return model_id
    return "claude-sonnet-4-5-20250929"  # fallback to default


def get_display_from_model_id(model_id):
    """Convert model ID to display name."""
    for display, mid in CLAUDE_MODELS:
        if mid == model_id:
            return display
    return "Claude Sonnet 4.5 (Recommended)"  # fallback to default


def open_system_settings(cfg, parent):
    """Open the system settings dialog."""
    settings_window = tb.Toplevel(parent)
    settings_window.title("System Settings")
    settings_window.geometry("700x550")
    settings_window.transient(parent)
    settings_window.grab_set()

    # Main frame with padding
    main_frame = tb.Frame(settings_window, padding=20)
    main_frame.pack(fill="both", expand=True)

    # Title
    tb.Label(
        main_frame,
        text="System Settings",
        font=("Arial", 14, "bold")
    ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # Shopify Settings Section
    tb.Label(
        main_frame,
        text="Shopify Configuration",
        font=("Arial", 11, "bold")
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 5))

    tb.Separator(main_frame, orient="horizontal").grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10)
    )

    # Shopify Store URL
    tb.Label(main_frame, text="Shopify Store URL:").grid(
        row=3, column=0, sticky="w", padx=5, pady=5
    )
    store_url_var = tb.StringVar(value=cfg.get("SHOPIFY_STORE_URL", ""))
    store_url_entry = tb.Entry(main_frame, textvariable=store_url_var, width=50)
    store_url_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    ToolTip(store_url_entry, text="Your Shopify store URL (e.g., mystore.myshopify.com)")

    # Shopify Access Token
    tb.Label(main_frame, text="Shopify Access Token:").grid(
        row=4, column=0, sticky="w", padx=5, pady=5
    )
    access_token_var = tb.StringVar(value=cfg.get("SHOPIFY_ACCESS_TOKEN", ""))
    access_token_entry = tb.Entry(main_frame, textvariable=access_token_var, width=50, show="*")
    access_token_entry.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    ToolTip(access_token_entry, text="Your Shopify Admin API access token")

    # Claude AI Settings Section
    tb.Label(
        main_frame,
        text="Claude AI Configuration",
        font=("Arial", 11, "bold")
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(20, 5))

    tb.Separator(main_frame, orient="horizontal").grid(
        row=6, column=0, columnspan=2, sticky="ew", pady=(0, 10)
    )

    # Claude API Key
    tb.Label(main_frame, text="Claude API Key:").grid(
        row=7, column=0, sticky="w", padx=5, pady=5
    )
    claude_api_key_var = tb.StringVar(value=cfg.get("CLAUDE_API_KEY", ""))
    claude_api_key_entry = tb.Entry(main_frame, textvariable=claude_api_key_var, width=50, show="*")
    claude_api_key_entry.grid(row=7, column=1, sticky="ew", padx=5, pady=5)
    ToolTip(
        claude_api_key_entry,
        text="Your Anthropic Claude API key\n(Get one at: console.anthropic.com)"
    )

    # Claude Model Selection
    tb.Label(main_frame, text="Claude Model:").grid(
        row=8, column=0, sticky="w", padx=5, pady=5
    )

    current_model_id = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
    current_display = get_display_from_model_id(current_model_id)

    model_var = tb.StringVar(value=current_display)
    model_dropdown = tb.Combobox(
        main_frame,
        textvariable=model_var,
        values=[display for display, _ in CLAUDE_MODELS],
        state="readonly",
        width=47
    )
    model_dropdown.grid(row=8, column=1, sticky="ew", padx=5, pady=5)
    ToolTip(
        model_dropdown,
        text="Sonnet 4.5: Best for this task (Recommended)\n"
             "Opus 3.5: Maximum intelligence, higher cost\n"
             "Sonnet 3.5: Previous generation, good balance\n"
             "Haiku 3.5: Fast and cheap, may miss nuances"
    )

    # Info label about Claude AI
    info_frame = tb.Frame(main_frame)
    info_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=10)

    info_label = tb.Label(
        info_frame,
        text="ℹ️  Claude AI automatically assigns products to your internal taxonomy\n"
             "and rewrites descriptions following voice and tone guidelines.",
        font=("Arial", 9),
        foreground="#5BC0DE",
        justify="left"
    )
    info_label.pack(anchor="w", padx=5)

    # Configure column weights
    main_frame.columnconfigure(1, weight=1)

    # Button frame
    button_frame = tb.Frame(settings_window)
    button_frame.pack(side="bottom", fill="x", padx=20, pady=20)

    def save_settings():
        """Save settings and close dialog."""
        cfg["SHOPIFY_STORE_URL"] = store_url_var.get().strip()
        cfg["SHOPIFY_ACCESS_TOKEN"] = access_token_var.get().strip()
        cfg["CLAUDE_API_KEY"] = claude_api_key_var.get().strip()
        cfg["CLAUDE_MODEL"] = get_model_id_from_display(model_var.get())

        save_config(cfg)
        messagebox.showinfo("Settings Saved", "System settings have been saved successfully.")
        settings_window.destroy()

    def cancel_settings():
        """Close dialog without saving."""
        settings_window.destroy()

    # Save and Cancel buttons
    tb.Button(
        button_frame,
        text="Save",
        command=save_settings,
        bootstyle="success",
        width=15
    ).pack(side="right", padx=5)

    tb.Button(
        button_frame,
        text="Cancel",
        command=cancel_settings,
        bootstyle="secondary",
        width=15
    ).pack(side="right")


def build_gui():
    """Build the main GUI application."""
    global cfg
    cfg = load_config()
    
    app = tb.Window(themename="darkly")
    app.title("Shopify Product Uploader")
    app.geometry(cfg.get("WINDOW_GEOMETRY", "900x900"))
    
    # Create menu bar
    menu_bar = tb.Menu(app)
    app.config(menu=menu_bar)
    
    # Add Settings menu
    settings_menu = tb.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Settings", menu=settings_menu)
    settings_menu.add_command(label="System Settings", command=lambda: open_system_settings(cfg, app))
    
    # Create toolbar
    toolbar = tb.Frame(app)
    toolbar.pack(side="top", fill="x", padx=5, pady=5)
    
    # Add settings button with gear icon
    settings_btn = tb.Button(
        toolbar,
        text="⚙️ Settings",
        command=lambda: open_system_settings(cfg, app),
        bootstyle="secondary-outline"
    )
    settings_btn.pack(side="left", padx=5)
    
    # Main container
    container = tb.Frame(app)
    container.pack(fill="both", expand=True, padx=10, pady=10)
    container.columnconfigure(1, weight=1)
    
    # Title
    tb.Label(container, text="Shopify Product Uploader", font=("Arial", 14, "bold")).grid(
        row=0, column=0, columnspan=3, pady=10
    )
    
    # Input File field
    row = container.grid_size()[1]
    
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)
    
    tb.Label(label_frame, text="Input File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")
    
    tooltip_text = (
        "Select the JSON file containing your product data.\n\n"
        "This file should include product information, variants, images, "
        "and any other data you want to upload.\n\n"
        "Tip: Use the Browse button to easily find your file."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")
    
    input_var = tb.StringVar(value=cfg.get("INPUT_FILE", ""))
    tb.Entry(container, textvariable=input_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )
    
    def browse_input():
        """Browse for input file."""
        try:
            filename = filedialog.askopenfilename(
                title="Select Input File",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                input_var.set(filename)
        except Exception as e:
            messagebox.showerror("Browse Failed", f"Failed to open file dialog:\n\n{str(e)}")
    
    tb.Button(container, text="Browse", command=browse_input, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )
    
    def on_input_change(*args):
        """Auto-save input file path to config."""
        try:
            cfg["INPUT_FILE"] = input_var.get()
            save_config(cfg)
        except Exception:
            pass
    
    input_var.trace_add("write", on_input_change)
    
    # Product Output File field
    row = container.grid_size()[1]
    
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)
    
    tb.Label(label_frame, text="Product Output File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")
    
    tooltip_text = (
        "Choose where to save the product upload results.\n\n"
        "This file will contain details about each uploaded product, "
        "including Shopify IDs, success/failure status, and error messages.\n\n"
        "Tip: Use a descriptive filename like 'products_output_2025-10-26.json'"
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")
    
    product_output_var = tb.StringVar(value=cfg.get("PRODUCT_OUTPUT_FILE", ""))
    tb.Entry(container, textvariable=product_output_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )
    
    def browse_product_output():
        """Browse for product output file."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Select Product Output File",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                product_output_var.set(filename)
        except Exception as e:
            messagebox.showerror("Browse Failed", f"Failed to open file dialog:\n\n{str(e)}")
    
    tb.Button(container, text="Browse", command=browse_product_output, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )
    
    def on_product_output_change(*args):
        """Auto-save product output file path to config."""
        try:
            cfg["PRODUCT_OUTPUT_FILE"] = product_output_var.get()
            save_config(cfg)
        except Exception:
            pass
    
    product_output_var.trace_add("write", on_product_output_change)
    
    # Collections Output File field
    row = container.grid_size()[1]
    
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)
    
    tb.Label(label_frame, text="Collections Output File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")
    
    tooltip_text = (
        "Choose where to save the collection creation results.\n\n"
        "This file will track all collections created during the upload, "
        "including department, category, and subcategory collections.\n\n"
        "Tip: This helps avoid duplicate collections on future runs."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")
    
    collections_output_var = tb.StringVar(value=cfg.get("COLLECTIONS_OUTPUT_FILE", ""))
    tb.Entry(container, textvariable=collections_output_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )
    
    def browse_collections_output():
        """Browse for collections output file."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Select Collections Output File",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                collections_output_var.set(filename)
        except Exception as e:
            messagebox.showerror("Browse Failed", f"Failed to open file dialog:\n\n{str(e)}")
    
    tb.Button(container, text="Browse", command=browse_collections_output, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )
    
    def on_collections_output_change(*args):
        """Auto-save collections output file path to config."""
        try:
            cfg["COLLECTIONS_OUTPUT_FILE"] = collections_output_var.get()
            save_config(cfg)
        except Exception:
            pass
    
    collections_output_var.trace_add("write", on_collections_output_change)
    
    # Log File field
    row = container.grid_size()[1]
    
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)
    
    tb.Label(label_frame, text="Log File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")
    
    tooltip_text = (
        "Choose where to save detailed processing logs.\n\n"
        "Logs help you track what happened during processing and "
        "troubleshoot any issues.\n\n"
        "Tip: Include the date in the filename (e.g., log_2025-10-26.txt)"
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")
    
    log_file_var = tb.StringVar(value=cfg.get("LOG_FILE", ""))
    tb.Entry(container, textvariable=log_file_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )
    
    def browse_log_file():
        """Browse for log file."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Select Log File",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                log_file_var.set(filename)
        except Exception as e:
            messagebox.showerror("Browse Failed", f"Failed to open file dialog:\n\n{str(e)}")
    
    tb.Button(container, text="Browse", command=browse_log_file, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )
    
    def delete_log_file():
        """Delete the log file after confirmation."""
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
                messagebox.showerror("Delete Failed", f"Permission denied. The log file may be in use.")
            except Exception as e:
                messagebox.showerror("Delete Failed", f"Failed to delete log file:\n\n{str(e)}")
    
    tb.Button(container, text="Delete", command=delete_log_file, bootstyle="danger-outline").grid(
        row=row, column=3, padx=5, pady=5
    )
    
    def on_log_change(*args):
        """Auto-save log file path to config."""
        try:
            cfg["LOG_FILE"] = log_file_var.get()
            save_config(cfg)
        except Exception:
            pass
    
    log_file_var.trace_add("write", on_log_change)

    # Claude AI Enhancement checkbox
    row = container.grid_size()[1]

    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="AI Enhancement", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    tooltip_text = (
        "Use Claude AI to enhance products before uploading:\n\n"
        "• Assigns products to your internal taxonomy\n"
        "  (Department → product_type, Category/Subcategory → tags)\n\n"
        "• Rewrites descriptions following voice and tone guidelines\n"
        "  (Professional, brand-consistent copy for each department)\n\n"
        "Requirements:\n"
        "• Claude API key configured in Settings\n"
        "• anthropic package installed (pip install anthropic)\n\n"
        "Tip: This processes ~5 products per minute due to AI processing time."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")

    use_claude_var = tb.BooleanVar(value=cfg.get("USE_CLAUDE_AI", False))

    claude_checkbox = tb.Checkbutton(
        container,
        text="🤖 Use Claude AI for taxonomy assignment and description rewriting",
        variable=use_claude_var,
        bootstyle="info-round-toggle"
    )
    claude_checkbox.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=5)

    def on_claude_toggle(*args):
        """Auto-save Claude AI setting to config."""
        try:
            cfg["USE_CLAUDE_AI"] = use_claude_var.get()
            save_config(cfg)
        except Exception:
            pass

    use_claude_var.trace_add("write", on_claude_toggle)

    # Execution Mode toggle
    row = container.grid_size()[1]

    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Execution Mode", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    tooltip_text = (
        "Choose how to handle existing products:\n\n"
        "• Resume from Last Run:\n"
        "  Continues where the previous run left off.\n"
        "  Skips products already processed successfully.\n\n"
        "• Overwrite & Continue:\n"
        "  Deletes and recreates products that were already processed.\n"
        "  Useful when you need to fix/update existing products.\n\n"
        "Tip: Use 'Overwrite' mode when data has changed and needs updating."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")

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

    def on_execution_mode_change(*args):
        """Auto-save execution mode to config."""
        try:
            cfg["EXECUTION_MODE"] = execution_mode_var.get()
            save_config(cfg)
        except Exception:
            pass

    execution_mode_var.trace_add("write", on_execution_mode_change)

    # Buttons
    button_frame = tb.Frame(app)
    button_frame.pack(pady=10)
    
    def validate_inputs():
        """Validate all required inputs."""
        try:
            if not input_var.get().strip():
                messagebox.showerror("Validation Error", "Input File is required.")
                return False
            
            if not os.path.exists(input_var.get()):
                messagebox.showerror("Validation Error", "Input File does not exist.")
                return False
            
            if not product_output_var.get().strip():
                messagebox.showerror("Validation Error", "Product Output File is required.")
                return False
            
            if not collections_output_var.get().strip():
                messagebox.showerror("Validation Error", "Collections Output File is required.")
                return False
            
            if not log_file_var.get().strip():
                messagebox.showerror("Validation Error", "Log File is required.")
                return False
            
            if not cfg.get("SHOPIFY_STORE_URL", "").strip():
                messagebox.showerror("Validation Error", "Shopify Store URL is required.\n\nPlease configure it in Settings.")
                return False
            
            if not cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip():
                messagebox.showerror("Validation Error", "Shopify Access Token is required.\n\nPlease configure it in Settings.")
                return False
            
            return True
        except Exception as e:
            messagebox.showerror("Validation Error", f"Unexpected error during validation:\n\n{str(e)}")
            return False
    
    def validate_and_start():
        """Validate inputs and start processing."""
        if not validate_inputs():
            return

        clear_status()

        start_btn.config(state="disabled")
        validate_btn.config(state="disabled")
        delete_log_btn.config(state="disabled")

        def run_processing():
            try:
                # Get execution mode from config
                execution_mode = cfg.get("EXECUTION_MODE", "resume")
                print("DEBUG: Starting process_products()")
                process_products(cfg, status, execution_mode=execution_mode)
                print("DEBUG: process_products() completed normally")
            except Exception as e:
                print(f"DEBUG: Exception in process_products(): {e}")
                status(f"❌ Fatal error: {e}")
                logging.exception("Full traceback:")
            finally:
                print("DEBUG: Finally block reached - re-enabling buttons via queue")
                # Always re-enable buttons, even if there was an error
                status("")  # Add blank line after completion
                status("=" * 80)
                status("Processing stopped. Buttons re-enabled.")
                status("=" * 80)
                # Send signal to re-enable buttons via queue (thread-safe)
                print("DEBUG: Putting enable_buttons signal into queue")
                button_control_queue.put("enable_buttons")
                print("DEBUG: enable_buttons signal queued successfully")

        thread = threading.Thread(target=run_processing, daemon=True)
        thread.start()
    
    # TEST BUTTON: Add a test button to verify status function works
    def test_status_button():
        """Test button to verify status function works."""
        import datetime
        status(f"Test button clicked at {datetime.datetime.now().strftime('%H:%M:%S')}")
        status("If you see this, the status function is working!")

    test_btn = tb.Button(
        button_frame,
        text="Test Status",
        command=test_status_button,
        bootstyle="warning"
    )
    test_btn.pack(side="left", padx=5)

    validate_btn = tb.Button(
        button_frame,
        text="Validate Settings",
        command=validate_inputs,
        bootstyle="info"
    )
    validate_btn.pack(side="left", padx=5)
    
    start_btn = tb.Button(
        button_frame,
        text="Start Processing",
        command=validate_and_start,
        bootstyle="success"
    )
    start_btn.pack(side="left", padx=5)
    
    delete_log_btn = tb.Button(
        button_frame,
        text="Delete Log File",
        command=delete_log_file,
        bootstyle="danger-outline"
    )
    delete_log_btn.pack(side="left", padx=5)
    
    def on_closing():
        """Handle window close event."""
        try:
            cfg["WINDOW_GEOMETRY"] = app.geometry()
            save_config(cfg)
        except Exception as e:
            logging.warning(f"Failed to save window geometry: {e}")
        app.quit()
    
    exit_btn = tb.Button(
        button_frame,
        text="Exit",
        command=on_closing,
        bootstyle="secondary"
    )
    exit_btn.pack(side="left", padx=5)
    
    # Status field
    status_label = tb.Label(app, text="Status Log:", anchor="w")
    status_label.pack(anchor="w", padx=10, pady=(10, 0))
    
    status_log = tb.Text(app, height=100, state="normal")  # Start in normal state for testing
    status_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # Create a queue for thread-safe status updates
    status_queue = queue.Queue()

    # Create a queue for thread-safe button control signals
    button_control_queue = queue.Queue()

    # Test: Try writing directly to widget
    try:
        status_log.insert("1.0", "=== DIRECT WRITE TEST ===\n")
        status_log.insert("end", "If you see this, the Text widget is working\n")
        status_log.insert("end", "=" * 80 + "\n")
        print("DEBUG: Direct write to Text widget succeeded")
    except Exception as e:
        print(f"ERROR: Direct write to Text widget failed: {e}")

    def process_status_queue():
        """Process all pending status messages and button control signals from queues. Runs in main thread."""
        try:
            # Process status messages
            messages_processed = 0
            messages = []
            while True:
                try:
                    msg = status_queue.get_nowait()
                    messages.append(msg)
                    messages_processed += 1
                except queue.Empty:
                    break

            # If we have messages, update the widget in one batch
            if messages_processed > 0:
                # Enable widget temporarily to allow insertion
                status_log.config(state="normal")
                for msg in messages:
                    status_log.insert("end", msg + "\n")
                status_log.see("end")
                # Re-disable to prevent user editing
                status_log.config(state="disabled")

                print(f"DEBUG: Processed {messages_processed} status messages from queue")
                # CRITICAL: Force widget to update display after batch insert
                status_log.update_idletasks()
                print(f"DEBUG: Widget display refreshed")

            # Process button control signals
            while True:
                try:
                    signal = button_control_queue.get_nowait()
                    if signal == "enable_buttons":
                        print("DEBUG: Processing enable_buttons signal from queue")
                        start_btn.config(state="normal")
                        validate_btn.config(state="normal")
                        delete_log_btn.config(state="normal")
                        print("DEBUG: Buttons re-enabled successfully via queue")
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"ERROR: Failed to process button control signal: {e}")
                    logging.error(f"Failed to process button control signal: {e}", exc_info=True)

        except Exception as e:
            print(f"ERROR processing status queue: {e}")
            logging.error(f"Error processing status queue: {e}", exc_info=True)

        # Schedule next queue check (every 50ms for responsive updates)
        app.after(50, process_status_queue)

    def status(msg):
        """Update status with auto-scroll to bottom. Thread-safe using queue."""
        # Debug: confirm status function is being called
        print(f"DEBUG: status() called with: {msg[:80] if len(msg) > 80 else msg}")

        try:
            # Put message in queue - works from any thread
            status_queue.put(msg)
            print(f"DEBUG: Message added to queue")
        except Exception as e:
            logging.error(f"Failed to queue status message: {e}", exc_info=True)
            print(f"ERROR queuing status message: {e}")
    
    def clear_status():
        """Clear status field."""
        try:
            status_log.config(state="normal")
            status_log.delete("1.0", "end")
            status_log.config(state="disabled")
        except Exception as e:
            logging.warning(f"Failed to clear status UI: {e}")
    
    app.protocol("WM_DELETE_WINDOW", on_closing)

    # Start the queue processor (runs in main thread via app.after())
    print("DEBUG: Starting status queue processor...")
    app.after(50, process_status_queue)

    # Test: Add initial message to verify status log works
    status("=" * 80)
    status(f"{SCRIPT_VERSION}")
    status("GUI loaded successfully")
    status("=" * 80)
    status("")

    app.mainloop()


