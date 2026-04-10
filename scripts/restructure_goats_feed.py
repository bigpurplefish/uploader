"""
Restructure Goats subcategories in Shopify.

Changes:
1. Fetch all products from "Goats Feed" and "Goats Feed (includes hay)" collections
2. Classify each product as TREAT or FEED/HAY based on title keywords
3. Create new "Goats Treats" collection (only if treats found)
4. Retag all products (remove old tags, add new ones)
5. Rename "Goats Feed" collection → "Goats Feed and Hay"
6. Delete "Goats Feed (includes hay)" collection
7. Update main menu: rename Feed → Feed and Hay, remove Feed (includes hay), add Treats

Usage:
    cd /Users/moosemarketer/Code/garoppos/uploader
    python scripts/restructure_goats_feed.py
"""

import json
import sys
import time
import logging
import requests

sys.path.insert(0, '/Users/moosemarketer/Code/garoppos/uploader')
from uploader_modules.config import load_config
from uploader_modules.shopify_api import (
    create_collection, update_shopify_product, get_menu_by_handle,
    update_menu, invalidate_menu_cache, convert_menu_items_for_update,
    build_menu_item_for_collection
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

cfg = load_config()
store_url = cfg['SHOPIFY_STORE_URL'].strip().replace('https://', '').replace('http://', '')
access_token = cfg['SHOPIFY_ACCESS_TOKEN'].strip()
api_url = f'https://{store_url}/admin/api/2025-10/graphql.json'
headers = {'Content-Type': 'application/json', 'X-Shopify-Access-Token': access_token}
ONLINE_STORE_PUB = 'gid://shopify/Publication/286630838564'

GOATS_FEED_GID = 'gid://shopify/Collection/651861917988'
GOATS_FEED_HAY_GID = 'gid://shopify/Collection/651862016292'

# ─── Treat keywords (case-insensitive) ────────────────────────────────────────

TREAT_KEYWORDS = [
    'treat', 'treats',
    'nibble', 'nibbles',
    'muffin', 'muffins',
    'cookie', 'cookies',
    'snack', 'snacks', 'snax',
    'bites', 'bite-sized', 'bits',
    'rounders',
]

# peppermint is a treat UNLESS the title also contains 'lick' or 'block'
PEPPERMINT_KEYWORD = 'peppermint'
PEPPERMINT_EXCLUSIONS = ['lick', 'block']


def is_treat(title: str) -> bool:
    title_lower = title.lower()
    for kw in TREAT_KEYWORDS:
        if kw in title_lower:
            return True
    if PEPPERMINT_KEYWORD in title_lower:
        if not any(excl in title_lower for excl in PEPPERMINT_EXCLUSIONS):
            return True
    return False


# ─── GraphQL helpers ──────────────────────────────────────────────────────────

def gql(query: str, variables: dict = None) -> dict:
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    resp = requests.post(api_url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    if 'errors' in result:
        raise RuntimeError(f"GraphQL errors: {result['errors']}")
    return result


def fetch_collection_products(collection_gid: str) -> list:
    """Paginate all products in a collection. Returns list of product dicts."""
    query = """
    query collectionProducts($id: ID!, $cursor: String) {
      collection(id: $id) {
        title
        products(first: 50, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id
              title
              tags
              vendor
            }
          }
        }
      }
    }
    """
    products = []
    cursor = None
    page = 0
    while True:
        page += 1
        result = gql(query, {'id': collection_gid, 'cursor': cursor})
        coll = result['data']['collection']
        edges = coll['products']['edges']
        page_info = coll['products']['pageInfo']
        for edge in edges:
            products.append(edge['node'])
        logger.info(f"  Page {page}: fetched {len(edges)} products (total so far: {len(products)})")
        if not page_info['hasNextPage']:
            break
        cursor = page_info['endCursor']
        time.sleep(0.2)
    logger.info(f"  Collection '{coll['title']}': {len(products)} total products")
    return products


# ─── Phase 1: Collect all products ────────────────────────────────────────────

def phase1_collect():
    logger.info("=" * 60)
    logger.info("PHASE 1: Collecting products from both collections")
    logger.info("=" * 60)

    logger.info(f"Fetching Goats Feed ({GOATS_FEED_GID})...")
    feed_products = fetch_collection_products(GOATS_FEED_GID)

    logger.info(f"Fetching Goats Feed (includes hay) ({GOATS_FEED_HAY_GID})...")
    hay_products = fetch_collection_products(GOATS_FEED_HAY_GID)

    # Merge, deduplicate by product ID
    all_by_id = {}
    for p in feed_products + hay_products:
        all_by_id[p['id']] = p

    all_products = list(all_by_id.values())
    logger.info(f"Total unique products: {len(all_products)} (feed: {len(feed_products)}, hay: {len(hay_products)})")
    return all_products


# ─── Phase 2: Classify ────────────────────────────────────────────────────────

def phase2_classify(products: list) -> dict:
    """Returns {product_id: 'TREAT' | 'FEED/HAY'}"""
    logger.info("=" * 60)
    logger.info("PHASE 2: Classifying products")
    logger.info("=" * 60)

    classifications = {}
    treats = []
    feed_hay = []

    for p in products:
        label = 'TREAT' if is_treat(p['title']) else 'FEED/HAY'
        classifications[p['id']] = label
        if label == 'TREAT':
            treats.append(p['title'])
        else:
            feed_hay.append(p['title'])

    logger.info(f"\nTREAT products ({len(treats)}):")
    for t in sorted(treats):
        logger.info(f"  [TREAT]    {t}")
    logger.info(f"\nFEED/HAY products ({len(feed_hay)}):")
    for f in sorted(feed_hay):
        logger.info(f"  [FEED/HAY] {f}")
    logger.info(f"\nSummary: {len(treats)} treats, {len(feed_hay)} feed/hay")

    return classifications


# ─── Phase 3: Create "Goats Treats" collection ────────────────────────────────

def phase3_create_treats_collection() -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 3: Creating 'Goats Treats' collection")
    logger.info("=" * 60)

    rules = [
        {'column': 'TAG', 'relation': 'EQUALS', 'condition': 'Goats'},
        {'column': 'TAG', 'relation': 'EQUALS', 'condition': 'Treats'},
    ]
    result = create_collection(
        'Goats Treats',
        rules,
        cfg,
        description='Shop goat treats, cookies, and flavored snacks.'
    )
    if not result:
        raise RuntimeError("Failed to create 'Goats Treats' collection")

    collection_id = result['id']
    collection_handle = result['handle']
    logger.info(f"Created collection: {collection_id} (handle: {collection_handle})")

    # Publish to Online Store
    publish_mutation = """
    mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
      publishablePublish(id: $id, input: $input) {
        publishable { ... on Collection { id title } }
        userErrors { field message }
      }
    }
    """
    pub_result = gql(publish_mutation, {
        'id': collection_id,
        'input': [{'publicationId': ONLINE_STORE_PUB}]
    })
    pub_errors = pub_result['data']['publishablePublish']['userErrors']
    if pub_errors:
        logger.warning(f"Publish userErrors: {pub_errors}")
    else:
        logger.info(f"Published '{collection_id}' to Online Store")

    return {'id': collection_id, 'handle': collection_handle}


# ─── Phase 4: Retag all products ─────────────────────────────────────────────

def phase4_retag(products: list, classifications: dict):
    logger.info("=" * 60)
    logger.info("PHASE 4: Retagging all products")
    logger.info("=" * 60)

    REMOVE_TAGS = {'Feed', 'Feed (includes hay)'}

    success_count = 0
    error_count = 0

    for i, p in enumerate(products):
        product_id = p['id']
        old_tags = p['tags']  # list of strings
        classification = classifications[product_id]

        # Compute new tag set
        new_tags = [t for t in old_tags if t not in REMOVE_TAGS]
        if classification == 'TREAT':
            if 'Treats' not in new_tags:
                new_tags.append('Treats')
        else:  # FEED/HAY
            if 'Feed and Hay' not in new_tags:
                new_tags.append('Feed and Hay')

        old_tags_str = ', '.join(sorted(old_tags))
        new_tags_str = ', '.join(sorted(new_tags))
        logger.info(f"[{i+1}/{len(products)}] {p['title']}")
        logger.info(f"  [{classification}] OLD tags: {old_tags_str}")
        logger.info(f"  [{classification}] NEW tags: {new_tags_str}")

        update_result = update_shopify_product(product_id, {'tags': new_tags}, cfg)
        if update_result:
            success_count += 1
            logger.info(f"  -> Updated OK")
        else:
            error_count += 1
            logger.error(f"  -> FAILED to update {p['title']} ({product_id})")

        time.sleep(0.3)

    logger.info(f"\nRetag complete: {success_count} OK, {error_count} errors")
    return error_count == 0


# ─── Phase 5: Rename "Goats Feed" → "Goats Feed and Hay" ─────────────────────

def phase5_rename_collection():
    logger.info("=" * 60)
    logger.info("PHASE 5: Renaming 'Goats Feed' → 'Goats Feed and Hay'")
    logger.info("=" * 60)

    mutation = """
    mutation collectionUpdate($input: CollectionInput!) {
      collectionUpdate(input: $input) {
        collection {
          id
          title
          handle
          productsCount { count }
        }
        userErrors { field message }
      }
    }
    """
    variables = {
        "input": {
            "id": GOATS_FEED_GID,
            "title": "Goats Feed and Hay",
            "ruleSet": {
                "appliedDisjunctively": False,
                "rules": [
                    {"column": "TAG", "relation": "EQUALS", "condition": "Goats"},
                    {"column": "TAG", "relation": "EQUALS", "condition": "Feed and Hay"}
                ]
            }
        }
    }

    result = gql(mutation, variables)
    user_errors = result['data']['collectionUpdate']['userErrors']
    if user_errors:
        raise RuntimeError(f"collectionUpdate userErrors: {user_errors}")

    coll = result['data']['collectionUpdate']['collection']
    logger.info(f"Renamed collection: {coll['title']} (handle: {coll['handle']}, {coll['productsCount']['count']} products)")
    return coll


# ─── Phase 6: Delete "Goats Feed (includes hay)" collection ──────────────────

def phase6_delete_old_collection():
    logger.info("=" * 60)
    logger.info("PHASE 6: Deleting 'Goats Feed (includes hay)' collection")
    logger.info("=" * 60)

    mutation = """
    mutation {
      collectionDelete(input: {id: "gid://shopify/Collection/651862016292"}) {
        deletedCollectionId
        userErrors { field message }
      }
    }
    """
    result = gql(mutation)
    user_errors = result['data']['collectionDelete']['userErrors']
    if user_errors:
        raise RuntimeError(f"collectionDelete userErrors: {user_errors}")

    deleted_id = result['data']['collectionDelete']['deletedCollectionId']
    logger.info(f"Deleted collection: {deleted_id}")
    return deleted_id


# ─── Phase 7: Update main menu ────────────────────────────────────────────────

def phase7_update_menu(treats_collection: dict):
    logger.info("=" * 60)
    logger.info("PHASE 7: Updating main menu")
    logger.info("=" * 60)

    invalidate_menu_cache()
    menu = get_menu_by_handle('main-menu', cfg)
    if not menu:
        raise RuntimeError("Could not fetch main-menu")

    menu_id = menu['id']
    menu_title = menu['title']
    top_items = menu['items']

    logger.info(f"Menu: {menu_title} ({menu_id})")

    # Find "Livestock and Farm" → "Goats"
    livestock_item = None
    for item in top_items:
        if 'livestock' in item['title'].lower() or 'farm' in item['title'].lower():
            livestock_item = item
            break
    if not livestock_item:
        for item in top_items:
            logger.info(f"  Top-level item: {item['title']}")
        raise RuntimeError("Could not find 'Livestock and Farm' in top-level menu items")

    logger.info(f"Found top-level item: '{livestock_item['title']}'")

    goats_item = None
    for item in livestock_item.get('items', []):
        if 'goats' in item['title'].lower():
            goats_item = item
            break
    if not goats_item:
        for item in livestock_item.get('items', []):
            logger.info(f"  Livestock sub-item: {item['title']}")
        raise RuntimeError("Could not find 'Goats' under Livestock and Farm")

    logger.info(f"Found Goats item: '{goats_item['title']}'")

    # Inspect Goats sub-items
    goats_subitems = goats_item.get('items', [])
    logger.info(f"Current Goats sub-items ({len(goats_subitems)}):")
    for sub in goats_subitems:
        logger.info(f"  - {sub['title']} (type={sub.get('type')}, resourceId={sub.get('resourceId')}, url={sub.get('url')})")

    # Build new goats sub-items:
    # 1. Rename "Feed" → "Feed and Hay" (keep same id/resourceId)
    # 2. Remove "Feed (includes hay)"
    # 3. Add "Treats" after Feed and Hay (only if treats_collection is not None)
    # 4. Keep all others

    new_goats_subitems = []
    treats_inserted = False

    for sub in goats_subitems:
        title_lower = sub['title'].lower()

        if title_lower == 'feed (includes hay)':
            logger.info(f"  Removing: '{sub['title']}'")
            continue  # skip / delete

        elif title_lower == 'feed':
            # Rename to "Feed and Hay"
            updated = dict(sub)
            updated['title'] = 'Feed and Hay'
            new_goats_subitems.append(updated)
            logger.info(f"  Renamed: '{sub['title']}' → 'Feed and Hay'")

            # Insert Treats right after Feed and Hay (only if treats exist)
            if treats_collection is not None:
                treats_item = build_menu_item_for_collection(
                    'Treats',
                    treats_collection['handle'],
                    treats_collection['id']
                )
                new_goats_subitems.append(treats_item)
                treats_inserted = True
                logger.info(f"  Inserted: 'Treats' (collection: {treats_collection['id']})")

        else:
            new_goats_subitems.append(sub)
            logger.info(f"  Keeping: '{sub['title']}'")

    if treats_collection is not None and not treats_inserted:
        # Feed item wasn't found by exact match — try broader
        logger.warning("'Feed' item not found by exact match. Appending Treats at start.")
        treats_item = build_menu_item_for_collection(
            'Treats',
            treats_collection['handle'],
            treats_collection['id']
        )
        new_goats_subitems.insert(0, treats_item)

    logger.info(f"\nNew Goats sub-items ({len(new_goats_subitems)}):")
    for sub in new_goats_subitems:
        logger.info(f"  - {sub['title']}")

    # Rebuild the full menu tree with the updated Goats subitems
    def rebuild_items(items, target_goats_title, new_subitems):
        """Recursively rebuild menu items, replacing goats subitems."""
        rebuilt = []
        for item in items:
            if item['title'].lower() == target_goats_title.lower():
                updated = dict(item)
                updated['items'] = new_subitems
                rebuilt.append(updated)
            elif item.get('items'):
                updated = dict(item)
                updated['items'] = rebuild_items(item['items'], target_goats_title, new_subitems)
                rebuilt.append(updated)
            else:
                rebuilt.append(item)
        return rebuilt

    updated_top_items = rebuild_items(top_items, goats_item['title'], new_goats_subitems)

    # Convert for update
    converted = convert_menu_items_for_update(updated_top_items)

    # Save
    ok = update_menu(menu_id, menu_title, converted, cfg)
    if not ok:
        raise RuntimeError("update_menu returned False — check logs above")

    logger.info("Menu updated successfully")

    # Verify by re-fetching
    invalidate_menu_cache()
    menu_after = get_menu_by_handle('main-menu', cfg)
    if menu_after:
        for top in menu_after['items']:
            for sub in top.get('items', []):
                if 'goats' in sub['title'].lower():
                    logger.info(f"\nVerification — Goats sub-items in updated menu:")
                    for s in sub.get('items', []):
                        logger.info(f"  - {s['title']}")
                    break

    return ok


# ─── Report ───────────────────────────────────────────────────────────────────

def report(products, classifications, treats_collection, renamed_coll):
    logger.info("=" * 60)
    logger.info("FINAL REPORT")
    logger.info("=" * 60)

    treat_count = sum(1 for v in classifications.values() if v == 'TREAT')
    feed_hay_count = sum(1 for v in classifications.values() if v == 'FEED/HAY')

    logger.info(f"Treats retagged:                    {treat_count}")
    logger.info(f"Feed/Hay retagged:                  {feed_hay_count}")
    logger.info(f"'Goats Feed and Hay' collection id: {GOATS_FEED_GID}")
    logger.info(f"  Products in renamed collection:   {renamed_coll.get('productsCount', {}).get('count', '?')}")

    if treats_collection:
        logger.info(f"'Goats Treats' collection id:       {treats_collection['id']}")
        logger.info(f"'Goats Treats' collection handle:   {treats_collection['handle']}")
    else:
        logger.info("No treats found — 'Goats Treats' collection was NOT created")

    logger.info("(Note: collection product counts reflect tag changes — may take Shopify a moment to sync)")

    # Show final Goats menu state
    invalidate_menu_cache()
    menu = get_menu_by_handle('main-menu', cfg)
    if menu:
        for top in menu['items']:
            for sub in top.get('items', []):
                if 'goats' in sub['title'].lower():
                    logger.info(f"\nGoats subcategories in main menu (in order):")
                    for s in sub.get('items', []):
                        logger.info(f"  - {s['title']}  (type={s.get('type')}, resourceId={s.get('resourceId')})")
                    break


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("Starting Goats feed restructure...")
    logger.info(f"Store: {store_url}")

    # Phase 1: Collect
    products = phase1_collect()

    # Phase 2: Classify
    classifications = phase2_classify(products)

    treat_count = sum(1 for v in classifications.values() if v == 'TREAT')

    # Phase 3: Create Treats collection only if treats exist
    treats_collection = None
    if treat_count > 0:
        treats_collection = phase3_create_treats_collection()
    else:
        logger.info("=" * 60)
        logger.info("PHASE 3: SKIPPED — no treat products found")
        logger.info("=" * 60)

    # Phase 4: Retag products
    phase4_retag(products, classifications)

    # Phase 5: Rename collection
    renamed_coll = phase5_rename_collection()

    # Phase 6: Delete old collection
    phase6_delete_old_collection()

    # Phase 7: Update menu
    phase7_update_menu(treats_collection)

    # Final report
    report(products, classifications, treats_collection, renamed_coll)

    logger.info("\nDone.")


if __name__ == '__main__':
    main()
