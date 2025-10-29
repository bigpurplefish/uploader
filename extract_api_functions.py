"""
Script to extract API functions from uploader.py and create shopify_api.py module.
"""

import re

# Read the original file
with open('uploader.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# API functions to extract (function name -> True)
api_functions = {
    'get_sales_channel_ids',
    'publish_collection_to_channels',
    'publish_product_to_channels',
    'delete_shopify_product',
    'search_collection',
    'create_collection',
    'create_metafield_definition',
    'upload_model_to_shopify',
    'search_shopify_taxonomy',
    'get_taxonomy_id',
}

# Extract functions
extracted_functions = []
current_function = None
function_lines = []
indent_level = 0

for i, line in enumerate(lines):
    # Check if this is a function definition
    match = re.match(r'^def (\w+)\(', line)
    if match:
        # Save previous function if it was an API function
        if current_function and current_function in api_functions:
            extracted_functions.append('\n'.join(function_lines))
            extracted_functions.append('\n')  # Add blank line between functions

        # Start new function
        current_function = match.group(1)
        function_lines = [line]
        indent_level = 0
    elif current_function:
        # Continue collecting lines for current function
        # Stop when we hit another top-level definition or class
        if line and not line[0].isspace() and not line.startswith('def ') and line.strip():
            # End of function - save if it's an API function
            if current_function in api_functions:
                extracted_functions.append('\n'.join(function_lines))
                extracted_functions.append('\n')
            current_function = None
            function_lines = []
        else:
            function_lines.append(line)

# Don't forget the last function
if current_function and current_function in api_functions:
    extracted_functions.append('\n'.join(function_lines))

# Create the shopify_api.py module
api_module_content = '''"""
Shopify API operations for Product Uploader.

This module contains all functions that interact with the Shopify GraphQL Admin API.
"""

import logging
import requests
from .config import log_and_status
from .state import save_taxonomy_cache
from .utils import key_to_label


'''

api_module_content += '\n'.join(extracted_functions)

# Write to uploader_modules/shopify_api.py
with open('uploader_modules/shopify_api.py', 'w', encoding='utf-8') as f:
    f.write(api_module_content)

print(f"Extracted {len(api_functions)} API functions to uploader_modules/shopify_api.py")
