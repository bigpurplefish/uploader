#!/usr/bin/env python3
"""
Reshape River Rock Stone (gid://shopify/Product/10368017137956):
  - Rename 4 existing variants' SKUs to append -01 (skip 24630)
  - Flip inventoryPolicy CONTINUE on all 5 existing variants
  - Add 4 new "50 LB Bag" variants (SKU -02, $6, cost null, 50 lb, CONTINUE)
  - Strip #Ton hashtag from 5 existing media alt tags (single-hashtag = match
    any Unit of Sale via theme's positional filter)
  - Update SEO + descriptionHtml

Structure: Size x Unit of Sale (2 options). UoS values auto-extend to include
50 LB Bag when the first bag variant is created. No productSet, no inventory
destruction.

Usage:
  python reshape_river_rock_stone.py            # dry run
  python reshape_river_rock_stone.py --execute  # execute
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("/Users/moosemarketer/Code/garoppos/uploader/config.json")
PRODUCT_GID = "gid://shopify/Product/10368017137956"
EXCLUDE_FROM_BAG_SKUS = {"24630"}   # skip creating bag counterpart
BAG_PRICE = "6.00"
BAG_WEIGHT_LB = 50.0
BAG_INVENTORY_POLICY = "CONTINUE"
TON_INVENTORY_POLICY = "CONTINUE"   # applied to all 5 existing variants
PACE_SECONDS = 0.08

NEW_SEO_TITLE = "River Rock Stone \u2014 Bulk by the Ton or 50 lb Bag | Garoppo's"
NEW_SEO_DESC = (
    "Natural rounded river rock in 3/8\", 3/4\", 1-1/2\", 1-3\", and 3-9\". "
    "Bulk by the ton for large projects or 50 lb bags for smaller jobs. "
    "Pickup or delivery."
)

NEW_DESCRIPTION_HTML = """<p>Direct water where it needs to go and finish beds with a clean, natural look using River Rock Stone. Use these smooth, rounded stones to manage runoff, top-dress planting areas, and build long-lasting dry creek accents. Pick the size that fits your project, then choose bulk by the ton for large installations or a 50 lb bag for repairs, borders, and smaller features.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Ton (bulk):</strong> Cover large areas efficiently \u2014 French drains, dry creek beds, and full landscape installations. Available in 3/8\", 3/4\", 1-1/2\", 1-3\", and 3-9\".</li>
  <li><strong>50 LB Bag:</strong> Easy to handle for repairs, small accent beds, and container features. Available in 3/8\", 3/4\", 1-1/2\", and 1-3\".</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Natural stone:</strong> Add organic texture that withstands weather and heavy seasons.</li>
  <li><strong>Rounded profile:</strong> Promote drainage and reduce washouts in swales and trenches.</li>
  <li><strong>Low maintenance:</strong> Skip seasonal mulch replacement and keep beds tidy with minimal upkeep.</li>
  <li><strong>Size options:</strong> Match pathways, around trees, or larger water features with ease.</li>
  <li><strong>Clean finish:</strong> Deliver a polished, professional look to new and refreshed landscapes.</li>
</ul>

<h3>Applications</h3>
<p>Build dry creek beds, line French drains, or edge walkways and patios. Dress around trees and shrubs to help retain moisture while keeping soil off siding and hardscapes. Pair with edging to contain stones on slopes or along traffic areas.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural stone (rounded river rock)</li>
  <li><strong>Sizes:</strong> 3/8\", 3/4\", 1-1/2\", 1-3\", 3-9\" (ton); 3/8\", 3/4\", 1-1/2\", 1-3\" (50 lb bag)</li>
  <li><strong>Finish:</strong> Smooth, rounded surface</li>
  <li><strong>Colors:</strong> Mixed earth tones (tans, grays, browns; natural variation)</li>
  <li><strong>Coverage:</strong> Approx. 100 sq ft at 2 in depth (varies by size and base)</li>
</ul>

<p>Install over landscape fabric to limit weeds and migration. Rinse stones before or after placement to remove dust. For drainage lines, choose 3/4\" or larger; for paths and borders, pick 3/8\" or 3/4\" for a steadier feel underfoot. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>"""

# Alt-tag replacements keyed by media GID.
# Strips "#Ton" so each image matches on Size only (option1) and shows for
# both Ton AND 50 LB Bag variants of that size.
ALT_UPDATES = {
    "gid://shopify/MediaImage/45190795297060": 'River rock stone, 3/8 inch size. #3/8"',
    "gid://shopify/MediaImage/45190795329828": 'River rock stone, 3/4 inch size. #3/4"',
    "gid://shopify/MediaImage/45190795362596": 'River rock stone, 1-1/2 inch size. #1-1/2"',
    "gid://shopify/MediaImage/45190795395364": 'River rock stone, between 1 and 3 inches. #1-3"',
    "gid://shopify/MediaImage/45190795428132": 'River rock stone, ranging from 3 to 9 inches. #3-9"',
}


def load_config():
    cfg = json.loads(CONFIG_PATH.read_text())
    return cfg["SHOPIFY_STORE_URL"], cfg["SHOPIFY_ACCESS_TOKEN"]


def gql(store_url: str, token: str, query: str, variables=None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{store_url}/admin/api/2025-10/graphql.json",
        data=body,
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


SNAPSHOT_QUERY = """
query($id: ID!) {
  product(id: $id) {
    id title handle status
    options { name position values }
    seo { title description }
    media(first: 50) {
      edges { node { id alt ... on MediaImage { image { url } } } }
    }
    variants(first: 50) {
      edges { node {
        id sku title price inventoryPolicy
        selectedOptions { name value }
        inventoryItem {
          id unitCost { amount } measurement { weight { value unit } }
          inventoryLevels(first: 10) {
            edges { node {
              location { id name }
              quantities(names:["on_hand","available"]) { name quantity }
            } }
          }
        }
        metafields(first: 20) { edges { node { namespace key value type } } }
      } }
    }
  }
}
"""


def fetch_product(store_url, token):
    d = gql(store_url, token, SNAPSHOT_QUERY, {"id": PRODUCT_GID})
    if "errors" in d:
        print("errors:", json.dumps(d["errors"], indent=2)); sys.exit(1)
    return d["data"]["product"]


def variant_by_sku(product, sku):
    for e in product["variants"]["edges"]:
        if e["node"]["sku"] == sku:
            return e["node"]
    return None


def build_existing_updates(product):
    """Return list of ProductVariantsBulkInput for the 5 existing variants."""
    updates = []
    for e in product["variants"]["edges"]:
        v = e["node"]
        sku = v["sku"]
        upd = {"id": v["id"], "inventoryPolicy": TON_INVENTORY_POLICY}
        if sku not in EXCLUDE_FROM_BAG_SKUS:
            upd["inventoryItem"] = {"sku": f"{sku}-01"}
        updates.append(upd)
    return updates


def build_bag_creates(product):
    """Return list of ProductVariantsBulkInput for new bag variants."""
    creates = []
    for e in product["variants"]["edges"]:
        v = e["node"]
        if v["sku"] in EXCLUDE_FROM_BAG_SKUS:
            continue
        size = next((s["value"] for s in v["selectedOptions"] if s["name"] == "Size"), None)
        if size is None:
            continue
        # Copy color_swatch_image metafield from source Ton variant if present
        mfs = []
        for me in v["metafields"]["edges"]:
            n = me["node"]
            if n["namespace"] == "custom" and n["key"] == "color_swatch_image":
                mfs.append({
                    "namespace": n["namespace"],
                    "key": n["key"],
                    "value": n["value"],
                    "type": n["type"],
                })
        creates.append({
            "optionValues": [
                {"optionName": "Size", "name": size},
                {"optionName": "Unit of Sale", "name": "50 LB Bag"},
            ],
            "price": BAG_PRICE,
            "taxable": True,
            "inventoryPolicy": BAG_INVENTORY_POLICY,
            "inventoryItem": {
                "sku": f"{v['sku']}-02",
                "tracked": True,
                "measurement": {"weight": {"value": BAG_WEIGHT_LB, "unit": "POUNDS"}},
            },
            "metafields": mfs,
        })
    return creates


BULK_UPDATE_MUTATION = """
mutation bulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id sku inventoryPolicy }
    userErrors { field message code }
  }
}
"""

BULK_CREATE_MUTATION = """
mutation bulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!, $strategy: ProductVariantsBulkCreateStrategy) {
  productVariantsBulkCreate(productId: $productId, variants: $variants, strategy: $strategy) {
    productVariants {
      id sku price inventoryPolicy
      selectedOptions { name value }
      inventoryItem { id measurement { weight { value unit } } }
    }
    product { options { name values } }
    userErrors { field message code }
  }
}
"""

FILE_UPDATE_MUTATION = """
mutation fileUpdate($files: [FileUpdateInput!]!) {
  fileUpdate(files: $files) { files { id alt } userErrors { field message code } }
}
"""

PRODUCT_UPDATE_MUTATION = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id seo { title description } }
    userErrors { field message }
  }
}
"""


def print_plan(product, updates, creates):
    print("=" * 72)
    print("RIVER ROCK STONE — RESHAPE PLAN")
    print("=" * 72)
    print(f"\nProduct: {product['title']}  {product['id']}  status={product['status']}")
    print(f"Options (current): {[(o['name'],o['position'],o['values']) for o in product['options']]}")
    print(f"\n--- Existing variants to update (policy + SKU rename where not excluded) ---")
    for upd in updates:
        orig = next(e["node"] for e in product["variants"]["edges"] if e["node"]["id"] == upd["id"])
        new_sku = upd.get("inventoryItem", {}).get("sku", orig["sku"])
        skipped = "  [SKIP rename, 24630]" if orig["sku"] in EXCLUDE_FROM_BAG_SKUS else ""
        print(f"  {orig['id']}  sku {orig['sku']!r} -> {new_sku!r}  policy {orig['inventoryPolicy']}->{upd['inventoryPolicy']}{skipped}")

    print(f"\n--- New bag variants to create ---")
    for c in creates:
        size = next(o["name"] for o in c["optionValues"] if o["optionName"] == "Size")
        uos = next(o["name"] for o in c["optionValues"] if o["optionName"] == "Unit of Sale")
        mfct = len(c.get("metafields", []))
        print(f"  sku={c['inventoryItem']['sku']!r}  Size={size!r}  UoS={uos!r}  price=${c['price']}  weight={c['inventoryItem']['measurement']['weight']}  policy={c['inventoryPolicy']}  mfs={mfct}")

    print(f"\n--- Media alt updates ---")
    for e in product["media"]["edges"]:
        n = e["node"]
        new_alt = ALT_UPDATES.get(n["id"])
        if new_alt and new_alt != n["alt"]:
            print(f"  {n['id']}\n    OLD: {n['alt']!r}\n    NEW: {new_alt!r}")

    print(f"\n--- SEO ---")
    print(f"  title: {NEW_SEO_TITLE!r} ({len(NEW_SEO_TITLE)} chars)")
    print(f"  desc : {NEW_SEO_DESC!r} ({len(NEW_SEO_DESC)} chars)")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    store_url, token = load_config()
    product = fetch_product(store_url, token)
    updates = build_existing_updates(product)
    creates = build_bag_creates(product)
    print_plan(product, updates, creates)

    if not args.execute:
        print("\nDRY RUN. Re-run with --execute to apply.")
        return

    print("\n>>> EXECUTING <<<\n")

    # 1) bulk update: rename + policy
    print("[1/4] productVariantsBulkUpdate ...")
    r = gql(store_url, token, BULK_UPDATE_MUTATION, {"productId": PRODUCT_GID, "variants": updates})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["productVariantsBulkUpdate"]
    if payload["userErrors"]:
        print("userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    for pv in payload["productVariants"]:
        print(f"    updated: {pv['id']} sku={pv['sku']} policy={pv['inventoryPolicy']}")
    time.sleep(PACE_SECONDS)

    # 2) bulk create bag variants
    print("\n[2/4] productVariantsBulkCreate ...")
    r = gql(store_url, token, BULK_CREATE_MUTATION,
            {"productId": PRODUCT_GID, "variants": creates, "strategy": "REMOVE_STANDALONE_VARIANT"})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["productVariantsBulkCreate"]
    if payload["userErrors"]:
        print("userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    for pv in payload["productVariants"]:
        so = {s["name"]: s["value"] for s in pv["selectedOptions"]}
        w = pv["inventoryItem"]["measurement"]["weight"] if pv["inventoryItem"]["measurement"] else None
        print(f"    created: {pv['id']} sku={pv['sku']} opts={so} price=${pv['price']} policy={pv['inventoryPolicy']} weight={w}")
    if payload.get("product"):
        print(f"    UoS option values now: {[o['values'] for o in payload['product']['options'] if o['name']=='Unit of Sale']}")
    time.sleep(PACE_SECONDS)

    # 3) alt updates
    print("\n[3/4] fileUpdate (5 alt tags) ...")
    files_payload = [{"id": gid, "alt": alt} for gid, alt in ALT_UPDATES.items()]
    r = gql(store_url, token, FILE_UPDATE_MUTATION, {"files": files_payload})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["fileUpdate"]
    if payload["userErrors"]:
        print("userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    for f in payload["files"]:
        print(f"    {f['id']} alt={f['alt']!r}")
    time.sleep(PACE_SECONDS)

    # 4) product update (seo + description)
    print("\n[4/4] productUpdate (SEO + description) ...")
    r = gql(store_url, token, PRODUCT_UPDATE_MUTATION, {
        "input": {
            "id": PRODUCT_GID,
            "seo": {"title": NEW_SEO_TITLE, "description": NEW_SEO_DESC},
            "descriptionHtml": NEW_DESCRIPTION_HTML,
        }
    })
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["productUpdate"]
    if payload["userErrors"]:
        print("userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    print(f"    SEO set: {payload['product']['seo']}")
    time.sleep(PACE_SECONDS)

    # Verify
    print("\n--- VERIFYING ---")
    final = fetch_product(store_url, token)
    print(f"Options: {[(o['name'],o['values']) for o in final['options']]}")
    print(f"SEO: title={final['seo']['title']!r} desc={final['seo']['description']!r}")
    print(f"Variants ({len(final['variants']['edges'])}):")
    for e in final["variants"]["edges"]:
        v = e["node"]
        so = {s["name"]: s["value"] for s in v["selectedOptions"]}
        inv = {}
        for le in v["inventoryItem"]["inventoryLevels"]["edges"]:
            ln = le["node"]
            qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
            inv[ln["location"]["name"]] = qs.get("on_hand", 0)
        w = v["inventoryItem"]["measurement"]["weight"] if v["inventoryItem"]["measurement"] else None
        print(f"  {v['sku']:<14} {so}  ${v['price']}  policy={v['inventoryPolicy']}  weight={w}  inv={inv}  cost={v['inventoryItem']['unitCost']}")
    print("\nMedia:")
    for e in final["media"]["edges"]:
        n = e["node"]
        print(f"  {n['id']} alt={n['alt']!r}")
    print("\nDone.")


if __name__ == "__main__":
    main()
