"""
Script to extract GUI code from uploader.py and create gui.py module.
"""

# Read the original file
with open('uploader.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the build_gui function (starts around line 2943)
# Extract from build_gui to the end of file (excluding if __name__ == "__main__")
gui_lines = []
capturing = False
for i, line in enumerate(lines):
    if line.startswith('def build_gui():'):
        capturing = True

    if capturing:
        # Stop at if __name__ == "__main__"
        if line.startswith('if __name__ =='):
            break
        gui_lines.append(line)

# Create the gui.py module
gui_module_content = '''"""
GUI implementation for Shopify Product Uploader.

This module contains the tkinter/ttkbootstrap GUI code.
"""

import os
import threading
import logging
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip

from .config import load_config, save_config
from .product_processing import process_products


SCRIPT_VERSION = "2.6.0 - Shopify Product Uploader (API 2025-10 Fix - No Duplicate Variants)"


'''

gui_module_content += ''.join(gui_lines)

# Write to uploader_modules/gui.py
with open('uploader_modules/gui.py', 'w', encoding='utf-8') as f:
    f.write(gui_module_content)

print(f"Extracted GUI code to uploader_modules/gui.py")
