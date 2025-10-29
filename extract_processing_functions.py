"""
Script to extract processing functions from uploader.py and create product_processing.py module.
"""

import re

# Read the original file
with open('uploader.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Processing functions to extract
processing_functions = {
    'process_collections',
    'process_products',
    'ensure_metafield_definitions',
}

# Extract functions
extracted_functions = []
current_function = None
function_lines = []

for i, line in enumerate(lines):
    # Check if this is a function definition
    match = re.match(r'^def (\w+)\(', line)
    if match:
        # Save previous function if it was a processing function
        if current_function and current_function in processing_functions:
            extracted_functions.append('\n'.join(function_lines))
            extracted_functions.append('\n')  # Add blank line between functions

        # Start new function
        current_function = match.group(1)
        function_lines = [line]
    elif current_function:
        # Continue collecting lines for current function
        # Stop when we hit another top-level definition or class
        if line and not line[0].isspace() and not line.startswith('def ') and line.strip():
            # End of function - save if it's a processing function
            if current_function in processing_functions:
                extracted_functions.append('\n'.join(function_lines))
                extracted_functions.append('\n')
            current_function = None
            function_lines = []
        else:
            function_lines.append(line)

# Don't forget the last function
if current_function and current_function in processing_functions:
    extracted_functions.append('\n'.join(function_lines))

# Create the product_processing.py module
processing_module_content = '''"""
Product and collection processing logic for Shopify Product Uploader.

This module contains the main business logic for processing products and collections.
"""

import json
import time
import logging
import requests
from datetime import datetime

from .config import log_and_status, setup_logging
from .state import (
    load_collections, save_collections, load_products, save_products,
    load_taxonomy_cache, update_product_in_restore
)
from .shopify_api import (
    get_sales_channel_ids, search_collection, create_collection,
    publish_collection_to_channels, publish_product_to_channels,
    delete_shopify_product, create_metafield_definition,
    upload_model_to_shopify, get_taxonomy_id
)
from .utils import (
    extract_category_subcategory, extract_unique_option_values,
    key_to_label
)


'''

processing_module_content += '\n'.join(extracted_functions)

# Write to uploader_modules/product_processing.py
with open('uploader_modules/product_processing.py', 'w', encoding='utf-8') as f:
    f.write(processing_module_content)

print(f"Extracted {len(processing_functions)} processing functions to uploader_modules/product_processing.py")
