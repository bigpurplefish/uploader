#!/usr/bin/env python3
"""
Shopify Product Uploader - Main Entry Point

Version 2.6.0 - Refactored Modular Structure
Shopify GraphQL Admin API 2025-10

This is the main entry point for the Shopify Product Uploader application.
All functionality has been refactored into separate modules for better maintainability.
"""

import sys
import logging

# Import the GUI module and version
try:
    from uploader_modules.config import SCRIPT_VERSION
    from uploader_modules.gui import build_gui
except ImportError as e:
    print(f"Error importing uploader_modules: {e}")
    print("Make sure the uploader_modules package is in the same directory as this script.")
    sys.exit(1)

# Print version info
print(f"Starting {SCRIPT_VERSION}")


def main():
    """Main entry point for the application."""
    try:
        build_gui()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        logging.exception("Fatal error in main:")
        sys.exit(1)


if __name__ == "__main__":
    main()
