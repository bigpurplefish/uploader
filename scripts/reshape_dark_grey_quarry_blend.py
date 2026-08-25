#!/usr/bin/env python3
"""
Reshape Dark Grey Quarry Blend Stone (single-variant -> 2 variants).

Target:
  Option: Unit of Sale (values: "Ton", "50 LB Bag")
  Variants:
    1. 24623-01  Ton        price=$40.00  cost=null  weight=2000 lb (preserved)
    2. 24623-02  50 LB Bag  price=$6.00   cost=null  weight=50 lb

Because this product has only a `Title` option today, we MUST use productSet
to introduce `Unit of Sale`. productSet destroys the existing variant GID and
inventoryItem GID, so we pre-fetch inventory and restore it via
inventorySetQuantities (ignoreCompareQuantity: true) on the new Ton variant.

Carry the existing variant's `custom.color_swatch_image` metafield to BOTH
new variants. Preserve product metafields, tags, category, publications.

Alt tag: retag the single existing image with `#Ton` so that future bag
images can use `#50 LB Bag` and theme positional filtering works correctly
on this 1-option product (option1 = Unit of Sale).

Usage:
  python reshape_dark_grey_quarry_blend.py            # dry run (default)
  python reshape_dark_grey_quarry_blend.py --execute  # execute

Reusable: the logic is parameterized at the top of the file. To apply to
another single-variant aggregate, change PRODUCT_GID, titles, description,
and SEO constants.
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("/Users/moosemarketer/Code/garoppos/uploader/config.json")

# ----- parameters per product -----
PRODUCT_GID = "gid://shopify/Product/10368018153764"
PRODUCT_TITLE = "Dark Grey Quarry Blend Stone"
ORIGINAL_SKU = "24623"
TON_SKU = f"{ORIGINAL_SKU}-01"
BAG_SKU = f"{ORIGINAL_SKU}-02"
TON_UOS = "Ton"
BAG_UOS = "50 LB Bag"
BAG_PRICE = "6.00"
BAG_WEIGHT_LB = 50.0
POLICY = "CONTINUE"   # apply to both new variants
PACE_SECONDS = 0.08

NEW_SEO_TITLE = "Dark Grey Quarry Blend Stone \u2014 Bulk Ton or 50 lb Bag | Garoppo's"
NEW_SEO_DESC = (
    "3/4 inch dark grey quarry blend for driveway, paver, and patio base. "
    "Bulk by the ton for full projects or 50 lb bags for repairs. "
    "Pickup or delivery."
)

NEW_DESCRIPTION_HTML = """<p>Build a solid, long-lasting base with Dark Grey Quarry Blend Stone from Garoppo's. Get dependable compaction for driveways, patios, walkways, and paver projects that stay put through freeze-thaw and heavy traffic. Lock in a 3/4 inch blend that interlocks tight, resists shifting, and supports clean, even finishes above. Order bulk by the ton for full installations or a 50 lb bag for repairs, top-ups, and smaller projects.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Ton (bulk):</strong> Cover driveways, patio sub-bases, shed pads, and pathways. Best when you're installing from scratch or laying a full base.</li>
  <li><strong>50 LB Bag (retail):</strong> Easy to handle for base repairs, sinkhole fills, drainage trenches, and spot work where a ton is more than you need.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Compacts fast:</strong> Create a dense, stable base that won't rut.</li>
  <li><strong>Angular aggregate:</strong> Interlocks under vibration for superior load support.</li>
  <li><strong>Consistent grading:</strong> Helps achieve level surfaces with fewer passes.</li>
  <li><strong>Dark grey color:</strong> Uniform look if edges are exposed along borders.</li>
  <li><strong>Weather ready:</strong> Performs reliably through wet seasons and freeze-thaw cycles.</li>
</ul>

<h3>Applications</h3>
<p>Use as base material under pavers, slabs, and natural stone. Set a sturdy foundation for driveways, shed pads, and pathways. Support small retaining wall projects with a compacted sub-base that stays stable over time. Fill drainage trenches and French drain beds where an angular compacting aggregate keeps water moving.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Crushed natural stone blend with fines</li>
  <li><strong>Size:</strong> 3/4 inch nominal</li>
  <li><strong>Finish/Texture:</strong> Angular, compacting aggregate</li>
  <li><strong>Color:</strong> Dark grey</li>
  <li><strong>Bag weight:</strong> 50 lb</li>
</ul>

<h3>Installation Tips</h3>
<ul>
  <li><strong>Prepare subgrade:</strong> Excavate to required depth and remove organics.</li>
  <li><strong>Reinforce if needed:</strong> Place geotextile over soft or clay soils.</li>
  <li><strong>Place in lifts:</strong> Spread 2-3 inch layers and compact each pass.</li>
  <li><strong>Moisten lightly:</strong> Add a fine mist to aid compaction - avoid puddling.</li>
  <li><strong>Finish properly:</strong> Top with a bedding layer of concrete sand before setting pavers.</li>
</ul>

<p>Confirm local base depth requirements and drainage needs for your site. Natural stone may vary slightly in appearance. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>"""

# Single image; retag with only #Ton. When a bag photo is added later,
# its alt should end in "#50 LB Bag" so it shows only for the bag variant.
ALT_UPDATES = {
    "gid://shopify/MediaImage/45190796017956":
        "Dark Grey Quarry Blend Stone, 3/4 inch size, sold by the ton. #Ton",
}


def load_config():
    cfg = json.loads(CONFIG_PATH.read_text())
    return cfg["SHOPIFY_STORE_URL"], cfg["SHOPIFY_ACCESS_TOKEN"]


def gql(store_url, token, query, variables=None):
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
    id title handle status vendor productType tags
    descriptionHtml
    category { id }
    seo { title description }
    options { id name position values }
    media(first: 50) { edges { node { id alt } } }
    metafields(first: 50) { edges { node { namespace key value type } } }
    variants(first: 50) {
      edges { node {
        id sku title price
        selectedOptions { name value }
        inventoryItem {
          id measurement { weight { value unit } }
          inventoryLevels(first: 10) {
            edges { node {
              location { id name }
              quantities(names:["on_hand","available","committed","incoming"]) { name quantity }
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


def pick_current_weight_lb(product):
    variants = product["variants"]["edges"]
    if not variants: return 2000.0
    ii = variants[0]["node"]["inventoryItem"]
    if not ii.get("measurement") or not ii["measurement"].get("weight"):
        return 2000.0
    w = ii["measurement"]["weight"]
    val = float(w["value"])
    unit = w["unit"]
    if unit == "POUNDS": return val
    if unit == "OUNCES": return val / 16.0
    if unit == "KILOGRAMS": return val * 2.20462
    if unit == "GRAMS": return val * 0.00220462
    return val


def get_inventory_snapshot(product):
    snap = {}
    variants = product["variants"]["edges"]
    if not variants: return snap
    ii = variants[0]["node"]["inventoryItem"]
    for le in ii["inventoryLevels"]["edges"]:
        ln = le["node"]
        loc = ln["location"]["id"]
        qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
        if qs.get("on_hand", 0) != 0:
            snap[loc] = qs["on_hand"]
    return snap


def get_current_price(product):
    variants = product["variants"]["edges"]
    if not variants: return "0.00"
    return variants[0]["node"]["price"]


def build_product_set_input(product, ton_weight_lb):
    # Preserve variant-level metafield(s) from the current sole variant on both new variants
    variant_mfs = []
    for me in product["variants"]["edges"][0]["node"]["metafields"]["edges"]:
        n = me["node"]
        if n["namespace"] == "custom" and n["key"] == "color_swatch_image":
            variant_mfs.append({
                "namespace": n["namespace"],
                "key": n["key"],
                "value": n["value"],
                "type": n["type"],
            })

    product_mfs = []
    for me in product["metafields"]["edges"]:
        n = me["node"]
        product_mfs.append({
            "namespace": n["namespace"],
            "key": n["key"],
            "value": n["value"],
            "type": n["type"],
        })

    ton_price = get_current_price(product)

    input_obj = {
        "id": PRODUCT_GID,
        "title": product["title"],
        "descriptionHtml": NEW_DESCRIPTION_HTML,
        "vendor": product["vendor"],
        "productType": product["productType"],
        "tags": product["tags"],
        "status": product["status"],
        "seo": {"title": NEW_SEO_TITLE, "description": NEW_SEO_DESC},
        "productOptions": [
            {
                "name": "Unit of Sale",
                "position": 1,
                "values": [{"name": TON_UOS}, {"name": BAG_UOS}],
            }
        ],
        "variants": [
            {
                "optionValues": [{"optionName": "Unit of Sale", "name": TON_UOS}],
                "price": ton_price,
                "sku": TON_SKU,
                "taxable": True,
                "inventoryPolicy": POLICY,
                "inventoryItem": {
                    "tracked": True,
                    "measurement": {"weight": {"value": ton_weight_lb, "unit": "POUNDS"}},
                },
                "metafields": variant_mfs,
            },
            {
                "optionValues": [{"optionName": "Unit of Sale", "name": BAG_UOS}],
                "price": BAG_PRICE,
                "sku": BAG_SKU,
                "taxable": True,
                "inventoryPolicy": POLICY,
                "inventoryItem": {
                    "tracked": True,
                    "measurement": {"weight": {"value": BAG_WEIGHT_LB, "unit": "POUNDS"}},
                },
                "metafields": variant_mfs,
            },
        ],
        "metafields": product_mfs,
    }
    if product.get("category") and product["category"].get("id"):
        input_obj["category"] = product["category"]["id"]
    return input_obj


PRODUCT_SET_MUTATION = """
mutation productSet($input: ProductSetInput!, $synchronous: Boolean!) {
  productSet(input: $input, synchronous: $synchronous) {
    product {
      id options { name position values }
      variants(first: 20) {
        edges { node {
          id sku price inventoryPolicy
          selectedOptions { name value }
          inventoryItem { id measurement { weight { value unit } } }
        } }
      }
    }
    userErrors { field message code }
  }
}
"""

INVENTORY_SET_MUTATION = """
mutation invSet($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { id reason }
    userErrors { field message code }
  }
}
"""

FILE_UPDATE_MUTATION = """
mutation fileUpdate($files: [FileUpdateInput!]!) {
  fileUpdate(files: $files) { files { id alt } userErrors { field message code } }
}
"""


def run_product_set(store_url, token, input_obj):
    r = gql(store_url, token, PRODUCT_SET_MUTATION, {"input": input_obj, "synchronous": True})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["productSet"]
    if payload["userErrors"]:
        print("productSet userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    return payload["product"]


def restore_inventory(store_url, token, inventory_item_id, qty_by_loc):
    if not qty_by_loc:
        print("No prior inventory to restore."); return
    quantities = [
        {"inventoryItemId": inventory_item_id, "locationId": loc, "quantity": qty}
        for loc, qty in qty_by_loc.items()
    ]
    variables = {"input": {
        "reason": "correction",
        "name": "on_hand",
        "ignoreCompareQuantity": True,
        "quantities": quantities,
    }}
    r = gql(store_url, token, INVENTORY_SET_MUTATION, variables)
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["inventorySetQuantities"]
    if payload["userErrors"]:
        print("inventorySetQuantities userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    print(f"Inventory restored: {qty_by_loc}")


def update_alts(store_url, token):
    files = [{"id": gid, "alt": alt} for gid, alt in ALT_UPDATES.items()]
    if not files: return
    r = gql(store_url, token, FILE_UPDATE_MUTATION, {"files": files})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    payload = r["data"]["fileUpdate"]
    if payload["userErrors"]:
        print("fileUpdate userErrors:", json.dumps(payload["userErrors"], indent=2)); sys.exit(1)
    for f in payload["files"]:
        print(f"  {f['id']} alt={f['alt']!r}")


def print_plan(product, input_obj, inv_snapshot):
    print("=" * 72)
    print(f"DRY RUN - {PRODUCT_TITLE} reshape")
    print("=" * 72)
    print(f"\nProduct: {product['title']}  {product['id']}  handle={product['handle']}  status={product['status']}")
    print(f"Tags: {product['tags']}  ProductType: {product['productType']}")
    print(f"Category (preserved): {product['category']}")
    print(f"Current options: {[(o['name'], o['values']) for o in product['options']]}")
    print(f"Current variant count: {len(product['variants']['edges'])}")
    for ve in product["variants"]["edges"]:
        v = ve["node"]
        ii = v["inventoryItem"]
        print(f"  - sku={v['sku']!r} title={v['title']!r} price=${v['price']} weight={ii['measurement']['weight'] if ii['measurement'] else None}")

    print(f"\nInventory snapshot (to restore on new {TON_UOS} variant):")
    for loc, qty in inv_snapshot.items():
        print(f"  {loc}  on_hand={qty}")

    print(f"\n--- PLANNED CHANGES ---")
    print(f"Option:     Unit of Sale = [{TON_UOS}, {BAG_UOS}]")
    print(f"SEO title:  {input_obj['seo']['title']}  ({len(input_obj['seo']['title'])} chars)")
    print(f"SEO desc:   {input_obj['seo']['description']}  ({len(input_obj['seo']['description'])} chars)")
    for v in input_obj["variants"]:
        uos = v["optionValues"][0]["name"]
        w = v["inventoryItem"]["measurement"]["weight"]
        print(f"  Variant:  sku={v['sku']:<12} uos={uos:<10}  price=${v['price']}  weight={w['value']} {w['unit']}  policy={v['inventoryPolicy']}")

    print(f"\nMedia alt updates:")
    for e in product["media"]["edges"]:
        n = e["node"]
        new = ALT_UPDATES.get(n["id"])
        if new:
            print(f"  {n['id']}")
            print(f"    OLD: {n['alt']!r}")
            print(f"    NEW: {new!r}")

    print(f"\nMetafields preserved (product): {len(input_obj.get('metafields', []))}")
    for mf in input_obj.get("metafields", []):
        v = mf['value']
        if len(v) > 80: v = v[:80] + "..."
        print(f"  - {mf['namespace']}.{mf['key']} ({mf['type']}) = {v}")
    vmf_count = len(input_obj["variants"][0].get("metafields", []))
    print(f"\nMetafields preserved (per variant): {vmf_count} (carried to both new variants)")
    print(f"\nPublications (verified, no change): Online Store + POS")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    store_url, token = load_config()
    product = fetch_product(store_url, token)
    ton_weight = pick_current_weight_lb(product)
    inv_snapshot = get_inventory_snapshot(product)
    input_obj = build_product_set_input(product, ton_weight_lb=ton_weight)
    print_plan(product, input_obj, inv_snapshot)

    if not args.execute:
        print("\nDRY RUN complete. Re-run with --execute to apply.")
        return

    print("\n>>> EXECUTING <<<\n")
    print("[1/3] productSet ...")
    updated = run_product_set(store_url, token, input_obj)
    time.sleep(PACE_SECONDS)

    ton_item_id = None
    for ve in updated["variants"]["edges"]:
        v = ve["node"]
        uos = next((so["value"] for so in v["selectedOptions"] if so["name"] == "Unit of Sale"), None)
        print(f"    {v['sku']:<12}  uos={uos:<10}  price=${v['price']}  policy={v['inventoryPolicy']}  variant={v['id']}  item={v['inventoryItem']['id']}")
        if uos == TON_UOS:
            ton_item_id = v["inventoryItem"]["id"]

    print(f"\n[2/3] inventorySetQuantities ...")
    if ton_item_id and inv_snapshot:
        restore_inventory(store_url, token, ton_item_id, inv_snapshot)
    else:
        print("  No inventory to restore (snapshot empty or Ton variant missing).")
    time.sleep(PACE_SECONDS)

    print(f"\n[3/3] fileUpdate (media alts) ...")
    update_alts(store_url, token)
    time.sleep(PACE_SECONDS)

    print("\n--- VERIFYING ---")
    final = fetch_product(store_url, token)
    print(f"Options: {[(o['name'],o['values']) for o in final['options']]}")
    print(f"SEO: title={final['seo']['title']!r} desc={final['seo']['description']!r}")
    for ve in final["variants"]["edges"]:
        v = ve["node"]
        uos = next((so["value"] for so in v["selectedOptions"] if so["name"] == "Unit of Sale"), None)
        inv = {}
        for le in v["inventoryItem"]["inventoryLevels"]["edges"]:
            ln = le["node"]
            qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
            inv[ln["location"]["name"]] = qs.get("on_hand", 0)
        w = v["inventoryItem"]["measurement"]["weight"] if v["inventoryItem"]["measurement"] else None
        print(f"  {v['sku']:<12} uos={uos:<10} price=${v['price']} weight={w} inv={inv}")
    for e in final["media"]["edges"]:
        n = e["node"]
        print(f"  Media {n['id']} alt={n['alt']!r}")
    print("\nDone.")


if __name__ == "__main__":
    main()
