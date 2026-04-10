#!/usr/bin/env python3
"""
Reassign Stepping Stone products to Lawn and Garden > Garden Decor > Stepping Stones.

Steps:
1. Search Shopify for products with "Stepping Stone" or "Stepping Stones" in title
2. Create "Stepping Stones" subcollection if it doesn't exist
3. Update each product's product_type and tags
4. Ensure menu items exist for the new taxonomy path
"""

import sys
import os
import json
import logging
import time

# Add uploader root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config
from uploader_modules.shopify_api import (
    search_collection,
    create_collection,
    update_shopify_product,
    get_menu_by_handle,
    ensure_menu_items_for_product,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEPARTMENT = "Lawn and Garden"
CATEGORY = "Garden Decor"
SUBCATEGORY = "Stepping Stones"

# Search terms - both singular and plural
SEARCH_TERMS = ["Stepping Stone", "Stepping Stones"]


def search_products_by_term(term, cfg):
    """Search Shopify for products matching a term (wildcard title search)."""
    import requests

    store_url = cfg.get("SHOPIFY_STORE_URL", "").strip().replace("https://", "").replace("http://", "")
    access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()
    api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": access_token}

    # Use wildcard search (no quotes) to find partial matches
    query = """
    query searchProducts($query: String!, $cursor: String) {
      products(first: 50, query: $query, after: $cursor) {
        edges {
          node {
            id
            title
            handle
            productType
            tags
          }
          cursor
        }
        pageInfo { hasNextPage }
      }
    }
    """

    all_products = []
    cursor = None

    while True:
        variables = {"query": f"title:*{term}*"}
        if cursor:
            variables["cursor"] = cursor

        response = requests.post(api_url, json={"query": query, "variables": variables}, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logging.error(f"GraphQL errors: {data['errors']}")
            break

        edges = data.get("data", {}).get("products", {}).get("edges", [])
        for edge in edges:
            node = edge["node"]
            # Filter: title must actually contain the term (case-insensitive)
            if term.lower() in node["title"].lower():
                all_products.append(node)
            cursor = edge.get("cursor")

        if not data.get("data", {}).get("products", {}).get("pageInfo", {}).get("hasNextPage"):
            break

    return all_products


def main():
    cfg = load_config()

    if not cfg.get("SHOPIFY_STORE_URL") or not cfg.get("SHOPIFY_ACCESS_TOKEN"):
        logging.error("Shopify credentials not configured in config.json")
        sys.exit(1)

    # --- Step 1: Find all stepping stone products ---
    logging.info("=" * 60)
    logging.info("STEP 1: Searching for Stepping Stone products")
    logging.info("=" * 60)

    seen_ids = set()
    products = []

    for term in SEARCH_TERMS:
        logging.info(f"  Searching for: {term}")
        found = search_products_by_term(term, cfg)
        for p in found:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                products.append(p)
                logging.info(f"    Found: {p['title']} (type={p['productType']}, tags={p['tags']})")

    if not products:
        logging.info("  No stepping stone products found. Nothing to do.")
        return

    logging.info(f"\n  Total unique products found: {len(products)}")

    # Show which are already correctly assigned
    needs_update = []
    already_correct = []
    for p in products:
        tags = p.get("tags", [])
        if (p.get("productType") == DEPARTMENT and CATEGORY in tags and SUBCATEGORY in tags):
            already_correct.append(p)
        else:
            needs_update.append(p)

    if already_correct:
        logging.info(f"  Already correctly assigned: {len(already_correct)}")
        for p in already_correct:
            logging.info(f"    ✓ {p['title']}")

    if not needs_update:
        logging.info("  All products already have correct taxonomy.")
    else:
        logging.info(f"  Need reassignment: {len(needs_update)}")
        for p in needs_update:
            logging.info(f"    → {p['title']} (current: type={p['productType']}, tags={p['tags']})")

    # --- Step 2: Create subcollection if needed ---
    logging.info("\n" + "=" * 60)
    logging.info("STEP 2: Ensuring 'Stepping Stones' collection exists")
    logging.info("=" * 60)

    existing = search_collection(SUBCATEGORY, cfg)
    if existing:
        logging.info(f"  Collection already exists: {existing['id']} (handle: {existing['handle']})")
        collection_info = existing
    else:
        logging.info(f"  Creating subcategory collection: {SUBCATEGORY}")
        rules = [
            {"column": "TAG", "relation": "EQUALS", "condition": CATEGORY},
            {"column": "TAG", "relation": "EQUALS", "condition": SUBCATEGORY},
        ]
        result = create_collection(SUBCATEGORY, rules, cfg, description=f"Shop stepping stones and decorative garden path stones.")
        if result:
            logging.info(f"  ✓ Created collection: {result['id']} (handle: {result['handle']})")
            collection_info = result
        else:
            logging.error("  ✗ Failed to create collection")
            collection_info = None

    # --- Step 3: Update products ---
    if needs_update:
        logging.info("\n" + "=" * 60)
        logging.info("STEP 3: Reassigning products")
        logging.info("=" * 60)

        for p in needs_update:
            product_id = p["id"]
            title = p["title"]

            # Build new tags: keep existing, add category + subcategory if missing
            current_tags = p.get("tags", [])
            new_tags = list(current_tags)  # copy

            if CATEGORY not in new_tags:
                new_tags.append(CATEGORY)
            if SUBCATEGORY not in new_tags:
                new_tags.append(SUBCATEGORY)

            update_input = {
                "productType": DEPARTMENT,
                "tags": new_tags,
            }

            logging.info(f"  Updating: {title}")
            logging.info(f"    productType: {p.get('productType', '')} → {DEPARTMENT}")
            logging.info(f"    tags: {current_tags} → {new_tags}")

            result = update_shopify_product(product_id, update_input, cfg)
            if result:
                logging.info(f"    ✓ Updated successfully")
            else:
                logging.error(f"    ✗ Failed to update {title}")

            time.sleep(0.5)  # Rate limit

    # --- Step 4: Ensure menu items ---
    logging.info("\n" + "=" * 60)
    logging.info("STEP 4: Ensuring menu items for Lawn and Garden > Garden Decor > Stepping Stones")
    logging.info("=" * 60)

    # Build a fake product dict to drive the menu function
    menu_product = {
        "product_type": DEPARTMENT,
        "tags": [CATEGORY, SUBCATEGORY],
    }

    # Build collections_data with what we know
    collections_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "collections.json")
    collections_data = {"collections": []}
    if os.path.exists(collections_file):
        with open(collections_file, "r") as f:
            collections_data = json.load(f)

    # Add collection info if we have it
    if collection_info:
        # Check if already in collections_data
        found_in_data = False
        for col in collections_data.get("collections", []):
            if col.get("name", "").lower() == SUBCATEGORY.lower():
                found_in_data = True
                break
        if not found_in_data:
            collections_data["collections"].append({
                "name": SUBCATEGORY,
                "handle": collection_info.get("handle", "stepping-stones"),
                "id": collection_info.get("id"),
            })

    result = ensure_menu_items_for_product(menu_product, collections_data, cfg, status_fn=print)
    if result:
        logging.info("  ✓ Menu items ensured")
    else:
        logging.error("  ✗ Failed to update menu")

    # --- Summary ---
    logging.info("\n" + "=" * 60)
    logging.info("SUMMARY")
    logging.info("=" * 60)
    logging.info(f"  Products found: {len(products)}")
    logging.info(f"  Already correct: {len(already_correct)}")
    logging.info(f"  Reassigned: {len(needs_update)}")
    logging.info(f"  Collection: {'exists' if existing else ('created' if collection_info else 'FAILED')}")
    logging.info(f"  Menu: updated")


if __name__ == "__main__":
    main()
