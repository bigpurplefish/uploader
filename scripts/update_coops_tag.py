"""
One-time script: rename "Supplies (coops; feeders; waterers)" tag to
"Supplies (coops | feeders | waterers)" across products, collection, and menu.
"""

import json
import sys
import time
import logging
import requests

sys.path.insert(0, '/Users/moosemarketer/Code/garoppos/uploader')
from uploader_modules.config import load_config
from uploader_modules.shopify_api import (
    update_shopify_product,
    get_menu_by_handle,
    update_menu,
    invalidate_menu_cache,
    convert_menu_items_for_update,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

OLD_TAG = "Supplies (coops; feeders; waterers)"
NEW_TAG = "Supplies (coops | feeders | waterers)"

cfg = load_config()
store_url = cfg['SHOPIFY_STORE_URL'].strip().replace('https://','').replace('http://','')
access_token = cfg['SHOPIFY_ACCESS_TOKEN'].strip()
api_url = f'https://{store_url}/admin/api/2025-10/graphql.json'
headers = {'Content-Type': 'application/json', 'X-Shopify-Access-Token': access_token}


# ─────────────────────────────────────────────────────────────
# STEP 1: Update product tags
# ─────────────────────────────────────────────────────────────

def fetch_products_with_tag(tag):
    """Paginate through all products matching the given tag."""
    products = []
    cursor = None
    query_template = """
    query($cursor: String) {
      products(first: 50, after: $cursor, query: "tag:\\"%s\\"") {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
            title
            tags
          }
        }
      }
    }
    """ % tag

    while True:
        variables = {"cursor": cursor}
        resp = requests.post(api_url, json={"query": query_template, "variables": variables}, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            logging.error(f"GraphQL errors fetching products: {data['errors']}")
            break
        products_data = data.get("data", {}).get("products", {})
        for edge in products_data.get("edges", []):
            products.append(edge["node"])
        page_info = products_data.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            cursor = page_info["endCursor"]
        else:
            break
    return products


logging.info("=== STEP 1: Updating product tags ===")
products = fetch_products_with_tag(OLD_TAG)
logging.info(f"Found {len(products)} products with tag '{OLD_TAG}'")

updated_count = 0
failed_count = 0

for i, product in enumerate(products):
    product_id = product["id"]
    old_tags = product["tags"]

    # Replace old tag with new tag
    new_tags = [NEW_TAG if t == OLD_TAG else t for t in old_tags]

    if new_tags == old_tags:
        logging.warning(f"  [{i+1}/{len(products)}] No change needed for {product['title']} ({product_id})")
        continue

    result = update_shopify_product(product_id, {"tags": new_tags}, cfg)
    if result:
        logging.info(f"  [{i+1}/{len(products)}] Updated: {product['title']}")
        updated_count += 1
    else:
        logging.error(f"  [{i+1}/{len(products)}] FAILED: {product['title']} ({product_id})")
        failed_count += 1

    time.sleep(0.3)

logging.info(f"Product tags: {updated_count} updated, {failed_count} failed, {len(products)} total")


# ─────────────────────────────────────────────────────────────
# STEP 2: Update the collection
# ─────────────────────────────────────────────────────────────

logging.info("=== STEP 2: Updating collection ===")

# Find collection by title
find_query = """
query {
  collections(first: 10, query: "title:'Supplies (coops; feeders; waterers)'") {
    edges {
      node {
        id
        title
        productsCount { count }
        ruleSet {
          appliedDisjunctively
          rules { column relation condition }
        }
      }
    }
  }
}
"""
resp = requests.post(api_url, json={"query": find_query}, headers=headers, timeout=30)
resp.raise_for_status()
coll_data = resp.json()

if "errors" in coll_data:
    logging.error(f"GraphQL errors finding collection: {coll_data['errors']}")
    collection_id = None
else:
    edges = coll_data.get("data", {}).get("collections", {}).get("edges", [])
    collection_id = None
    for edge in edges:
        if edge["node"]["title"] == OLD_TAG:
            collection_id = edge["node"]["id"]
            logging.info(f"Found collection: {edge['node']['title']} ({collection_id}), products: {edge['node']['productsCount']['count']}")
            break
    if not collection_id:
        logging.warning(f"Collection '{OLD_TAG}' not found. edges returned: {len(edges)}")

if collection_id:
    coll_mutation = """
    mutation collectionUpdate($input: CollectionInput!) {
      collectionUpdate(input: $input) {
        collection { id title productsCount { count } }
        userErrors { field message }
      }
    }
    """
    coll_input = {
        "id": collection_id,
        "title": NEW_TAG,
        "ruleSet": {
            "appliedDisjunctively": False,
            "rules": [
                {"column": "TAG", "relation": "EQUALS", "condition": "Chickens"},
                {"column": "TAG", "relation": "EQUALS", "condition": NEW_TAG}
            ]
        }
    }
    resp = requests.post(api_url, json={"query": coll_mutation, "variables": {"input": coll_input}}, headers=headers, timeout=30)
    resp.raise_for_status()
    coll_result = resp.json()
    if "errors" in coll_result:
        logging.error(f"GraphQL errors updating collection: {coll_result['errors']}")
    else:
        user_errors = coll_result.get("data", {}).get("collectionUpdate", {}).get("userErrors", [])
        if user_errors:
            logging.error(f"Collection update userErrors: {user_errors}")
        else:
            updated_coll = coll_result.get("data", {}).get("collectionUpdate", {}).get("collection", {})
            logging.info(f"Collection updated: '{updated_coll.get('title')}' ({updated_coll.get('id')}), products: {updated_coll.get('productsCount', {}).get('count')}")


# ─────────────────────────────────────────────────────────────
# STEP 3: Update the menu item
# ─────────────────────────────────────────────────────────────

logging.info("=== STEP 3: Updating menu item ===")

invalidate_menu_cache()
menu = get_menu_by_handle("main-menu", cfg)
if not menu:
    logging.error("Could not retrieve main-menu — skipping menu update")
else:
    menu_id = menu["id"]
    menu_title = menu["title"]
    logging.info(f"Retrieved menu '{menu_title}' ({menu_id})")

    # Navigate the nested items to find and rename the target
    def rename_item_recursive(items, old_title, new_title, path=""):
        found = False
        for item in items:
            current_path = f"{path} > {item.get('title', '')}" if path else item.get('title', '')
            if item.get("title") == old_title:
                logging.info(f"  Found menu item at: {current_path}")
                item["title"] = new_title
                found = True
            # Recurse into children
            if item.get("items"):
                child_found = rename_item_recursive(item["items"], old_title, new_title, current_path)
                if child_found:
                    found = True
        return found

    items = menu.get("items", [])
    found = rename_item_recursive(items, OLD_TAG, NEW_TAG)

    if not found:
        logging.warning(f"Menu item '{OLD_TAG}' not found in main-menu")
    else:
        converted_items = convert_menu_items_for_update(items)
        success = update_menu(menu_id, menu_title, converted_items, cfg)
        if success:
            logging.info(f"Menu item renamed to '{NEW_TAG}'")
        else:
            logging.error("Menu update failed")

logging.info("=== Done ===")
