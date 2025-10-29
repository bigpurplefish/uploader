"""
State file management for Shopify Product Uploader.

Handles upload_state.json, collections.json, products.json, and product_taxonomy.json
"""

import os
import json
import logging
from datetime import datetime

# File paths
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(APP_DIR, "upload_state.json")
COLLECTIONS_FILE = os.path.join(APP_DIR, "collections.json")
PRODUCTS_FILE = os.path.join(APP_DIR, "products.json")
TAXONOMY_FILE = os.path.join(APP_DIR, "product_taxonomy.json")


def load_state():
    """Load processing state from state file."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse upload_state.json: {e}. Starting fresh.")
    except IOError as e:
        logging.warning(f"Failed to read upload_state.json: {e}. Starting fresh.")
    except Exception as e:
        logging.warning(f"Unexpected error loading state: {e}. Starting fresh.")

    return {}


def save_state(state):
    """Save processing state to state file."""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        logging.error(f"Failed to write upload_state.json: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving state: {e}")


def load_collections():
    """Load collections tracking data from collections.json."""
    try:
        if os.path.exists(COLLECTIONS_FILE):
            with open(COLLECTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse collections.json: {e}. Starting fresh.")
    except IOError as e:
        logging.warning(f"Failed to read collections.json: {e}. Starting fresh.")
    except Exception as e:
        logging.warning(f"Unexpected error loading collections: {e}. Starting fresh.")

    return {
        "collections": [],
        "last_updated": datetime.now().isoformat()
    }


def save_collections(collections_data):
    """Save collections tracking data to collections.json."""
    try:
        collections_data["last_updated"] = datetime.now().isoformat()
        with open(COLLECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(collections_data, f, indent=4)
    except IOError as e:
        logging.error(f"Failed to write collections.json: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving collections: {e}")


def load_products():
    """
    Load products restore point data from products.json.
    This file tracks all products and serves as a granular restore point.

    Returns:
        Dictionary with products array indexed by title and metadata
    """
    try:
        if os.path.exists(PRODUCTS_FILE):
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert list to dict for faster lookups
                if "products" in data and isinstance(data["products"], list):
                    products_dict = {}
                    for product in data["products"]:
                        title_key = product.get("title", "").strip().lower()
                        if title_key:
                            products_dict[title_key] = product
                    data["products_dict"] = products_dict
                return data
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse products.json: {e}. Starting fresh.")
    except IOError as e:
        logging.warning(f"Failed to read products.json: {e}. Starting fresh.")
    except Exception as e:
        logging.warning(f"Unexpected error loading products: {e}. Starting fresh.")

    return {
        "products": [],
        "products_dict": {},
        "last_updated": datetime.now().isoformat()
    }


def save_products(products_data):
    """
    Save products restore point data to products.json.

    Args:
        products_data: Dictionary with products array and metadata
    """
    try:
        # Remove the temporary dict before saving
        save_data = {
            "products": products_data.get("products", []),
            "last_updated": datetime.now().isoformat()
        }

        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4)
    except IOError as e:
        logging.error(f"Failed to write products.json: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving products: {e}")


def update_product_in_restore(products_restore, product_data):
    """
    Update a specific product in the restore point data.

    Args:
        products_restore: Dictionary with products array
        product_data: Dictionary with product information to update

    Returns:
        Updated products_restore dictionary
    """
    title = product_data.get("title", "").strip()
    if not title:
        return products_restore

    title_key = title.lower()

    # Update in both list and dict
    products_list = products_restore.get("products", [])
    products_dict = products_restore.get("products_dict", {})

    # Check if product exists
    existing_idx = None
    for idx, product in enumerate(products_list):
        if product.get("title", "").strip().lower() == title_key:
            existing_idx = idx
            break

    if existing_idx is not None:
        # Update existing product
        products_list[existing_idx].update(product_data)
    else:
        # Add new product
        products_list.append(product_data)

    # Update dict
    products_dict[title_key] = product_data

    products_restore["products"] = products_list
    products_restore["products_dict"] = products_dict
    products_restore["last_updated"] = datetime.now().isoformat()

    return products_restore


def load_taxonomy_cache():
    """
    Load taxonomy cache from taxonomy file.

    Returns:
        Dictionary mapping category names to taxonomy IDs
    """
    try:
        if os.path.exists(TAXONOMY_FILE):
            with open(TAXONOMY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse taxonomy file: {e}. Starting fresh.")
    except IOError as e:
        logging.warning(f"Failed to read taxonomy file: {e}. Starting fresh.")
    except Exception as e:
        logging.warning(f"Unexpected error loading taxonomy: {e}. Starting fresh.")

    return {}


def save_taxonomy_cache(taxonomy_cache):
    """
    Save taxonomy cache to taxonomy file.

    Args:
        taxonomy_cache: Dictionary mapping category names to taxonomy IDs
    """
    try:
        with open(TAXONOMY_FILE, 'w', encoding='utf-8') as f:
            json.dump(taxonomy_cache, f, indent=4)
    except IOError as e:
        logging.error(f"Failed to write taxonomy file: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving taxonomy: {e}")
