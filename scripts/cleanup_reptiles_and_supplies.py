"""
Cleanup script:
1. Remove "Reptiles" (and its "Heating and Lighting" sub-item) from the main menu under Pet Supplies
2. Delete the orphan "Supplies" collection (0 products, not the Chickens Supplies one)
3. Check and handle empty Reptiles / Heating and Lighting collections
"""

import json
import sys
import requests
import logging

sys.path.insert(0, '/Users/moosemarketer/Code/garoppos/uploader')
from uploader_modules.config import load_config
from uploader_modules.shopify_api import (
    get_menu_by_handle,
    update_menu,
    invalidate_menu_cache,
    convert_menu_items_for_update,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

cfg = load_config()
store_url = cfg['SHOPIFY_STORE_URL'].strip().replace('https://', '').replace('http://', '')
access_token = cfg['SHOPIFY_ACCESS_TOKEN'].strip()
api_url = f'https://{store_url}/admin/api/2025-10/graphql.json'
headers = {'Content-Type': 'application/json', 'X-Shopify-Access-Token': access_token}


def gql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if "errors" in result:
        logging.error(f"GraphQL errors: {result['errors']}")
    return result


# =============================================================================
# TASK 1: Remove Reptiles from main menu
# =============================================================================
logging.info("=== TASK 1: Removing Reptiles from main menu ===")

invalidate_menu_cache()
menu = get_menu_by_handle("main-menu", cfg)
if not menu:
    logging.error("Could not fetch main-menu — aborting Task 1")
    sys.exit(1)

menu_id = menu["id"]
menu_title = menu["title"]
logging.info(f"Fetched menu: '{menu_title}' (id={menu_id})")

# Find Pet Supplies top-level item
items = menu.get("items", [])
pet_supplies_item = None
for item in items:
    if item.get("title") == "Pet Supplies":
        pet_supplies_item = item
        break

if not pet_supplies_item:
    logging.warning("'Pet Supplies' item not found in main menu — skipping Task 1")
else:
    # List current children of Pet Supplies
    pet_children = pet_supplies_item.get("items", [])
    logging.info(f"Pet Supplies has {len(pet_children)} children: {[c['title'] for c in pet_children]}")

    # Remove Reptiles (and its Heating and Lighting child will be removed automatically)
    reptiles_item = None
    for child in pet_children:
        if child.get("title") == "Reptiles":
            reptiles_item = child
            break

    if not reptiles_item:
        logging.warning("'Reptiles' not found under Pet Supplies — nothing to remove")
    else:
        reptiles_children = reptiles_item.get("items", [])
        logging.info(f"Reptiles sub-items: {[c['title'] for c in reptiles_children]}")

        # Filter out Reptiles
        new_pet_children = [c for c in pet_children if c.get("title") != "Reptiles"]
        logging.info(f"Pet Supplies children after removal: {[c['title'] for c in new_pet_children]}")

        # Rebuild menu items with updated Pet Supplies children
        pet_supplies_item["items"] = new_pet_children

        # Convert to update format
        converted = convert_menu_items_for_update(items)

        logging.info("Calling update_menu...")
        success = update_menu(menu_id, menu_title, converted, cfg)
        if success:
            logging.info("Menu updated successfully — Reptiles removed.")
        else:
            logging.error("Menu update FAILED.")


# =============================================================================
# TASK 2: Delete orphan "Supplies" collection
# =============================================================================
logging.info("=== TASK 2: Finding and deleting orphan 'Supplies' collection ===")

search_query = """
query {
  collections(first: 20, query: "title:Supplies") {
    edges {
      node {
        id
        title
        handle
        productsCount {
          count
        }
      }
    }
  }
}
"""

result = gql(search_query)
collections = result.get("data", {}).get("collections", {}).get("edges", [])
logging.info(f"Found {len(collections)} collection(s) matching 'Supplies':")

orphan_id = None
for edge in collections:
    node = edge["node"]
    count = node["productsCount"]["count"]
    logging.info(f"  - '{node['title']}' (handle={node['handle']}, id={node['id']}, products={count})")
    # Target: exactly "Supplies", 0 products, not a chicken-related collection
    if (node["title"].strip() == "Supplies"
            and count == 0
            and "chicken" not in node["title"].lower()
            and "chicken" not in node["handle"].lower()
            and "coop" not in node["title"].lower()
            and "coop" not in node["handle"].lower()):
        orphan_id = node["id"]
        logging.info(f"  ^^^ SELECTED as orphan to delete")

if not orphan_id:
    logging.warning("No orphan 'Supplies' collection found with 0 products — skipping deletion.")
else:
    delete_mutation = """
    mutation collectionDelete($input: CollectionDeleteInput!) {
      collectionDelete(input: $input) {
        deletedCollectionId
        userErrors {
          field
          message
        }
      }
    }
    """
    del_result = gql(delete_mutation, {"input": {"id": orphan_id}})
    del_data = del_result.get("data", {}).get("collectionDelete", {})
    user_errors = del_data.get("userErrors", [])
    if user_errors:
        logging.error(f"Collection delete errors: {user_errors}")
    else:
        deleted_id = del_data.get("deletedCollectionId")
        logging.info(f"Deleted orphan 'Supplies' collection: {deleted_id}")


# =============================================================================
# TASK 3: Check Reptiles and Heating and Lighting collections
# =============================================================================
logging.info("=== TASK 3: Checking Reptiles and Heating and Lighting collections ===")

for coll_title in ["Reptiles", "Heating and Lighting"]:
    q = f"""
    query {{
      collections(first: 5, query: "title:{coll_title}") {{
        edges {{
          node {{
            id
            title
            handle
            productsCount {{
              count
            }}
          }}
        }}
      }}
    }}
    """
    res = gql(q)
    edges = res.get("data", {}).get("collections", {}).get("edges", [])
    # Filter to exact title match
    matches = [e["node"] for e in edges if e["node"]["title"] == coll_title]
    if not matches:
        logging.info(f"  No collection titled '{coll_title}' found.")
        continue

    for node in matches:
        count = node["productsCount"]["count"]
        logging.info(f"  Collection '{node['title']}' (handle={node['handle']}, products={count})")
        if count == 0:
            logging.info(f"  -> Empty. Deleting '{node['title']}' collection ({node['id']})...")
            del_mutation = """
            mutation collectionDelete($input: CollectionDeleteInput!) {
              collectionDelete(input: $input) {
                deletedCollectionId
                userErrors { field message }
              }
            }
            """
            del_res = gql(del_mutation, {"input": {"id": node["id"]}})
            del_data = del_res.get("data", {}).get("collectionDelete", {})
            errs = del_data.get("userErrors", [])
            if errs:
                logging.error(f"  Error deleting '{node['title']}': {errs}")
            else:
                logging.info(f"  Deleted '{node['title']}' collection: {del_data.get('deletedCollectionId')}")
        else:
            logging.info(f"  -> Has {count} products — NOT deleting.")

logging.info("=== All tasks complete ===")
