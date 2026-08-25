#!/usr/bin/env python3
"""
Batch reshape of single-variant aggregate products to 2-option
(Size x Unit of Sale) with Ton + 50 LB Bag variants.

Parameterized list: each entry is a dict describing one product. The script
loops over them, running the productSet + inventorySetQuantities + fileUpdate
sequence per product, with pacing.

Pattern per product:
  - productSet (synchronous) reshapes Title -> Size x UoS
  - inventorySetQuantities restores prior on_hand to the new Ton variant
  - fileUpdate normalizes each image alt to `#<Size>#Ton`
  - descriptionHtml, SEO set inside productSet

Pre-execution safety checks per product:
  - title matches
  - single variant with expected SKU
  - weight == 2000 lb (Ton convention — abort if mismatched)
If any check fails, that product is skipped with a clear reason.

Usage:
  python reshape_aggregates_batch.py             # dry run
  python reshape_aggregates_batch.py --execute   # execute
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("/Users/moosemarketer/Code/garoppos/uploader/config.json")
PACE_SECONDS = 0.08        # between mutations within one product
INTER_PRODUCT_SECONDS = 0.5  # between products


# ---- Per-product spec ----
# - size_value: string used in Size option AND in `#<Size>#Ton` alt hashtag
# - media_alt_updates: {media_id: new_alt} - only images where alt needs changing
# - seo_title / seo_desc / description_html: final copy set inside productSet
# - expected_weight_lb: 2000.0 by default; set explicitly if different
PRODUCTS = [
    {
        "label": "Goose Egg Stone",
        "product_gid": "gid://shopify/Product/10368018743588",
        "expected_title": "Goose Egg Stone",
        "original_sku": "29273",
        "size_value": "2-4\"",
        "expected_weight_lb": 2000.0,
        "media_alt_updates": {
            "gid://shopify/MediaImage/45190796280100":
                "Goose Egg Stone, 2-4 inch rounded decorative stone sold by the ton. #2-4\"#Ton",
        },
        "seo_title": "Goose Egg Stone \u2014 Bulk Ton or 50 lb Bag | Garoppo's",
        "seo_desc": (
            "Rounded 2-4 inch decorative stone for landscape beds, dry creek beds, "
            "and drainage. Bulk by the ton or 50 lb bags for accents. "
            "Pickup or delivery."
        ),
        "description_html": """<p>Refresh your landscape and control runoff with Goose Egg Stone from Garoppo's, a natural 2-4 inch rounded decorative rock. Create clean borders, protect beds from washouts, and cut down on weeding with a heavy cover that stays put. Order bulk by the ton for full bed installations or grab a 50 lb bag for accent areas, downspout splash zones, and smaller features.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Ton (bulk):</strong> Cover landscape beds, dry creek beds, French drains, and foundation perimeters where you need volume. Approximately 70 sq ft coverage at 2 in depth per ton.</li>
  <li><strong>50 LB Bag (retail):</strong> Easy to handle for accents around trees and shrubs, pond surrounds, AC unit pads, and smaller decorative features where a ton is more than you need.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Rounded 2-4 in size:</strong> Resist shifting in heavy rain and stay stable on slopes.</li>
  <li><strong>Smooth, egg-like shape:</strong> Deliver a refined, finished look for beds and water features.</li>
  <li><strong>Neutral color blend:</strong> Mix of whites, tans, and grays that complements plants and hardscape.</li>
  <li><strong>Heavy, durable cover:</strong> Help suppress weeds and reduce erosion without frequent replacement.</li>
  <li><strong>Low maintenance:</strong> Won't fade or decompose like mulch, saving time season after season.</li>
</ul>

<h3>Applications</h3>
<p>Use Goose Egg Stone in landscape beds, dry creek beds, around downspouts, along foundations, and around AC units or utility areas. Define edges, buffer splash near siding, and dress up pond and fountain surrounds. Choose smaller rock for high-traffic walkways; this 2-4 in size is best for beds and drainage.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural rounded decorative stone</li>
  <li><strong>Size:</strong> Nominal 2-4 in (size and shape vary naturally)</li>
  <li><strong>Finish:</strong> Smooth, rounded surface</li>
  <li><strong>Colors:</strong> Mixed whites, tans, and grays (color may vary by load)</li>
  <li><strong>Bag weight:</strong> 50 lb</li>
  <li><strong>Coverage:</strong> About 70 sq ft per ton at 2 in depth</li>
</ul>

<p>Lay over landscape fabric to limit weeds and use edging to contain stone. Rinse after placement to reveal natural color and keep a rake handy for quick touch-ups. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>""",
    },
    {
        "label": "Light Grey Quarry Blend Stone",
        "product_gid": "gid://shopify/Product/10368018022692",
        "expected_title": "Light Grey Quarry Blend Stone",
        "original_sku": "24622",
        "size_value": "3/4\"",
        "expected_weight_lb": 2000.0,
        "media_alt_updates": {
            "gid://shopify/MediaImage/45190795919652":
                "Light Grey Quarry Blend Stone, 3/4 inch crushed aggregate sold by the ton. #3/4\"#Ton",
        },
        "seo_title": "Light Grey Quarry Blend Stone \u2014 Bulk Ton or 50 lb Bag | Garoppo's",
        "seo_desc": (
            "3/4 inch light grey quarry blend for driveway, paver, and patio base. "
            "Bulk by the ton or 50 lb bags for repairs. Pickup or delivery."
        ),
        "description_html": """<p>Build a stable, long-lasting base with Light Grey Quarry Blend Stone from Garoppo's. This 3/4 inch crushed blend compacts tight, locks in place, and supports patios, walkways, and driveways without shifting. Order bulk by the ton for full installations or grab a 50 lb bag for base repairs, sinkhole fills, and smaller projects.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Ton (bulk):</strong> Cover driveways, patio sub-bases, shed pads, and pathways. Best when you're installing from scratch or laying a full base.</li>
  <li><strong>50 LB Bag (retail):</strong> Easy to handle for base repairs, drainage trench top-ups, and spot work where a ton is more than you need.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>3/4 in gradation:</strong> Create a dense, level base that compacts evenly under pavers and slabs.</li>
  <li><strong>Angular crushed aggregate:</strong> Improve interlock to reduce movement, ruts, and settling.</li>
  <li><strong>Blend with fines:</strong> Fill voids for better stability and smoother grading.</li>
  <li><strong>Light grey color:</strong> Deliver a clean, professional finish on paths and driveway top layers.</li>
  <li><strong>Bulk efficiency:</strong> Cover large areas with fewer trips when ordered by the ton.</li>
</ul>

<h3>Applications</h3>
<p>Use as a paver base, sub-base for concrete slabs, footing material for small retaining walls, shed pads, and as a top layer for gravel driveways and walkways. Shape grades quickly, then compact in lifts for a firm, long-lasting foundation.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural crushed stone aggregate</li>
  <li><strong>Size:</strong> 3/4 in quarry blend</li>
  <li><strong>Finish/Texture:</strong> Crushed, angular stone with fines for compaction</li>
  <li><strong>Color:</strong> Light grey (natural variation will occur)</li>
  <li><strong>Bag weight:</strong> 50 lb</li>
  <li><strong>Coverage per ton:</strong> About 100 sq ft at 2 in depth (varies by moisture and compaction)</li>
</ul>

<p>Compact in 2-3 in lifts for best results, and maintain proper slope (about 1-2%) to shed water. Top off and re-compact high-traffic areas as needed to keep surfaces smooth. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>""",
    },
]


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
    id title handle status vendor productType tags descriptionHtml
    category { id }
    seo { title description }
    options { name position values }
    media(first: 50) { edges { node { id alt } } }
    metafields(first: 50) { edges { node { namespace key value type } } }
    variants(first: 50) {
      edges { node {
        id sku price inventoryPolicy
        selectedOptions { name value }
        inventoryItem {
          id measurement { weight { value unit } }
          unitCost { amount }
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


def fetch_product(store_url, token, pid):
    d = gql(store_url, token, SNAPSHOT_QUERY, {"id": pid})
    if "errors" in d:
        raise RuntimeError(f"snapshot errors: {d['errors']}")
    return d["data"]["product"]


def weight_lb(weight_obj):
    if not weight_obj: return None
    val = float(weight_obj["value"]); unit = weight_obj["unit"]
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
        qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
        if qs.get("on_hand", 0) != 0:
            snap[ln["location"]["id"]] = qs["on_hand"]
    return snap


def build_input(product, spec):
    # Carry custom variant metafields
    variant_mfs = []
    if product["variants"]["edges"]:
        for me in product["variants"]["edges"][0]["node"]["metafields"]["edges"]:
            n = me["node"]
            if n["namespace"] == "custom":
                variant_mfs.append({
                    "namespace": n["namespace"], "key": n["key"],
                    "value": n["value"], "type": n["type"],
                })
    # Carry product metafields
    product_mfs = []
    for me in product["metafields"]["edges"]:
        n = me["node"]
        product_mfs.append({
            "namespace": n["namespace"], "key": n["key"],
            "value": n["value"], "type": n["type"],
        })

    ton_price = product["variants"]["edges"][0]["node"]["price"]
    ton_weight = weight_lb(product["variants"]["edges"][0]["node"]["inventoryItem"]["measurement"]["weight"])

    input_obj = {
        "id": spec["product_gid"],
        "title": product["title"],
        "descriptionHtml": spec["description_html"],
        "vendor": product["vendor"],
        "productType": product["productType"],
        "tags": product["tags"],
        "status": product["status"],
        "seo": {"title": spec["seo_title"], "description": spec["seo_desc"]},
        "productOptions": [
            {"name": "Size", "position": 1, "values": [{"name": spec["size_value"]}]},
            {"name": "Unit of Sale", "position": 2,
             "values": [{"name": "Ton"}, {"name": "50 LB Bag"}]},
        ],
        "variants": [
            {
                "optionValues": [
                    {"optionName": "Size", "name": spec["size_value"]},
                    {"optionName": "Unit of Sale", "name": "Ton"},
                ],
                "price": ton_price,
                "sku": f"{spec['original_sku']}-01",
                "taxable": True,
                "inventoryPolicy": "CONTINUE",
                "inventoryItem": {
                    "tracked": True,
                    "measurement": {"weight": {"value": ton_weight, "unit": "POUNDS"}},
                },
                "metafields": variant_mfs,
            },
            {
                "optionValues": [
                    {"optionName": "Size", "name": spec["size_value"]},
                    {"optionName": "Unit of Sale", "name": "50 LB Bag"},
                ],
                "price": "6.00",
                "sku": f"{spec['original_sku']}-02",
                "taxable": True,
                "inventoryPolicy": "CONTINUE",
                "inventoryItem": {
                    "tracked": True,
                    "measurement": {"weight": {"value": 50.0, "unit": "POUNDS"}},
                },
                "metafields": variant_mfs,
            },
        ],
        "metafields": product_mfs,
    }
    if product.get("category") and product["category"].get("id"):
        input_obj["category"] = product["category"]["id"]
    return input_obj


def restore_inventory(store_url, token, inv_item_id, qty_by_loc):
    if not qty_by_loc:
        print("    no inventory to restore"); return
    quantities = [
        {"inventoryItemId": inv_item_id, "locationId": loc, "quantity": qty}
        for loc, qty in qty_by_loc.items()
    ]
    r = gql(store_url, token, INVENTORY_SET_MUTATION,
            {"input": {"reason": "correction", "name": "on_hand",
                       "ignoreCompareQuantity": True, "quantities": quantities}})
    if "errors" in r: raise RuntimeError(f"invSet errors: {r['errors']}")
    p = r["data"]["inventorySetQuantities"]
    if p["userErrors"]:
        raise RuntimeError(f"invSet userErrors: {p['userErrors']}")
    print(f"    inventory restored: {qty_by_loc}")


def update_alts(store_url, token, alt_updates):
    if not alt_updates: return
    files = [{"id": gid, "alt": alt} for gid, alt in alt_updates.items()]
    r = gql(store_url, token, FILE_UPDATE_MUTATION, {"files": files})
    if "errors" in r: raise RuntimeError(f"fileUpdate errors: {r['errors']}")
    p = r["data"]["fileUpdate"]
    if p["userErrors"]:
        raise RuntimeError(f"fileUpdate userErrors: {p['userErrors']}")
    for f in p["files"]:
        print(f"    media {f['id']} alt={f['alt']!r}")


def process_one(store_url, token, spec, execute):
    print("=" * 72)
    print(f"[{spec['label']}]  {spec['product_gid']}")
    print("=" * 72)
    product = fetch_product(store_url, token, spec["product_gid"])

    # Safety checks
    if product["title"] != spec["expected_title"]:
        print(f"  ABORT: title mismatch  actual={product['title']!r} expected={spec['expected_title']!r}")
        return "abort-title"
    variants = product["variants"]["edges"]
    if len(variants) != 1:
        print(f"  ABORT: expected 1 variant, got {len(variants)}")
        return "abort-variant-count"
    cur_sku = variants[0]["node"]["sku"]
    if cur_sku != spec["original_sku"]:
        print(f"  ABORT: sku mismatch  actual={cur_sku!r} expected={spec['original_sku']!r}")
        return "abort-sku"
    cur_w = weight_lb(variants[0]["node"]["inventoryItem"]["measurement"]["weight"])
    if cur_w != spec["expected_weight_lb"]:
        print(f"  ABORT: weight mismatch  actual={cur_w} lb  expected={spec['expected_weight_lb']} lb (Ton convention)")
        return "abort-weight"
    if product["options"][0]["name"] != "Title":
        print(f"  ABORT: expected Title option, got {product['options']}")
        return "abort-options"

    inv_snapshot = get_inventory_snapshot(product)
    input_obj = build_input(product, spec)
    ton_price = product["variants"]["edges"][0]["node"]["price"]

    print(f"  Current: sku={cur_sku!r} price=${ton_price} weight={cur_w} lb inv={inv_snapshot}")
    print(f"  Plan: Size={spec['size_value']!r}, Ton -> {spec['original_sku']}-01 (${ton_price}, {cur_w} lb), 50 LB Bag -> {spec['original_sku']}-02 ($6.00, 50 lb), policy=CONTINUE")
    print(f"  SEO title: {spec['seo_title']} ({len(spec['seo_title'])} chars)")
    print(f"  SEO desc : {spec['seo_desc']} ({len(spec['seo_desc'])} chars)")
    if len(spec["seo_title"]) > 70:
        print(f"  WARN: SEO title {len(spec['seo_title'])} > 70")
    if len(spec["seo_desc"]) > 160:
        print(f"  WARN: SEO desc {len(spec['seo_desc'])} > 160")
    for gid, new_alt in spec.get("media_alt_updates", {}).items():
        curr = next((m["node"]["alt"] for m in product["media"]["edges"] if m["node"]["id"] == gid), "(media not found)")
        print(f"  Alt: {gid}\n       OLD: {curr!r}\n       NEW: {new_alt!r}")

    if not execute:
        return "dry-run"

    # Execute
    print("  [1/3] productSet ...")
    r = gql(store_url, token, PRODUCT_SET_MUTATION, {"input": input_obj, "synchronous": True})
    if "errors" in r: raise RuntimeError(f"productSet errors: {r['errors']}")
    p = r["data"]["productSet"]
    if p["userErrors"]:
        raise RuntimeError(f"productSet userErrors: {p['userErrors']}")
    ton_item_id = None
    for e in p["product"]["variants"]["edges"]:
        v = e["node"]
        so = {s["name"]: s["value"] for s in v["selectedOptions"]}
        print(f"    {v['sku']:<11}  Size={so.get('Size'):<7} UoS={so.get('Unit of Sale'):<10} ${v['price']} policy={v['inventoryPolicy']} variant={v['id']}")
        if so.get("Unit of Sale") == "Ton":
            ton_item_id = v["inventoryItem"]["id"]
    time.sleep(PACE_SECONDS)

    print("  [2/3] inventorySetQuantities ...")
    restore_inventory(store_url, token, ton_item_id, inv_snapshot)
    time.sleep(PACE_SECONDS)

    print("  [3/3] fileUpdate ...")
    update_alts(store_url, token, spec.get("media_alt_updates", {}))
    time.sleep(PACE_SECONDS)

    # Verify
    final = fetch_product(store_url, token, spec["product_gid"])
    print(f"  VERIFY options: {[(o['name'], o['position'], o['values']) for o in final['options']]}")
    for e in final["variants"]["edges"]:
        v = e["node"]
        so = {s["name"]: s["value"] for s in v["selectedOptions"]}
        inv = {}
        for le in v["inventoryItem"]["inventoryLevels"]["edges"]:
            ln = le["node"]
            qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
            inv[ln["location"]["name"]] = qs.get("on_hand", 0)
        w = v["inventoryItem"]["measurement"]["weight"] if v["inventoryItem"]["measurement"] else None
        mfs = [m["node"]["namespace"]+"."+m["node"]["key"] for m in v["metafields"]["edges"]]
        print(f"    {v['sku']:<11} Size={so.get('Size'):<7} UoS={so.get('Unit of Sale'):<10} ${v['price']} weight={w} policy={v['inventoryPolicy']} inv={inv} mfs={mfs}")
    print(f"  VERIFY SEO: title={final['seo']['title']!r}")
    print(f"  VERIFY URL: https://garoppos.com/products/{final['handle']}")
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    store_url, token = load_config()

    results = {}
    for i, spec in enumerate(PRODUCTS):
        try:
            status = process_one(store_url, token, spec, execute=args.execute)
            results[spec["label"]] = status
        except Exception as e:
            results[spec["label"]] = f"error: {e}"
            print(f"  ERROR: {e}")
        if i < len(PRODUCTS) - 1:
            time.sleep(INTER_PRODUCT_SECONDS)

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for label, status in results.items():
        print(f"  {label}: {status}")


if __name__ == "__main__":
    main()
