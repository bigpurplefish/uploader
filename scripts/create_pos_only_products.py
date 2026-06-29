#!/usr/bin/env python3
"""
Bulk-create simple, single-variant products in Shopify, POS channel ONLY.

Scope (deliberately minimal — matches the request):
  - One product per row, each with a single default variant.
  - Sets ONLY: title, SKU, price, cost, barcode (UPC), inventory quantity.
  - NO images, NO taxonomy/category, NO description, NO tags, NO weight.
  - Publishes ONLY to the Point of Sale channel (NOT Online Store).

Pattern mirrors uploader_modules/product_processing.py (API 2025-10):
  productSet(synchronous) -> inventorySetQuantities -> publishablePublish.
Cost is set via the variant's inventoryItem.cost during productSet.

Usage:
  python3 scripts/create_pos_only_products.py            # dry run (read-only checks + plan)
  python3 scripts/create_pos_only_products.py --execute  # create the products
"""
import argparse
import json
import os
import sys
import time

import requests

API_VERSION = "2025-10"

# (sku, title, qty, cost, price, upc)  -- upc "" means leave barcode blank
PRODUCTS = [
    ("50975", "NDS 500 5' Mini Channel Drain",        3,  "54.54",  "77.99",  "052063605005"),
    ("50980", "NDS 400 4' Gray Channel Drain",        5,  "36.26",  "51.99",  "052063404004"),
    ("50991", "LV Cable 12/2 x 500' Black",           3,  "243.04", "349.99", ""),
    ("50984", "NDS 249 3\" & 4\" S&D Offset Drain",   2,  "7.33",   "10.99",  "052063402499"),
    ("50983", "NDS 248 Channel Coupling",             4,  "6.55",   "9.99",   "052063402482"),
    ("50978", "NDS 548 Channel Coupling",             2,  "9.80",   "13.99",  "052063505480"),
    ("50982", "NDS 247 Solid End Cap",                4,  "6.55",   "9.99",   "052063402475"),
    ("50973", "NDS Drain Box 12x12 KIT",              1,  "66.30",  "94.99",  "052063030999"),
    ("50972", "NDS 9x9 Catch Basin Kit 900C",         4,  "50.27",  "70.99",  "052063030982"),
    ("50977", "NDS 547 End Cap",                      2,  "9.40",   "12.99",  "052063505473"),
    ("50979", "NDS 546 Spigot End Outlet 2\"",        2,  "12.49",  "17.99",  "052063505466"),
    ("50974", "NDS 430 3\"/4\" Pop-Up Drain",        2,  "22.33",  "30.99",  "052063003146"),
    ("51104", "Drain Spout Adapter",                 48,  "4.84",   "6.99",   "096942301909"),
    ("31368", "Floor Strainer PVC 4\"",              25,  "4.93",   "6.99",   "0662671190659"),
    ("26290", "Wye Drain 45 Degree 4\"",             15,  "10.54",  "14.99",  "096942301053"),
]


def load_cfg():
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(here, "..", "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)
    store = cfg["SHOPIFY_STORE_URL"].strip().replace("https://", "").replace("http://", "")
    token = cfg["SHOPIFY_ACCESS_TOKEN"].strip()
    api_url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}
    return api_url, headers, store


def gql(api_url, headers, query, variables=None):
    r = requests.post(api_url, json={"query": query, "variables": variables or {}},
                      headers=headers, timeout=60)
    r.raise_for_status()
    out = r.json()
    if "errors" in out:
        raise RuntimeError(f"GraphQL errors: {json.dumps(out['errors'], indent=2)}")
    return out["data"]


def get_active_location_id(api_url, headers):
    q = """
    query { locations(first: 20) { edges { node { id name isActive shipsInventory } } } }
    """
    edges = gql(api_url, headers, q)["locations"]["edges"]
    nodes = [e["node"] for e in edges]
    active = [n for n in nodes if n.get("isActive")]
    chosen = next((n for n in active if n.get("shipsInventory")), active[0] if active else nodes[0])
    return chosen["id"], chosen.get("name"), nodes


def get_pos_publication_id(api_url, headers):
    q = """
    query { publications(first: 25) { edges { node { id name } } } }
    """
    edges = gql(api_url, headers, q)["publications"]["edges"]
    pubs = [e["node"] for e in edges]
    pos = next((p for p in pubs if "point of sale" in (p["name"] or "").lower()), None)
    return (pos["id"] if pos else None), pubs


def find_existing_sku(api_url, headers, sku):
    q = """
    query($q: String!) {
      productVariants(first: 1, query: $q) {
        edges { node { id sku product { id title } } }
      }
    }
    """
    edges = gql(api_url, headers, q, {"q": f"sku:{sku}"})["productVariants"]["edges"]
    if edges:
        n = edges[0]["node"]
        # Shopify sku: search can be loose; confirm exact match
        if (n.get("sku") or "") == sku:
            return n["product"]
    return None


PRODUCT_SET = """
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
  productSet(synchronous: $synchronous, input: $input) {
    product {
      id
      title
      handle
      variants(first: 5) {
        edges { node { id sku price inventoryItem { id unitCost { amount } } } }
      }
    }
    userErrors { field message }
  }
}
"""

INVENTORY_SET = """
mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { id }
    userErrors { field message }
  }
}
"""

PUBLISH = """
mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    publishable { availablePublicationsCount { count } }
    userErrors { field message }
  }
}
"""


def build_product_input(sku, title, cost, price, upc):
    variant = {
        "price": str(price),
        "inventoryPolicy": "DENY",
        "taxable": True,
        "optionValues": [{"optionName": "Title", "name": "Default Title"}],
        "inventoryItem": {
            "tracked": True,
            "requiresShipping": True,
            "sku": sku,
            "cost": str(cost),
        },
    }
    if upc:
        variant["barcode"] = upc
    return {
        "title": title,
        "status": "ACTIVE",
        "productOptions": [{"name": "Title", "position": 1, "values": [{"name": "Default Title"}]}],
        "variants": [variant],
    }


def create_one(api_url, headers, row, location_id, pos_pub_id):
    sku, title, qty, cost, price, upc = row
    pinput = build_product_input(sku, title, cost, price, upc)

    data = gql(api_url, headers, PRODUCT_SET, {"synchronous": True, "input": pinput})
    res = data["productSet"]
    if res["userErrors"]:
        raise RuntimeError(f"productSet userErrors: {res['userErrors']}")
    product = res["product"]
    pid = product["id"]
    vnode = product["variants"]["edges"][0]["node"]
    inv_item_id = vnode["inventoryItem"]["id"]

    # Set inventory quantity at the active location.
    inv = gql(api_url, headers, INVENTORY_SET, {"input": {
        "name": "available",
        "reason": "correction",
        "ignoreCompareQuantity": True,
        "quantities": [{"inventoryItemId": inv_item_id, "locationId": location_id, "quantity": int(qty)}],
    }})["inventorySetQuantities"]
    if inv["userErrors"]:
        raise RuntimeError(f"inventorySetQuantities userErrors: {inv['userErrors']}")

    # Publish to POS channel only.
    pub = gql(api_url, headers, PUBLISH, {
        "id": pid, "input": [{"publicationId": pos_pub_id}],
    })["publishablePublish"]
    if pub["userErrors"]:
        raise RuntimeError(f"publishablePublish userErrors: {pub['userErrors']}")

    cost_returned = (vnode.get("inventoryItem") or {}).get("unitCost") or {}
    return {
        "product_id": pid,
        "handle": product["handle"],
        "variant_id": vnode["id"],
        "price": vnode["price"],
        "cost": cost_returned.get("amount"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Actually create products (default: dry run)")
    args = ap.parse_args()

    api_url, headers, store = load_cfg()
    print(f"Store: {store}  (API {API_VERSION})")

    location_id, location_name, all_locs = get_active_location_id(api_url, headers)
    print(f"Location: {location_name}  {location_id}")
    pos_pub_id, all_pubs = get_pos_publication_id(api_url, headers)
    print(f"POS publication: {pos_pub_id}")
    if not pos_pub_id:
        print("ERROR: Could not find a 'Point of Sale' publication. Available:")
        for p in all_pubs:
            print(f"   - {p['name']}  {p['id']}")
        sys.exit(1)

    # Pre-check: skip SKUs that already exist (avoid duplicates).
    print("\nChecking for existing SKUs...")
    to_create, skipped = [], []
    for row in PRODUCTS:
        sku = row[0]
        existing = find_existing_sku(api_url, headers, sku)
        if existing:
            skipped.append((sku, existing["title"], existing["id"]))
            print(f"  SKIP {sku}: already exists -> {existing['title']} ({existing['id']})")
        else:
            to_create.append(row)

    print(f"\nPlan: create {len(to_create)} products, skip {len(skipped)} existing.")
    for sku, title, qty, cost, price, upc in to_create:
        print(f"  + {sku:<6} {title:<38} qty={qty:<3} cost={cost:<7} price={price:<7} upc={upc or '(blank)'}")

    if not args.execute:
        print("\nDRY RUN — no changes made. Re-run with --execute to create.")
        return

    print("\n=== EXECUTING ===")
    created, failed = [], []
    for row in to_create:
        sku, title = row[0], row[1]
        try:
            info = create_one(api_url, headers, row, location_id, pos_pub_id)
            created.append((sku, title, info))
            print(f"  ✅ {sku}  {title}  -> {info['product_id']} (cost={info['cost']}, price={info['price']})")
        except Exception as e:
            failed.append((sku, title, str(e)))
            print(f"  ❌ {sku}  {title}  -> {e}")
        time.sleep(0.5)  # gentle rate limiting

    print(f"\nDone. Created {len(created)}, skipped {len(skipped)}, failed {len(failed)}.")
    if failed:
        print("FAILURES:")
        for sku, title, err in failed:
            print(f"  - {sku} {title}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
