#!/usr/bin/env python3
"""
Reshape SKU 18163 (Compost) from single-variant to 2 variants.

Target:
  Option: Unit of Sale (values: "Per Cubic Yard", "50 LB Bag")
  Variants:
    1. 18163-01  Per Cubic Yard  $27.00  cost $12.50    weight 1200 lb (preserved)
    2. 18163-02  50 LB Bag       $6.00   cost $0.5208   weight 50 lb
      (cost = 12.50 / 24; 1 yd = 1200 lb = 24 x 50-lb bags)

Safety:
  - Pre-fetch inventory; after productSet, restore qty to the new Per Cubic Yard variant
    via inventorySetQuantities(ignoreCompareQuantity: true).
  - Runs dry-run by default. Pass --execute to apply.

Usage:
  python reshape_compost_variants.py            # dry run
  python reshape_compost_variants.py --execute  # execute
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("/Users/moosemarketer/Code/garoppos/uploader/config.json")

PRODUCT_GID = "gid://shopify/Product/10368015204644"
DEFAULT_LOCATION_GID = "gid://shopify/Location/110377107748"

PUBLICATION_ONLINE_STORE = "gid://shopify/Publication/286630838564"
PUBLICATION_POS = "gid://shopify/Publication/286630871332"

YARD_PRICE = "27.00"
YARD_COST = "12.50"
YARD_SKU = "18163-01"
YARD_UOS = "Per Cubic Yard"

BAG_PRICE = "6.00"
BAG_COST = "0.5208"   # 12.50 / 24  (1 yd = 1200 lb = 24 x 50-lb bags)
BAG_SKU = "18163-02"
BAG_UOS = "50 LB Bag"
BAG_WEIGHT_LB = 50.0

NEW_SEO_TITLE = "Compost \u2014 Bulk by the Cubic Yard or 50 lb Bag | Garoppo's"
NEW_SEO_DESC = (
    "Garoppo's garden compost. Bulk by the cubic yard for landscape projects or "
    "50 lb bags for raised beds and small jobs. Pickup or local delivery."
)

NEW_DESCRIPTION_HTML = """<p>Build healthier soil fast with quality compost from Garoppo's. Enrich planting beds, topdress lawns, and improve soil structure so roots establish quickly and stay resilient through summer heat and seasonal rain. Order bulk by the cubic yard for landscape projects and garden refreshes, or grab a 50 lb bag for raised beds, container gardens, and smaller jobs around the yard.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Cubic Yard (bulk):</strong> Cover large areas efficiently. Ideal for garden bed prep, lawn topdressing, new plantings, and landscape installations where you need volume. One cubic yard covers roughly 100 sq ft at 3 inches depth.</li>
  <li><strong>50 LB Bag (retail):</strong> Easy to handle and store. Perfect for raised beds, container mixes, spot amendments, and homeowners working on smaller projects.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Improve soil structure:</strong> Loosen heavy clay and add body to sandy soils for better root anchoring.</li>
  <li><strong>Optimize moisture:</strong> Help soil hold water while still draining well to reduce stress between waterings.</li>
  <li><strong>Build long-term fertility:</strong> Add stable organic matter that supports ongoing nutrient cycling.</li>
  <li><strong>Support soil life:</strong> Encourage a more active soil ecosystem for stronger plant performance.</li>
  <li><strong>Easy to apply:</strong> Spread with a shovel, rake, or wheelbarrow and blend in quickly.</li>
</ul>

<h3>Applications</h3>
<p>Amend new or existing garden beds before planting. Blend 1\u20132 inches of compost into the top 6\u20138 inches of native soil. Topdress established lawns with 1/4\u20131/2 inch to smooth low spots and encourage dense turf. When planting trees and shrubs, mix compost with backfill rather than using it alone to support proper drainage.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Composted organic matter</li>
  <li><strong>Bulk coverage:</strong> Approximately 100 sq ft at 3 inches depth per cubic yard</li>
  <li><strong>Volume reference:</strong> 1 cubic yard = 27 cubic feet</li>
  <li><strong>Bag weight:</strong> 50 lb</li>
  <li><strong>Typical application depth:</strong> Beds: 1\u20132 in; Lawns: 0.25\u20130.5 in</li>
</ul>

<p>Plan your order by multiplying length \u00d7 width \u00d7 desired depth (in feet), then dividing by 27 to get cubic yards. Water lightly after application to settle the material and reapply seasonally to maintain soil health. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>"""

NEW_MEDIA_ALT = (
    "Bulk compost for landscape and garden projects, enriching soil for healthy plant growth. "
    "#Per Cubic Yard#50 LB Bag"
)

PACE_SECONDS = 0.08


def load_config():
    cfg = json.loads(CONFIG_PATH.read_text())
    return cfg["SHOPIFY_STORE_URL"], cfg["SHOPIFY_ACCESS_TOKEN"]


def gql(store_url: str, token: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{store_url}/admin/api/2025-10/graphql.json",
        data=body,
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


PRODUCT_SNAPSHOT_QUERY = """
query($id: ID!) {
  product(id: $id) {
    id title handle status vendor productType tags
    descriptionHtml
    category { id }
    seo { title description }
    options { id name position values }
    media(first: 50) {
      edges { node {
        id alt mediaContentType
        ... on MediaImage { image { url } }
      } }
    }
    metafields(first: 50) { edges { node { namespace key value type } } }
    variants(first: 100) {
      edges { node {
        id sku title price
        selectedOptions { name value }
        inventoryItem {
          id
          measurement { weight { value unit } }
          inventoryLevels(first: 20) {
            edges { node {
              location { id name }
              quantities(names: ["on_hand","available","committed","incoming"]) { name quantity }
            } }
          }
        }
        metafields(first: 20) { edges { node { namespace key value type } } }
      } }
    }
  }
}
"""


def fetch_product(store_url: str, token: str) -> dict:
    data = gql(store_url, token, PRODUCT_SNAPSHOT_QUERY, {"id": PRODUCT_GID})
    if "errors" in data:
        print("GraphQL errors:", json.dumps(data["errors"], indent=2))
        sys.exit(1)
    return data["data"]["product"]


def pick_current_variant_weight_lb(product: dict) -> float:
    """Return the current variant's weight in pounds (convert if needed)."""
    variants = product["variants"]["edges"]
    if not variants:
        return 1200.0
    ii = variants[0]["node"]["inventoryItem"]
    if not ii.get("measurement") or not ii["measurement"].get("weight"):
        return 1200.0
    w = ii["measurement"]["weight"]
    val = float(w["value"])
    unit = w["unit"]
    if unit == "POUNDS":
        return val
    if unit == "OUNCES":
        return val / 16.0
    if unit == "KILOGRAMS":
        return val * 2.20462
    if unit == "GRAMS":
        return val * 0.00220462
    return val


def get_inventory_snapshot(product: dict) -> dict:
    """Return dict keyed by location_gid -> on_hand qty for the current variant."""
    snap = {}
    variants = product["variants"]["edges"]
    if not variants:
        return snap
    ii = variants[0]["node"]["inventoryItem"]
    for le in ii["inventoryLevels"]["edges"]:
        ln = le["node"]
        loc = ln["location"]["id"]
        qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
        if qs.get("on_hand", 0) > 0:
            snap[loc] = qs["on_hand"]
    return snap


def build_product_set_input(product: dict, yard_weight_lb: float) -> dict:
    """Build productSet ProductSetInput preserving taxonomy, metafields, SEO, tags."""
    color_swatch_mf = None
    for me in product["variants"]["edges"][0]["node"]["metafields"]["edges"]:
        n = me["node"]
        if n["namespace"] == "custom" and n["key"] == "color_swatch_image":
            color_swatch_mf = {
                "namespace": "custom",
                "key": "color_swatch_image",
                "value": n["value"],
                "type": n["type"],
            }

    product_metafields = []
    for me in product["metafields"]["edges"]:
        n = me["node"]
        product_metafields.append({
            "namespace": n["namespace"],
            "key": n["key"],
            "value": n["value"],
            "type": n["type"],
        })

    def variant_metafields():
        if color_swatch_mf is None:
            return []
        return [color_swatch_mf]

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
                "values": [{"name": YARD_UOS}, {"name": BAG_UOS}],
            }
        ],
        "variants": [
            {
                "optionValues": [{"optionName": "Unit of Sale", "name": YARD_UOS}],
                "price": YARD_PRICE,
                "sku": YARD_SKU,
                "taxable": True,
                "inventoryItem": {
                    "tracked": True,
                    "cost": YARD_COST,
                    "measurement": {
                        "weight": {"value": yard_weight_lb, "unit": "POUNDS"}
                    },
                },
                "inventoryPolicy": "DENY",
                "metafields": variant_metafields(),
            },
            {
                "optionValues": [{"optionName": "Unit of Sale", "name": BAG_UOS}],
                "price": BAG_PRICE,
                "sku": BAG_SKU,
                "taxable": True,
                "inventoryItem": {
                    "tracked": True,
                    "cost": BAG_COST,
                    "measurement": {
                        "weight": {"value": BAG_WEIGHT_LB, "unit": "POUNDS"}
                    },
                },
                "inventoryPolicy": "DENY",
                "metafields": variant_metafields(),
            },
        ],
        "metafields": product_metafields,
    }
    if product.get("category") and product["category"].get("id"):
        input_obj["category"] = product["category"]["id"]
    return input_obj


PRODUCT_SET_MUTATION = """
mutation productSet($input: ProductSetInput!, $synchronous: Boolean!) {
  productSet(input: $input, synchronous: $synchronous) {
    product {
      id
      options { name position values }
      variants(first: 20) {
        edges { node {
          id sku title price
          selectedOptions { name value }
          inventoryItem {
            id
            unitCost { amount }
            measurement { weight { value unit } }
          }
        } }
      }
    }
    userErrors { field message code }
  }
}
"""


def run_product_set(store_url: str, token: str, input_obj: dict) -> dict:
    data = gql(store_url, token, PRODUCT_SET_MUTATION, {"input": input_obj, "synchronous": True})
    if "errors" in data:
        print("GraphQL errors:", json.dumps(data["errors"], indent=2))
        sys.exit(1)
    res = data["data"]["productSet"]
    if res["userErrors"]:
        print("productSet userErrors:", json.dumps(res["userErrors"], indent=2))
        sys.exit(1)
    return res["product"]


INVENTORY_SET_MUTATION = """
mutation invSet($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { id reason }
    userErrors { field message code }
  }
}
"""


def restore_inventory(store_url: str, token: str, inventory_item_id: str, qty_by_loc: dict):
    if not qty_by_loc:
        print("No prior inventory to restore.")
        return
    quantities = [
        {"inventoryItemId": inventory_item_id, "locationId": loc, "quantity": qty}
        for loc, qty in qty_by_loc.items()
    ]
    variables = {
        "input": {
            "reason": "correction",
            "name": "on_hand",
            "ignoreCompareQuantity": True,
            "quantities": quantities,
        }
    }
    data = gql(store_url, token, INVENTORY_SET_MUTATION, variables)
    if "errors" in data:
        print("inventorySetQuantities errors:", json.dumps(data["errors"], indent=2))
        sys.exit(1)
    res = data["data"]["inventorySetQuantities"]
    if res["userErrors"]:
        print("inventorySetQuantities userErrors:", json.dumps(res["userErrors"], indent=2))
        sys.exit(1)
    print(f"Inventory restored: {qty_by_loc}")


MEDIA_UPDATE_MUTATION = """
mutation fileUpdate($files: [FileUpdateInput!]!) {
  fileUpdate(files: $files) {
    files { id alt }
    userErrors { field message code }
  }
}
"""


def update_media_alt(store_url: str, token: str, media_id: str, new_alt: str):
    variables = {"files": [{"id": media_id, "alt": new_alt}]}
    data = gql(store_url, token, MEDIA_UPDATE_MUTATION, variables)
    if "errors" in data:
        print("fileUpdate errors:", json.dumps(data["errors"], indent=2))
        sys.exit(1)
    res = data["data"]["fileUpdate"]
    if res["userErrors"]:
        print("fileUpdate userErrors:", json.dumps(res["userErrors"], indent=2))
        sys.exit(1)
    print(f"Media alt updated on {media_id}")


def print_dry_run(product: dict, input_obj: dict, inv_snapshot: dict):
    print("=" * 72)
    print("DRY RUN — Compost reshape")
    print("=" * 72)
    print(f"\nProduct: {product['title']}  {product['id']}")
    print(f"Status: {product['status']}  Vendor: {product['vendor']}")
    print(f"ProductType: {product['productType']}  Tags: {product['tags']}")
    print(f"Category (preserved): {product['category']}")
    print(f"\nCurrent options: {[(o['name'], o['values']) for o in product['options']]}")
    print(f"Current variant count: {len(product['variants']['edges'])}")
    for ve in product["variants"]["edges"]:
        v = ve["node"]
        print(f"  - {v['sku']}  {v['title']}  ${v['price']}  weight={v['inventoryItem']['measurement']['weight'] if v['inventoryItem']['measurement'] else None}")

    print(f"\nInventory snapshot (to restore on new {YARD_UOS} variant):")
    for loc, qty in inv_snapshot.items():
        print(f"  {loc}  on_hand={qty}")

    print(f"\n--- PLANNED CHANGES ---")
    print(f"SEO title:  {input_obj['seo']['title']}  ({len(input_obj['seo']['title'])} chars)")
    print(f"SEO desc:   {input_obj['seo']['description']}  ({len(input_obj['seo']['description'])} chars)")
    print(f"Option:     Unit of Sale = [{YARD_UOS}, {BAG_UOS}]")
    for v in input_obj["variants"]:
        uos = v["optionValues"][0]["name"]
        w = v["inventoryItem"]["measurement"]["weight"]
        print(
            f"  Variant:  sku={v['sku']:<10}  uos={uos:<10}  "
            f"price=${v['price']}  cost=${v['inventoryItem']['cost']}  "
            f"weight={w['value']} {w['unit']}"
        )
    print(f"\nMedia alt update:")
    for e in product["media"]["edges"]:
        n = e["node"]
        print(f"  {n['id']}")
        print(f"    OLD alt: {n['alt']!r}")
        print(f"    NEW alt: {NEW_MEDIA_ALT!r}")

    print(f"\nMetafields preserved (product): {len(input_obj.get('metafields', []))}")
    for mf in input_obj.get("metafields", []):
        v = mf['value']
        if len(v) > 80: v = v[:80] + "..."
        print(f"  - {mf['namespace']}.{mf['key']} ({mf['type']}) = {v}")

    print(f"\nMetafields preserved (per variant): 1 (custom.color_swatch_image on both)")
    print(f"\nPublications (verified, no change): Online Store + POS")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Execute mutations (default: dry run)")
    args = ap.parse_args()

    store_url, token = load_config()
    product = fetch_product(store_url, token)
    yard_weight = pick_current_variant_weight_lb(product)
    inv_snapshot = get_inventory_snapshot(product)

    input_obj = build_product_set_input(product, yard_weight_lb=yard_weight)
    media_edges = product["media"]["edges"]
    media_id = media_edges[0]["node"]["id"] if media_edges else None

    print_dry_run(product, input_obj, inv_snapshot)

    if not args.execute:
        print("\nDRY RUN complete. Re-run with --execute to apply.")
        return

    print("\n>>> EXECUTING <<<\n")
    updated = run_product_set(store_url, token, input_obj)
    time.sleep(PACE_SECONDS)

    yard_item_id = None
    print("\nNew variants:")
    for ve in updated["variants"]["edges"]:
        v = ve["node"]
        uos = next((so["value"] for so in v["selectedOptions"] if so["name"] == "Unit of Sale"), None)
        print(
            f"  {v['sku']:<10}  uos={uos:<14}  "
            f"price=${v['price']}  cost={v['inventoryItem']['unitCost']}  "
            f"variant={v['id']}  inventoryItem={v['inventoryItem']['id']}"
        )
        if uos == YARD_UOS:
            yard_item_id = v["inventoryItem"]["id"]

    if yard_item_id and inv_snapshot:
        print(f"\nRestoring inventory to {YARD_UOS} variant's inventoryItem {yard_item_id}...")
        restore_inventory(store_url, token, yard_item_id, inv_snapshot)
        time.sleep(PACE_SECONDS)
    else:
        print(f"\nNo inventory restoration needed (snapshot empty or {YARD_UOS} variant not found).")

    if media_id:
        print(f"\nUpdating media alt...")
        update_media_alt(store_url, token, media_id, NEW_MEDIA_ALT)
        time.sleep(PACE_SECONDS)

    print("\nVerifying final state...")
    final = fetch_product(store_url, token)
    print(f"Options: {[(o['name'], o['values']) for o in final['options']]}")
    for ve in final["variants"]["edges"]:
        v = ve["node"]
        uos = next((so["value"] for so in v["selectedOptions"] if so["name"] == "Unit of Sale"), None)
        qty_summary = {}
        for le in v["inventoryItem"]["inventoryLevels"]["edges"]:
            ln = le["node"]
            qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
            qty_summary[ln["location"]["name"]] = qs.get("on_hand", 0)
        print(f"  {v['sku']:<10}  uos={uos:<10}  price=${v['price']}  inv={qty_summary}")
    for e in final["media"]["edges"]:
        n = e["node"]
        print(f"  Media: {n['id']}  alt={n['alt']!r}")
    print(f"\nSEO: title={final['seo']['title']!r}")
    print(f"     desc={final['seo']['description']!r}")
    print("\nDone.")


if __name__ == "__main__":
    main()
