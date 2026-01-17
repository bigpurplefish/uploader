"""
GUI implementation for Shopify Product Uploader.

This module contains the tkinter/ttkbootstrap GUI code.
"""

import os
import threading
import logging
import queue
import datetime
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip

from .config import load_config, save_config, SCRIPT_VERSION
from .product_processing import process_products


def open_system_settings(cfg, parent):
    """Open the system settings dialog."""
    settings_window = tb.Toplevel(parent)
    settings_window.title("System Settings")
    settings_window.geometry("700x450")
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

    # Configure column weights
    main_frame.columnconfigure(1, weight=1)

    # Button frame
    button_frame = tb.Frame(settings_window)
    button_frame.pack(side="bottom", fill="x", padx=20, pady=20)

    def save_settings():
        """Save settings and close dialog."""
        cfg["SHOPIFY_STORE_URL"] = store_url_var.get().strip()
        cfg["SHOPIFY_ACCESS_TOKEN"] = access_token_var.get().strip()

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
    """Build the main GUI application with tabbed interface."""
    global cfg
    cfg = load_config()

    app = tb.Window(themename="darkly")
    app.title("Shopify Product Uploader")
    app.geometry(cfg.get("WINDOW_GEOMETRY", "900x800"))

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

    # Title
    title_frame = tb.Frame(app)
    title_frame.pack(fill="x", padx=10, pady=(5, 10))
    tb.Label(title_frame, text="Shopify Product Uploader", font=("Arial", 14, "bold")).pack()

    # Create Notebook (tabbed interface)
    notebook = tb.Notebook(app, bootstyle="primary")
    notebook.pack(fill="x", padx=10, pady=(0, 5))

    # ==================== TAB 1: FILES ====================
    files_tab = tb.Frame(notebook, padding=15)
    notebook.add(files_tab, text="  Files  ")
    files_tab.columnconfigure(1, weight=1)

    # Input File field
    row = 0

    label_frame = tb.Frame(files_tab)
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
    tb.Entry(files_tab, textvariable=input_var, width=50).grid(
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

    tb.Button(files_tab, text="Browse", command=browse_input, bootstyle="info-outline").grid(
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
    row += 1

    label_frame = tb.Frame(files_tab)
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
    tb.Entry(files_tab, textvariable=product_output_var, width=50).grid(
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

    tb.Button(files_tab, text="Browse", command=browse_product_output, bootstyle="info-outline").grid(
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
    row += 1

    label_frame = tb.Frame(files_tab)
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
    tb.Entry(files_tab, textvariable=collections_output_var, width=50).grid(
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

    tb.Button(files_tab, text="Browse", command=browse_collections_output, bootstyle="info-outline").grid(
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
    row += 1

    label_frame = tb.Frame(files_tab)
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
    tb.Entry(files_tab, textvariable=log_file_var, width=50).grid(
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

    tb.Button(files_tab, text="Browse", command=browse_log_file, bootstyle="info-outline").grid(
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

    tb.Button(files_tab, text="Delete", command=delete_log_file, bootstyle="danger-outline").grid(
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

    # ==================== TAB 2: PROCESSING ====================
    processing_tab = tb.Frame(notebook, padding=15)
    notebook.add(processing_tab, text="  Processing  ")
    processing_tab.columnconfigure(1, weight=1)

    # Execution Mode toggle
    row = 0

    label_frame = tb.Frame(processing_tab)
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
    mode_frame = tb.Frame(processing_tab)
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

    # Start Record field
    row += 1

    label_frame = tb.Frame(processing_tab)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Start Record", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    tooltip_text = (
        "Specify the first record to process (1-based index).\n\n"
        "Leave blank to start from the beginning.\n"
        "Example: Enter '10' to start from the 10th record.\n\n"
        "Tip: Blank = process from start."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")

    # Use StringVar to allow blank values in spinbox
    start_val = cfg.get("START_RECORD", "")
    start_record_var = tb.StringVar(value=start_val)
    start_spinbox = tb.Spinbox(
        processing_tab,
        textvariable=start_record_var,
        from_=0,
        to=999999,
        increment=1,
        width=10
    )
    start_spinbox.grid(row=row, column=1, sticky="w", padx=5, pady=5)

    def on_start_record_change(*args):
        """Auto-save start record to config."""
        try:
            val = start_record_var.get().strip()
            # Validate it's a number or blank
            if val:
                int(val)  # Validate it's a valid integer
            cfg["START_RECORD"] = val
            save_config(cfg)
        except (ValueError, Exception):
            # Handle invalid spinbox values gracefully
            cfg["START_RECORD"] = ""
            save_config(cfg)

    start_record_var.trace_add("write", on_start_record_change)

    # End Record field
    row += 1

    label_frame = tb.Frame(processing_tab)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="End Record", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    tooltip_text = (
        "Specify the last record to process (1-based index).\n\n"
        "Leave blank to process until the end.\n"
        "Example: Enter '50' to stop processing after the 50th record.\n\n"
        "Tip: Blank = process to end."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")

    # Use StringVar to allow blank values in spinbox
    end_val = cfg.get("END_RECORD", "")
    end_record_var = tb.StringVar(value=end_val)
    end_spinbox = tb.Spinbox(
        processing_tab,
        textvariable=end_record_var,
        from_=0,
        to=999999,
        increment=1,
        width=10
    )
    end_spinbox.grid(row=row, column=1, sticky="w", padx=5, pady=5)

    def on_end_record_change(*args):
        """Auto-save end record to config."""
        try:
            val = end_record_var.get().strip()
            # Validate it's a number or blank
            if val:
                int(val)  # Validate it's a valid integer
            cfg["END_RECORD"] = val
            save_config(cfg)
        except (ValueError, Exception):
            # Handle invalid spinbox values gracefully
            cfg["END_RECORD"] = ""
            save_config(cfg)

    end_record_var.trace_add("write", on_end_record_change)

    # Inventory Quantity field
    row += 1

    label_frame = tb.Frame(processing_tab)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Inventory Quantity", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    tooltip_text = (
        "Specify the inventory quantity to set for all variants.\n\n"
        "This quantity will be applied to your default location.\n"
        "Leave blank or set to 0 to skip inventory quantity setting.\n\n"
        "Example: Enter '100' to set 100 units for each variant."
    )
    ToolTip(help_icon, text=tooltip_text, bootstyle="info")

    # Use StringVar to allow blank values in spinbox
    inv_qty_val = cfg.get("INVENTORY_QUANTITY", "")
    inventory_qty_var = tb.StringVar(value=inv_qty_val)
    inventory_qty_spinbox = tb.Spinbox(
        processing_tab,
        textvariable=inventory_qty_var,
        from_=0,
        to=999999,
        increment=1,
        width=10
    )
    inventory_qty_spinbox.grid(row=row, column=1, sticky="w", padx=5, pady=5)

    def on_inventory_qty_change(*args):
        """Auto-save inventory quantity to config."""
        try:
            val = inventory_qty_var.get().strip()
            # Validate it's a number or blank
            if val:
                int(val)  # Validate it's a valid integer
            cfg["INVENTORY_QUANTITY"] = val
            save_config(cfg)
        except (ValueError, Exception):
            # Handle invalid spinbox values gracefully
            cfg["INVENTORY_QUANTITY"] = ""
            save_config(cfg)

    inventory_qty_var.trace_add("write", on_inventory_qty_change)

    # ==================== BUTTONS (outside tabs) ====================
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

                # Get start/end record values (convert to int or None)
                start_record = None
                end_record = None
                try:
                    start_val = start_record_var.get().strip()
                    if start_val:
                        start_record = int(start_val)
                except (ValueError, Exception):
                    start_record = None

                try:
                    end_val = end_record_var.get().strip()
                    if end_val:
                        end_record = int(end_val)
                except (ValueError, Exception):
                    end_record = None

                print("DEBUG: Starting process_products()")
                process_products(cfg, status, execution_mode=execution_mode,
                               start_record=start_record, end_record=end_record)
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

    # Debounced window geometry saving
    geometry_save_pending = {"after_id": None, "last_geometry": None}

    def save_geometry_debounced():
        """Actually save the geometry after debounce delay."""
        try:
            current_geometry = app.geometry()
            # Only save if geometry actually changed
            if current_geometry != geometry_save_pending["last_geometry"]:
                cfg["WINDOW_GEOMETRY"] = current_geometry
                save_config(cfg)
                geometry_save_pending["last_geometry"] = current_geometry
        except Exception as e:
            logging.warning(f"Failed to save window geometry: {e}")
        finally:
            geometry_save_pending["after_id"] = None

    def on_window_configure(event):
        """Handle window resize/move with debounce."""
        # Only respond to events on the main window, not child widgets
        if event.widget != app:
            return

        # Cancel any pending save
        if geometry_save_pending["after_id"] is not None:
            app.after_cancel(geometry_save_pending["after_id"])

        # Schedule a new save after 500ms debounce delay
        geometry_save_pending["after_id"] = app.after(500, save_geometry_debounced)

    # Initialize last_geometry with current value
    geometry_save_pending["last_geometry"] = cfg.get("WINDOW_GEOMETRY", "900x800")

    # Bind to Configure event (fires on resize and move)
    app.bind("<Configure>", on_window_configure)

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

    # Set widget to disabled state (read-only for user)
    status_log.config(state="disabled")

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
        """Clear status field and any pending messages in the queue."""
        try:
            # Clear any pending messages in the queue first
            while True:
                try:
                    status_queue.get_nowait()
                except queue.Empty:
                    break

            # Clear the text widget
            status_log.config(state="normal")
            status_log.delete("1.0", "end")
            status_log.config(state="disabled")

            # Add header for new run
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status("=" * 80)
            status(f"New Run Started: {timestamp}")
            status("=" * 80)
            status("")
        except Exception as e:
            logging.warning(f"Failed to clear status UI: {e}")
            print(f"ERROR: Failed to clear status UI: {e}")
    
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


