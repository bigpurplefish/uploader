"""
fix_shared_subcategory_collections.py

Fixes subcategory collection menu links by:
1. Creating missing category-scoped collections (28 total)
2. Publishing each to Online Store
3. Renaming 13 existing shared collections with a category prefix
4. Updating the main menu to point each subcategory item to its correct collection

Run from the uploader directory:
    cd /Users/moosemarketer/Code/garoppos/uploader
    python scripts/fix_shared_subcategory_collections.py
"""

import json
import sys
import time
import logging
import requests

sys.path.insert(0, '/Users/moosemarketer/Code/garoppos/uploader')
from uploader_modules.config import load_config
from uploader_modules.shopify_api import (
    create_collection, search_collection, get_menu_by_handle,
    update_menu, invalidate_menu_cache, convert_menu_items_for_update
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

cfg = load_config()
store_url = cfg['SHOPIFY_STORE_URL'].strip().replace('https://', '').replace('http://', '')
access_token = cfg['SHOPIFY_ACCESS_TOKEN'].strip()
api_url = f'https://{store_url}/admin/api/2025-10/graphql.json'
headers = {'Content-Type': 'application/json', 'X-Shopify-Access-Token': access_token}

ONLINE_STORE_PUB = 'gid://shopify/Publication/286630838564'

SLEEP = 0.3  # seconds between API calls


# =============================================================================
# EXISTING COLLECTIONS TO RENAME
# Maps current collection GID -> new title
# =============================================================================
RENAMES = {
    'gid://shopify/Collection/650132947236': 'Pavers and Hardscaping Accessories',
    'gid://shopify/Collection/651581817124': 'Chickens Feed',
    'gid://shopify/Collection/651582570788': 'Horses Feed (includes hay)',
    'gid://shopify/Collection/650978754852': 'Horses Health',
    'gid://shopify/Collection/650978984228': 'Dogs Bedding',
    'gid://shopify/Collection/651581849892': 'Dogs Cleaning',
    'gid://shopify/Collection/650978787620': 'Dogs Collars',
    'gid://shopify/Collection/651581423908': 'Dogs Food',
    'gid://shopify/Collection/651581489444': 'Dogs Grooming',
    'gid://shopify/Collection/650979246372': 'Cats Harnesses',
    'gid://shopify/Collection/650978853156': 'Dogs Toys',
    'gid://shopify/Collection/650978951460': 'Dogs Treats',
    'gid://shopify/Collection/650978918692': 'Dogs Waste',
}


# =============================================================================
# NEW COLLECTIONS TO CREATE
# Each entry: (display_name, category_tag, subcategory_tag, menu_path)
# menu_path is used for menu-item matching: (dept_title, cat_title, sub_title)
# =============================================================================
NEW_COLLECTIONS = [
    # --- Accessories ---
    ('Dogs Accessories',        'Dogs',       'Accessories',       ('Pet Supplies',          'Dogs',        'Accessories')),
    ('Cats Accessories',        'Cats',       'Accessories',       ('Pet Supplies',          'Cats',        'Accessories')),
    ('Birds Accessories',       'Birds',      'Accessories',       ('Pet Supplies',          'Birds',       'Accessories')),
    ('Small Pets Accessories',  'Small Pets', 'Accessories',       ('Pet Supplies',          'Small Pets',  'Accessories')),
    ('Horses Accessories',      'Horses',     'Accessories',       ('Livestock and Farm',    'Horses',      'Accessories')),
    ('Chickens Accessories',    'Chickens',   'Accessories',       ('Livestock and Farm',    'Chickens',    'Accessories')),
    ('Goats Accessories',       'Goats',      'Accessories',       ('Livestock and Farm',    'Goats',       'Accessories')),
    ('Sheep Accessories',       'Sheep',      'Accessories',       ('Livestock and Farm',    'Sheep',       'Accessories')),
    # --- Feed ---
    ('Horses Feed',             'Horses',     'Feed',              ('Livestock and Farm',    'Horses',      'Feed')),
    ('Goats Feed',              'Goats',      'Feed',              ('Livestock and Farm',    'Goats',       'Feed')),
    ('Sheep Feed',              'Sheep',      'Feed',              ('Livestock and Farm',    'Sheep',       'Feed')),
    # --- Feed (includes hay) ---
    ('Goats Feed (includes hay)', 'Goats',   'Feed (includes hay)', ('Livestock and Farm',  'Goats',       'Feed (includes hay)')),
    # --- Health ---
    ('Birds Health',            'Birds',      'Health',            ('Pet Supplies',          'Birds',       'Health')),
    ('Goats Health',            'Goats',      'Health',            ('Livestock and Farm',    'Goats',       'Health')),
    ('Sheep Health',            'Sheep',      'Health',            ('Livestock and Farm',    'Sheep',       'Health')),
    # --- Bedding ---
    ('Cats Bedding',            'Cats',       'Bedding',           ('Pet Supplies',          'Cats',        'Bedding')),
    ('Small Pets Bedding',      'Small Pets', 'Bedding',           ('Pet Supplies',          'Small Pets',  'Bedding')),
    # --- Cleaning ---
    ('Cats Cleaning',           'Cats',       'Cleaning',          ('Pet Supplies',          'Cats',        'Cleaning')),
    # --- Collars ---
    ('Cats Collars',            'Cats',       'Collars',           ('Pet Supplies',          'Cats',        'Collars')),
    # --- Food ---
    ('Cats Food',               'Cats',       'Food',              ('Pet Supplies',          'Cats',        'Food')),
    ('Small Pets Food',         'Small Pets', 'Food',              ('Pet Supplies',          'Small Pets',  'Food')),
    # --- Grooming ---
    ('Cats Grooming',           'Cats',       'Grooming',          ('Pet Supplies',          'Cats',        'Grooming')),
    # --- Harnesses ---
    ('Dogs Harnesses',          'Dogs',       'Harnesses',         ('Pet Supplies',          'Dogs',        'Harnesses')),
    # --- Toys ---
    ('Cats Toys',               'Cats',       'Toys',              ('Pet Supplies',          'Cats',        'Toys')),
    ('Birds Toys',              'Birds',      'Toys',              ('Pet Supplies',          'Birds',       'Toys')),
    # --- Treats ---
    ('Cats Treats',             'Cats',       'Treats',            ('Pet Supplies',          'Cats',        'Treats')),
    ('Birds Treats',            'Birds',      'Treats',            ('Pet Supplies',          'Birds',       'Treats')),
    # --- Waste ---
    ('Cats Waste',              'Cats',       'Waste',             ('Pet Supplies',          'Cats',        'Waste')),
]


# =============================================================================
# MENU ITEM UPDATES
# Maps (dept_title, cat_title, sub_title) -> collection GID
# Populated during run as new collections are created and existing ones confirmed.
# Also includes the existing collections that are being kept/renamed:
# The old shared GIDs remain correct for their ONE intended path.
# =============================================================================
# Pre-seed with the existing collections that stay on their original paths
MENU_UPDATES = {
    # Existing collections kept (renamed but same GID, same path)
    ('Landscape and Construction', 'Pavers and Hardscaping', 'Accessories'):  'gid://shopify/Collection/650132947236',
    ('Livestock and Farm', 'Chickens', 'Feed'):                               'gid://shopify/Collection/651581817124',
    ('Livestock and Farm', 'Horses', 'Feed (includes hay)'):                  'gid://shopify/Collection/651582570788',
    ('Livestock and Farm', 'Horses', 'Health'):                               'gid://shopify/Collection/650978754852',
    ('Pet Supplies', 'Dogs', 'Bedding'):                                      'gid://shopify/Collection/650978984228',
    ('Pet Supplies', 'Dogs', 'Cleaning'):                                     'gid://shopify/Collection/651581849892',
    ('Pet Supplies', 'Dogs', 'Collars'):                                      'gid://shopify/Collection/650978787620',
    ('Pet Supplies', 'Dogs', 'Food'):                                         'gid://shopify/Collection/651581423908',
    ('Pet Supplies', 'Dogs', 'Grooming'):                                     'gid://shopify/Collection/651581489444',
    ('Pet Supplies', 'Cats', 'Harnesses'):                                    'gid://shopify/Collection/650979246372',
    ('Pet Supplies', 'Dogs', 'Toys'):                                         'gid://shopify/Collection/650978853156',
    ('Pet Supplies', 'Dogs', 'Treats'):                                       'gid://shopify/Collection/650978951460',
    ('Pet Supplies', 'Dogs', 'Waste'):                                        'gid://shopify/Collection/650978918692',
}


# =============================================================================
# HELPERS
# =============================================================================

def gql(query, variables=None):
    """Execute a GraphQL query/mutation and return the data dict (or None on error)."""
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if 'errors' in result:
        logging.error(f'GraphQL errors: {result["errors"]}')
        return None
    return result.get('data')


def publish_collection(collection_id):
    """Publish a collection to the Online Store publication."""
    mutation = """
    mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
      publishablePublish(id: $id, input: $input) {
        publishable {
          ... on Collection {
            id
            title
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        'id': collection_id,
        'input': [{'publicationId': ONLINE_STORE_PUB}]
    }
    data = gql(mutation, variables)
    if data is None:
        return False
    user_errors = data.get('publishablePublish', {}).get('userErrors', [])
    if user_errors:
        logging.error(f'Publish errors for {collection_id}: {user_errors}')
        return False
    return True


def rename_collection(collection_id, new_title):
    """Rename an existing collection."""
    mutation = """
    mutation collectionUpdate($input: CollectionInput!) {
      collectionUpdate(input: $input) {
        collection {
          id
          title
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {'input': {'id': collection_id, 'title': new_title}}
    data = gql(mutation, variables)
    if data is None:
        return False
    user_errors = data.get('collectionUpdate', {}).get('userErrors', [])
    if user_errors:
        logging.error(f'Rename errors for {collection_id} -> {new_title}: {user_errors}')
        return False
    actual_title = data.get('collectionUpdate', {}).get('collection', {}).get('title')
    logging.info(f'  Renamed collection {collection_id} -> "{actual_title}"')
    return True


def walk_menu_items(items, dept_title=None, cat_title=None):
    """
    Walk menu items 3 levels deep and yield (path_tuple, item_dict) for leaf items.
    path_tuple = (dept_title, cat_title, sub_title)
    """
    for dept_item in items:
        d = dept_item.get('title', '')
        for cat_item in dept_item.get('items', []):
            c = cat_item.get('title', '')
            for sub_item in cat_item.get('items', []):
                s = sub_item.get('title', '')
                yield (d, c, s), sub_item


def update_resource_id_in_items(items, path_to_gid):
    """
    Recursively walk items and update resourceId for subcategory items
    whose (dept, cat, sub) path appears in path_to_gid.
    Returns (modified_items, count_updated).
    """
    updated = 0
    result = []
    for item in items:
        item = dict(item)
        child_items = item.get('items', [])
        if child_items:
            # Check if this item's children have children (i.e., this is a dept or cat level)
            has_grandchildren = any(c.get('items') for c in child_items)
            if has_grandchildren:
                # dept level: recurse with dept context
                new_children, n = _update_recursive(child_items, item.get('title', ''), path_to_gid)
                item['items'] = new_children
                updated += n
            else:
                # cat level: children are subcategory items — but we need dept context
                # This branch shouldn't be reached from the top-level call;
                # handled in _update_recursive
                pass
        result.append(item)
    return result, updated


def _update_recursive(items, dept_title, path_to_gid):
    """Walk category items and update their subcategory children."""
    updated = 0
    result = []
    for item in items:
        item = dict(item)
        cat_title = item.get('title', '')
        sub_items = item.get('items', [])
        if sub_items:
            new_subs = []
            for sub in sub_items:
                sub = dict(sub)
                path = (dept_title, cat_title, sub.get('title', ''))
                if path in path_to_gid:
                    new_gid = path_to_gid[path]
                    old_gid = sub.get('resourceId')
                    if old_gid != new_gid:
                        logging.info(f'  Menu update: {path} -> {new_gid} (was {old_gid})')
                        sub['resourceId'] = new_gid
                        updated += 1
                    else:
                        logging.info(f'  Menu item already correct: {path}')
                new_subs.append(sub)
            item['items'] = new_subs
        result.append(item)
    return result, updated


# =============================================================================
# MAIN
# =============================================================================

def main():
    stats = {
        'created': 0,
        'published': 0,
        'renamed': 0,
        'menu_updated': 0,
        'errors': []
    }

    # -------------------------------------------------------------------------
    # STEP 1: Create all new collections
    # -------------------------------------------------------------------------
    logging.info('=' * 60)
    logging.info('STEP 1: Creating new category-scoped collections')
    logging.info('=' * 60)

    for (coll_name, cat_tag, sub_tag, menu_path) in NEW_COLLECTIONS:
        logging.info(f'Creating collection: "{coll_name}"')
        rules = [
            {'column': 'TAG', 'relation': 'EQUALS', 'condition': cat_tag},
            {'column': 'TAG', 'relation': 'EQUALS', 'condition': sub_tag},
        ]
        result = create_collection(coll_name, rules, cfg)
        time.sleep(SLEEP)

        if result and result.get('id'):
            coll_id = result['id']
            logging.info(f'  Created: {coll_id} (handle: {result.get("handle")})')
            stats['created'] += 1

            # Record for menu update
            MENU_UPDATES[menu_path] = coll_id

            # STEP 2 (inline): Publish to Online Store
            logging.info(f'  Publishing to Online Store...')
            ok = publish_collection(coll_id)
            time.sleep(SLEEP)
            if ok:
                logging.info(f'  Published OK')
                stats['published'] += 1
            else:
                msg = f'Failed to publish {coll_name} ({coll_id})'
                logging.error(f'  {msg}')
                stats['errors'].append(msg)
        else:
            msg = f'Failed to create collection: {coll_name}'
            logging.error(f'  {msg}')
            stats['errors'].append(msg)
            # Don't add to MENU_UPDATES — menu item will be skipped

    # -------------------------------------------------------------------------
    # STEP 3: Rename existing shared collections
    # -------------------------------------------------------------------------
    logging.info('=' * 60)
    logging.info('STEP 3: Renaming existing shared collections')
    logging.info('=' * 60)

    for coll_id, new_title in RENAMES.items():
        logging.info(f'Renaming {coll_id} -> "{new_title}"')
        ok = rename_collection(coll_id, new_title)
        time.sleep(SLEEP)
        if ok:
            stats['renamed'] += 1
        else:
            msg = f'Failed to rename {coll_id} -> {new_title}'
            stats['errors'].append(msg)

    # -------------------------------------------------------------------------
    # STEP 4: Update the main menu
    # -------------------------------------------------------------------------
    logging.info('=' * 60)
    logging.info('STEP 4: Updating main menu')
    logging.info('=' * 60)

    invalidate_menu_cache()
    menu = get_menu_by_handle('main-menu', cfg)
    time.sleep(SLEEP)

    if not menu:
        msg = 'Could not fetch main-menu — skipping menu update'
        logging.error(msg)
        stats['errors'].append(msg)
    else:
        logging.info(f'Fetched menu: {menu.get("id")} "{menu.get("title")}"')

        # Walk current menu to audit current state
        logging.info('Current subcategory menu item resourceIds:')
        menu_items = menu.get('items', [])
        for path, sub_item in walk_menu_items(menu_items):
            logging.info(f'  {path} -> {sub_item.get("resourceId")}')

        # Apply updates in-place
        updated_items, n_updated = update_resource_id_in_items(menu_items, MENU_UPDATES)
        stats['menu_updated'] = n_updated

        if n_updated == 0:
            logging.info('No menu items needed updating.')
        else:
            logging.info(f'Updated {n_updated} menu item(s). Saving...')
            update_items_fmt = convert_menu_items_for_update(updated_items)
            ok = update_menu(menu['id'], menu['title'], update_items_fmt, cfg)
            time.sleep(SLEEP)
            if not ok:
                msg = 'Menu update API call failed'
                logging.error(msg)
                stats['errors'].append(msg)

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    logging.info('=' * 60)
    logging.info('SUMMARY')
    logging.info('=' * 60)
    logging.info(f'Collections created:  {stats["created"]} / {len(NEW_COLLECTIONS)}')
    logging.info(f'Collections published: {stats["published"]} / {stats["created"]}')
    logging.info(f'Collections renamed:  {stats["renamed"]} / {len(RENAMES)}')
    logging.info(f'Menu items updated:   {stats["menu_updated"]}')
    if stats['errors']:
        logging.warning(f'Errors ({len(stats["errors"])}):')
        for e in stats['errors']:
            logging.warning(f'  - {e}')
    else:
        logging.info('No errors.')

    return stats


if __name__ == '__main__':
    main()
