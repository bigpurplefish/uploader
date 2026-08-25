#!/usr/bin/env python3
"""Convert the product containing variant SKU 24725 into a single-variant
'SRW Landscape Staples' product.

Phases:
 1. Investigate — find product by SKU, print its current state.
 2. Plan — print before/after diff.
 3. Execute — call productSet with existing product ID to fully replace
    title/description/options/variants with the new single-variant config.
 4. Follow-up — verify inventoryItem.unitCost, restore inventory at each
    location if productSet altered it, verify publications.

Dry-run by default; pass --execute to apply.
"""

import argparse
import json
import logging
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_VERSION = "2025-10"

PUB_ONLINE_STORE = "gid://shopify/Publication/286630838564"
PUB_POS = "gid://shopify/Publication/286630871332"

TARGET_SKU = "24725"

NEW_TITLE = "SRW Landscape Staples"
NEW_PRICE = "60.00"
NEW_COST = "39.95"
SIZE_VALUE = '6"x1"x6"'
UOS_VALUE = "1000 Per Box"

NEW_DESCRIPTION_HTML = """<p>Lock landscape fabric, weed barrier, and erosion control blankets into place with SRW Landscape Staples. These 6&quot; heavy-gauge steel staples drive in fast with a hammer and hold tight against wind, water, and foot traffic so your base layers stay exactly where you put them.</p>

<p>Reach for them on every hardscape and planting job: pin down geotextile under pavers and retaining walls, anchor silt fence on grading sites, stake sod and drip irrigation lines, and secure erosion blankets on slopes until vegetation takes hold. The 1&quot; crown grips fabric without tearing, and the full 6&quot; leg length bites into compacted soil and crushed stone base.</p>

<p>Sold by the box of 1000 &mdash; enough to cover a full day of landscape fabric work or stock the truck for the season. Keep a box on hand and stop chasing loose fabric across the site.</p>"""

PRODUCT_QUERY = """
query findProduct($query: String!) {
  productVariants(first: 10, query: $query) {
    edges {
      node {
        id
        sku
        product { id }
      }
    }
  }
}
"""

PRODUCT_DETAIL_QUERY = """
query productDetail($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    descriptionHtml
    productType
    vendor
    tags
    status
    category { id fullName }
    options { id name position values }
    variants(first: 100) {
      edges {
        node {
          id
          sku
          title
          price
          inventoryPolicy
          selectedOptions { name value }
          inventoryItem {
            id
            tracked
            unitCost { amount }
            measurement { weight { value unit } }
            inventoryLevels(first: 20) {
              edges {
                node {
                  location { id name }
                  quantities(names: ["available"]) { name quantity }
                }
              }
            }
          }
        }
      }
    }
    media(first: 50) { edges { node { id alt mediaContentType } } }
    metafields(first: 50) {
      edges {
        node { id namespace key type value }
      }
    }
    resourcePublications(first: 20) {
      edges { node { publication { id name } isPublished } }
    }
  }
}
"""

PRODUCT_SET = """
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
  productSet(synchronous: $synchronous, input: $input) {
    product {
      id
      handle
      title
      descriptionHtml
      options { id name position values }
      variants(first: 10) {
        edges {
          node {
            id
            sku
            title
            price
            selectedOptions { name value }
            inventoryItem {
              id
              unitCost { amount }
              measurement { weight { value unit } }
            }
          }
        }
      }
    }
    userErrors { field message }
  }
}
"""

INVENTORY_ITEM_UPDATE = """
mutation inventoryItemUpdate($id: ID!, $input: InventoryItemUpdateInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem { id unitCost { amount } }
    userErrors { field message }
  }
}
"""

INVENTORY_SET_QUANTITIES = """
mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { id }
    userErrors { field message }
  }
}
"""


def api_url(cfg):
    s = cfg["SHOPIFY_STORE_URL"].replace("https://", "").replace("http://", "").strip("/")
    return f"https://{s}/admin/api/{API_VERSION}/graphql.json"


def headers(cfg):
    return {"Content-Type": "application/json", "X-Shopify-Access-Token": cfg["SHOPIFY_ACCESS_TOKEN"]}


def gql(cfg, q, v=None):
    r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}}, headers=headers(cfg), timeout=120)
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        raise RuntimeError(f"GraphQL errors: {d['errors']}")
    return d["data"]


def find_product_by_sku(cfg, sku):
    data = gql(cfg, PRODUCT_QUERY, {"query": f"sku:{sku}"})
    edges = data["productVariants"]["edges"]
    if not edges:
        return None, None
    matches = [e for e in edges if e["node"]["sku"] == sku]
    if not matches:
        return None, None
    node = matches[0]["node"]
    return node["product"]["id"], node["id"]


def fetch_product(cfg, product_id):
    return gql(cfg, PRODUCT_DETAIL_QUERY, {"id": product_id})["product"]


def collect_inventory_by_location(variant):
    """Return list of {locationId, quantity} for 'available' quantities."""
    out = []
    item = variant.get("inventoryItem") or {}
    levels = (item.get("inventoryLevels") or {}).get("edges") or []
    for e in levels:
        node = e["node"]
        loc_id = node["location"]["id"]
        qty = 0
        for q in node.get("quantities") or []:
            if q.get("name") == "available":
                qty = q.get("quantity") or 0
                break
        out.append({"locationId": loc_id, "locationName": node["location"]["name"], "quantity": qty})
    return out


def summarize_product(prod):
    print()
    print("=" * 70)
    print("CURRENT PRODUCT STATE")
    print("=" * 70)
    print(f"ID:           {prod['id']}")
    print(f"Handle:       {prod['handle']}")
    print(f"Title:        {prod['title']}")
    print(f"Vendor:       {prod.get('vendor')}")
    print(f"Type:         {prod.get('productType')}")
    print(f"Status:       {prod.get('status')}")
    print(f"Tags:         {prod.get('tags')}")
    cat = prod.get("category")
    print(f"Category:     {cat.get('fullName') if cat else None}  id={cat.get('id') if cat else None}")
    desc = prod.get("descriptionHtml") or ""
    print(f"Description:  ({len(desc)} chars) {desc[:200]!r}{'...' if len(desc) > 200 else ''}")
    print()
    print("Options:")
    for o in prod.get("options") or []:
        print(f"  - [{o['position']}] {o['name']}  values={o['values']}")
    print()
    variants = [e["node"] for e in prod["variants"]["edges"]]
    print(f"Variants ({len(variants)}):")
    for v in variants:
        opts = " / ".join(f"{o['name']}={o['value']}" for o in v["selectedOptions"])
        item = v.get("inventoryItem") or {}
        cost = (item.get("unitCost") or {}).get("amount") if item else None
        meas = item.get("measurement") or {}
        weight = (meas.get("weight") or {})
        inv = collect_inventory_by_location(v)
        total = sum(i["quantity"] for i in inv)
        locs = ", ".join(f"{i['locationName']}={i['quantity']}" for i in inv)
        print(f"  - SKU={v['sku']:<10} ${v['price']:<8}  cost={cost}  wt={weight.get('value')}{weight.get('unit')}  [{opts}]")
        print(f"      inv_total={total}  byLocation={locs}")
    print()
    print(f"Media count: {len(prod.get('media', {}).get('edges', []))}")
    print(f"Metafields count: {len(prod.get('metafields', {}).get('edges', []))}")
    pubs = [e["node"] for e in (prod.get("resourcePublications") or {}).get("edges", [])]
    print(f"Publications ({len(pubs)}):")
    for p in pubs:
        print(f"  - {p['publication']['name']:<20} id={p['publication']['id']} published={p['isPublished']}")


def build_new_product_input(existing_prod, target_variant):
    """Build the full ProductSetInput that replaces state."""
    # Preserve weight if available (optional but useful)
    item = target_variant.get("inventoryItem") or {}
    meas = item.get("measurement") or {}
    weight = meas.get("weight") or {}

    variant_input = {
        "optionValues": [
            {"optionName": "Size", "name": SIZE_VALUE},
            {"optionName": "Unit of Sale", "name": UOS_VALUE},
        ],
        "price": NEW_PRICE,
        "sku": TARGET_SKU,
        "inventoryPolicy": target_variant.get("inventoryPolicy", "DENY"),
        "inventoryItem": {
            "tracked": True,
            "sku": TARGET_SKU,
            "cost": NEW_COST,
        },
    }

    if weight.get("value") is not None and weight.get("unit"):
        variant_input["inventoryItem"]["measurement"] = {
            "weight": {"value": float(weight["value"]), "unit": weight["unit"]}
        }

    product_input = {
        "id": existing_prod["id"],  # update in place
        "title": NEW_TITLE,
        "descriptionHtml": NEW_DESCRIPTION_HTML,
        "productOptions": [
            {"name": "Size", "position": 1, "values": [{"name": SIZE_VALUE}]},
            {"name": "Unit of Sale", "position": 2, "values": [{"name": UOS_VALUE}]},
        ],
        "variants": [variant_input],
    }
    return product_input


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Apply changes. Otherwise dry-run.")
    args = ap.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Update SKU {TARGET_SKU} -> {NEW_TITLE}  mode={mode}")

    # Phase 1: Find product
    log.info(f"Looking up product by variant SKU {TARGET_SKU}...")
    product_id, variant_id = find_product_by_sku(cfg, TARGET_SKU)
    if not product_id:
        log.error(f"No product variant found with SKU={TARGET_SKU}")
        return 1
    log.info(f"  Product:  {product_id}")
    log.info(f"  Variant:  {variant_id}")

    prod = fetch_product(cfg, product_id)
    summarize_product(prod)

    # Identify target variant full record
    variants = [e["node"] for e in prod["variants"]["edges"]]
    target = next((v for v in variants if v["sku"] == TARGET_SKU), None)
    if not target:
        log.error(f"Target variant SKU={TARGET_SKU} not found in product variants list.")
        return 1
    target_inventory = collect_inventory_by_location(target)
    deleted_skus = [v["sku"] for v in variants if v["sku"] != TARGET_SKU]

    # Phase 2: Plan
    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"Title:        {prod['title']!r} -> {NEW_TITLE!r}")
    print(f"Handle:       {prod['handle']}  (preserve)")
    print(f"Variants:     {len(variants)} -> 1  (keep SKU {TARGET_SKU})")
    if deleted_skus:
        print(f"  Deleting variant SKUs: {deleted_skus}")
    print(f"Options:      {[o['name'] for o in prod.get('options') or []]} -> ['Size', 'Unit of Sale']")
    print(f"  Size        -> [{SIZE_VALUE!r}]")
    print(f"  UoS         -> [{UOS_VALUE!r}]")
    print(f"Price:        {target.get('price')} -> {NEW_PRICE}")
    cur_cost = ((target.get('inventoryItem') or {}).get('unitCost') or {}).get('amount')
    print(f"Cost:         {cur_cost} -> {NEW_COST}")
    print(f"Inventory:    preserve on SKU {TARGET_SKU}:")
    for i in target_inventory:
        print(f"    {i['locationName']:<30} qty={i['quantity']}  loc={i['locationId']}")
    print(f"Description:  REWRITTEN ({len(NEW_DESCRIPTION_HTML)} chars)")
    print(f"  First 200:  {NEW_DESCRIPTION_HTML[:200]!r}...")
    print(f"Media:        {len(prod.get('media', {}).get('edges', []))} entries  (untouched by productSet)")
    print(f"Metafields:   {len(prod.get('metafields', {}).get('edges', []))} entries  (untouched — no metafields in productSet input)")
    pubs = [e["node"] for e in (prod.get("resourcePublications") or {}).get("edges", [])]
    pub_ids = [p["publication"]["id"] for p in pubs if p["isPublished"]]
    print(f"Publications: {pub_ids}  (preserved)")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

    # Phase 3: Execute productSet
    print("=" * 70)
    print("EXECUTING")
    print("=" * 70)

    product_input = build_new_product_input(prod, target)
    log.info("Calling productSet (synchronous=true) to update product in place...")
    data = gql(cfg, PRODUCT_SET, {"synchronous": True, "input": product_input})
    ue = data["productSet"]["userErrors"]
    if ue:
        log.error(f"productSet userErrors: {ue}")
        return 1
    result = data["productSet"]["product"]
    log.info(f"  OK  id={result['id']} handle={result['handle']} title={result['title']!r}")

    new_variants = [e["node"] for e in result["variants"]["edges"]]
    if len(new_variants) != 1:
        log.error(f"Expected 1 variant, got {len(new_variants)}")
        # proceed to inspection regardless
    surviving = next((v for v in new_variants if v["sku"] == TARGET_SKU), None)
    if not surviving:
        log.error(f"Surviving variant with SKU {TARGET_SKU} not found after productSet!")
        return 1

    log.info(f"  Surviving variant: id={surviving['id']} sku={surviving['sku']} price={surviving['price']}")
    for o in surviving["selectedOptions"]:
        log.info(f"    {o['name']}={o['value']}")
    inv_item = surviving["inventoryItem"]
    reported_cost = (inv_item.get("unitCost") or {}).get("amount")
    log.info(f"  inventoryItem id={inv_item['id']}  unitCost={reported_cost}")

    # Phase 4a: ensure unitCost is correct (productSet usually accepts it, but double-check)
    if str(reported_cost) != str(NEW_COST):
        log.info(f"Cost mismatch (got {reported_cost}, want {NEW_COST}) — sending inventoryItemUpdate...")
        iiu = gql(cfg, INVENTORY_ITEM_UPDATE, {
            "id": inv_item["id"],
            "input": {"cost": NEW_COST, "tracked": True},
        })
        ue2 = iiu["inventoryItemUpdate"]["userErrors"]
        if ue2:
            log.error(f"inventoryItemUpdate errors: {ue2}")
        else:
            log.info(f"  OK cost updated -> {iiu['inventoryItemUpdate']['inventoryItem']['unitCost']['amount']}")

    # Phase 4b: verify inventory per location, restore if needed
    log.info("Re-fetching product to verify inventory quantities...")
    time.sleep(1)
    post = fetch_product(cfg, result["id"])
    post_variants = [e["node"] for e in post["variants"]["edges"]]
    post_target = next((v for v in post_variants if v["sku"] == TARGET_SKU), None)
    post_inventory = collect_inventory_by_location(post_target) if post_target else []

    # Map by locationId
    pre_by_loc = {i["locationId"]: i["quantity"] for i in target_inventory}
    post_by_loc = {i["locationId"]: i["quantity"] for i in post_inventory}

    to_restore = []
    for loc_id, pre_q in pre_by_loc.items():
        post_q = post_by_loc.get(loc_id, 0)
        if post_q != pre_q:
            to_restore.append({
                "inventoryItemId": post_target["inventoryItem"]["id"],
                "locationId": loc_id,
                "quantity": pre_q,
            })
            log.info(f"  Location {loc_id} qty drift: pre={pre_q} post={post_q} -> will restore")
        else:
            log.info(f"  Location {loc_id} qty preserved ({pre_q})")

    if to_restore:
        log.info(f"Restoring {len(to_restore)} inventory quantities via inventorySetQuantities...")
        inv_input = {
            "name": "available",
            "reason": "correction",
            "ignoreCompareQuantity": True,
            "quantities": to_restore,
        }
        ir = gql(cfg, INVENTORY_SET_QUANTITIES, {"input": inv_input})
        ue3 = ir["inventorySetQuantities"]["userErrors"]
        if ue3:
            log.error(f"inventorySetQuantities errors: {ue3}")
        else:
            log.info("  OK inventory restored")

    # Phase 4c: final verification snapshot
    log.info("Final verification fetch...")
    time.sleep(1)
    final = fetch_product(cfg, result["id"])
    summarize_product(final)

    print()
    print("=" * 70)
    print("COMPLETED")
    print("=" * 70)
    print(f"Product URL path: /products/{final['handle']}")
    print(f"Admin URL:        https://{cfg['SHOPIFY_STORE_URL'].replace('https://','').replace('http://','').strip('/')}/admin/products/{final['id'].rsplit('/',1)[-1]}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
