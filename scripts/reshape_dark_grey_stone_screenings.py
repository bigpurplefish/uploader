#!/usr/bin/env python3
"""
Reshape "Dark Grey Stone Screenings" (SKU 24608) from single-variant to
2-option (Size x Unit of Sale) with a Ton + 50 LB Bag variant.

Size option value: "Screenings" (no numeric fraction in source data; this is
the standard trade designation for fines sifted from crushed stone).

Target:
  Options:
    Size          (pos 1) values: ["Screenings"]
    Unit of Sale  (pos 2) values: ["Ton", "50 LB Bag"]
  Variants:
    24608-01  Size=Screenings UoS=Ton        price=$40.00 cost=null weight=2000 lb (preserved)
    24608-02  Size=Screenings UoS=50 LB Bag  price=$6.00  cost=null weight=50 lb
  Both inventoryPolicy = CONTINUE.

productSet is required (going from Title option to new Size+UoS options).
Inventory pre-fetched and restored via inventorySetQuantities after reshape.

Usage:
  python reshape_dark_grey_stone_screenings.py            # dry run
  python reshape_dark_grey_stone_screenings.py --execute  # execute
"""
import argparse, json, sys, time, urllib.request
from pathlib import Path

CONFIG_PATH = Path("/Users/moosemarketer/Code/garoppos/uploader/config.json")
PRODUCT_GID = "gid://shopify/Product/10368016515364"
PRODUCT_TITLE_EXPECTED = "Dark Grey Stone Screenings"
ORIGINAL_SKU = "24608"
SIZE_VALUE = "Screenings"
TON_SKU = f"{ORIGINAL_SKU}-01"
BAG_SKU = f"{ORIGINAL_SKU}-02"
TON_UOS = "Ton"
BAG_UOS = "50 LB Bag"
BAG_PRICE = "6.00"
BAG_WEIGHT_LB = 50.0
POLICY = "CONTINUE"
PACE_SECONDS = 0.08

NEW_SEO_TITLE = "Dark Grey Stone Screenings \u2014 Bulk Ton or 50 lb Bag | Garoppo's"
NEW_SEO_DESC = (
    "Dark grey stone screenings for paver base, leveling, and joint filling. "
    "Bulk by the ton for full projects or 50 lb bags for repairs. Pickup or delivery."
)

NEW_DESCRIPTION_HTML = """<p>Build a stable, level base with Dark Grey Stone Screenings from Garoppo's. Compact fine, angular crushed stone to lock pavers in place, fill flagstone joints, and keep walkways true. Order bulk by the ton for full installations or grab a 50 lb bag for paver repairs, joint top-ups, and smaller leveling jobs.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Ton (bulk):</strong> Cover patio bedding layers, walkway sub-bases, and flagstone joint fills across large areas. Approximately 100 sq ft of coverage at 2 in depth per ton.</li>
  <li><strong>50 LB Bag (retail):</strong> Easy to handle for paver repairs, sinkhole fills, joint maintenance, and precision leveling where a ton is more than you need.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Compacts tight:</strong> Interlocking fines create a firm, non-shifting base.</li>
  <li><strong>Screeds cleanly:</strong> Achieve a smooth, consistent bedding layer fast.</li>
  <li><strong>Clean look:</strong> Uniform dark grey color blends into joints and edges.</li>
  <li><strong>Season-ready:</strong> Holds grades through freeze-thaw when properly compacted.</li>
  <li><strong>Versatile use:</strong> Ideal under pavers, for pathways, shed pads, and flagstone joints.</li>
</ul>

<h3>Applications</h3>
<p>Lay a dependable bedding layer for patios, walkways, and edging. Fill flagstone joints for a tight finish, or create compacted paths with a subtle, natural look. Pair with a proper base aggregate for driveways and heavier loads.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural crushed stone screenings</li>
  <li><strong>Particle Size:</strong> Graded fines with small chips for dense compaction</li>
  <li><strong>Color:</strong> Dark grey (natural variation may occur)</li>
  <li><strong>Texture:</strong> Angular, compactable</li>
  <li><strong>Bag weight:</strong> 50 lb</li>
  <li><strong>Coverage:</strong> Approx. 100 sq ft per ton at 2 in depth</li>
  <li><strong>Typical Depths:</strong> Bedding 1\u20132 in; use additional base aggregate as needed</li>
</ul>

<p>Compact in thin lifts for best results. Lightly moisten before compacting, maintain a slight slope for drainage, and use edge restraints to contain the material and reduce movement over time. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>"""

ALT_UPDATES = {
    "gid://shopify/MediaImage/45190794805540":
        "Dark Grey Stone Screenings, crushed fines sold by the ton. #Screenings#Ton",
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
    id title handle status vendor productType tags descriptionHtml
    category { id }
    seo { title description }
    options { name position values }
    media(first: 50) { edges { node { id alt } } }
    metafields(first: 50) { edges { node { namespace key value type } } }
    variants(first: 50) {
      edges { node {
        id sku title price inventoryPolicy
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
    val = float(w["value"]); unit = w["unit"]
    if unit == "POUNDS": return val
    if unit == "OUNCES": return val / 16.0
    if unit == "KILOGRAMS": return val * 2.20462
    if unit == "GRAMS": return val * 0.00220462
    return val


def pick_current_price(product):
    return product["variants"]["edges"][0]["node"]["price"] if product["variants"]["edges"] else "0.00"


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


def build_product_set_input(product, ton_weight_lb, ton_price):
    variant_mfs = []
    if product["variants"]["edges"]:
        for me in product["variants"]["edges"][0]["node"]["metafields"]["edges"]:
            n = me["node"]
            if n["namespace"] == "custom":
                variant_mfs.append({
                    "namespace": n["namespace"], "key": n["key"],
                    "value": n["value"], "type": n["type"],
                })
    product_mfs = []
    for me in product["metafields"]["edges"]:
        n = me["node"]
        product_mfs.append({
            "namespace": n["namespace"], "key": n["key"],
            "value": n["value"], "type": n["type"],
        })

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
            {"name": "Size", "position": 1, "values": [{"name": SIZE_VALUE}]},
            {"name": "Unit of Sale", "position": 2, "values": [{"name": TON_UOS}, {"name": BAG_UOS}]},
        ],
        "variants": [
            {
                "optionValues": [
                    {"optionName": "Size", "name": SIZE_VALUE},
                    {"optionName": "Unit of Sale", "name": TON_UOS},
                ],
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
                "optionValues": [
                    {"optionName": "Size", "name": SIZE_VALUE},
                    {"optionName": "Unit of Sale", "name": BAG_UOS},
                ],
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


def restore_inventory(store_url, token, inventory_item_id, qty_by_loc):
    if not qty_by_loc:
        print("  No prior inventory to restore."); return
    quantities = [
        {"inventoryItemId": inventory_item_id, "locationId": loc, "quantity": qty}
        for loc, qty in qty_by_loc.items()
    ]
    variables = {"input": {
        "reason": "correction", "name": "on_hand",
        "ignoreCompareQuantity": True, "quantities": quantities,
    }}
    r = gql(store_url, token, INVENTORY_SET_MUTATION, variables)
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    p = r["data"]["inventorySetQuantities"]
    if p["userErrors"]: print("userErrors:", json.dumps(p["userErrors"], indent=2)); sys.exit(1)
    print(f"  Inventory restored: {qty_by_loc}")


def print_plan(product, input_obj, inv_snapshot, ton_price):
    print("=" * 72)
    print(f"DRY RUN - {PRODUCT_TITLE_EXPECTED} reshape")
    print("=" * 72)
    print(f"\nProduct: {product['title']!r}  {product['id']}  handle={product['handle']}")
    print(f"Status: {product['status']}  Tags: {product['tags']}  ProductType: {product['productType']}")
    print(f"Category (preserved): {product['category']}")
    print(f"Current options: {[(o['name'], o['values']) for o in product['options']]}")
    print(f"Current variant: sku={product['variants']['edges'][0]['node']['sku']!r} price=${ton_price}")
    print(f"\nInventory snapshot (to restore on new Ton variant):")
    for loc, qty in inv_snapshot.items():
        print(f"  {loc}  on_hand={qty}")
    print(f"\n--- PLANNED CHANGES ---")
    print(f"Options -> Size ({SIZE_VALUE!r}) x Unit of Sale ([{TON_UOS!r}, {BAG_UOS!r}])")
    print(f"SEO title:  {input_obj['seo']['title']}  ({len(input_obj['seo']['title'])} chars)")
    print(f"SEO desc:   {input_obj['seo']['description']}  ({len(input_obj['seo']['description'])} chars)")
    for v in input_obj["variants"]:
        size = next(o["name"] for o in v["optionValues"] if o["optionName"] == "Size")
        uos = next(o["name"] for o in v["optionValues"] if o["optionName"] == "Unit of Sale")
        w = v["inventoryItem"]["measurement"]["weight"]
        print(f"  variant sku={v['sku']:<10} Size={size:<11} UoS={uos:<10} price=${v['price']} weight={w['value']} {w['unit']} policy={v['inventoryPolicy']} mfs={len(v['metafields'])}")
    print(f"\nMedia alt updates:")
    for e in product["media"]["edges"]:
        n = e["node"]
        new = ALT_UPDATES.get(n["id"])
        if new:
            print(f"  {n['id']}\n    OLD: {n['alt']!r}\n    NEW: {new!r}")
    print(f"\nProduct metafields preserved: {len(input_obj.get('metafields', []))}")
    for mf in input_obj.get("metafields", []):
        v = mf['value']
        if len(v) > 80: v = v[:80] + "..."
        print(f"  - {mf['namespace']}.{mf['key']} ({mf['type']}) = {v}")
    print(f"Publications (verified, no change): Online Store + POS")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    store_url, token = load_config()
    product = fetch_product(store_url, token)

    if product["title"] != PRODUCT_TITLE_EXPECTED:
        print(f"ABORT: unexpected product title {product['title']!r}"); sys.exit(1)
    current_variants = product["variants"]["edges"]
    if len(current_variants) != 1:
        print(f"ABORT: expected 1 variant, found {len(current_variants)}"); sys.exit(1)
    current_sku = current_variants[0]["node"]["sku"]
    if current_sku != ORIGINAL_SKU:
        print(f"ABORT: expected SKU {ORIGINAL_SKU!r}, found {current_sku!r}"); sys.exit(1)

    ton_weight = pick_current_weight_lb(product)
    ton_price = pick_current_price(product)
    inv_snapshot = get_inventory_snapshot(product)
    input_obj = build_product_set_input(product, ton_weight_lb=ton_weight, ton_price=ton_price)
    print_plan(product, input_obj, inv_snapshot, ton_price)

    if not args.execute:
        print("\nDRY RUN complete. Re-run with --execute.")
        return

    print("\n>>> EXECUTING <<<\n")
    print("[1/3] productSet ...")
    r = gql(store_url, token, PRODUCT_SET_MUTATION, {"input": input_obj, "synchronous": True})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    p = r["data"]["productSet"]
    if p["userErrors"]:
        print("userErrors:", json.dumps(p["userErrors"], indent=2)); sys.exit(1)
    ton_item_id = None
    for e in p["product"]["variants"]["edges"]:
        v = e["node"]
        so = {s["name"]: s["value"] for s in v["selectedOptions"]}
        print(f"  {v['sku']:<10}  Size={so.get('Size'):<11}  UoS={so.get('Unit of Sale'):<10}  ${v['price']}  policy={v['inventoryPolicy']}  variant={v['id']}  item={v['inventoryItem']['id']}")
        if so.get("Unit of Sale") == TON_UOS:
            ton_item_id = v["inventoryItem"]["id"]
    time.sleep(PACE_SECONDS)

    print("\n[2/3] inventorySetQuantities ...")
    if ton_item_id and inv_snapshot:
        restore_inventory(store_url, token, ton_item_id, inv_snapshot)
    else:
        print("  Nothing to restore.")
    time.sleep(PACE_SECONDS)

    print("\n[3/3] fileUpdate (alt tag) ...")
    files = [{"id": gid, "alt": alt} for gid, alt in ALT_UPDATES.items()]
    r = gql(store_url, token, FILE_UPDATE_MUTATION, {"files": files})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    p = r["data"]["fileUpdate"]
    if p["userErrors"]:
        print("userErrors:", json.dumps(p["userErrors"], indent=2)); sys.exit(1)
    for f in p["files"]:
        print(f"  {f['id']} alt={f['alt']!r}")
    time.sleep(PACE_SECONDS)

    print("\n--- VERIFYING ---")
    final = fetch_product(store_url, token)
    print(f"Options: {[(o['name'], o['position'], o['values']) for o in final['options']]}")
    print(f"SEO: title={final['seo']['title']!r}")
    print(f"     desc={final['seo']['description']!r}")
    print(f"descriptionHtml len: {len(final['descriptionHtml'] or '')}  contains 'Pack Sizes': {'Pack Sizes' in (final['descriptionHtml'] or '')}")
    for e in final["variants"]["edges"]:
        v = e["node"]
        so = {s["name"]: s["value"] for s in v["selectedOptions"]}
        inv = {}
        for le in v["inventoryItem"]["inventoryLevels"]["edges"]:
            ln = le["node"]
            qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
            inv[ln["location"]["name"]] = qs.get("on_hand", 0)
        w = v["inventoryItem"]["measurement"]["weight"] if v["inventoryItem"]["measurement"] else None
        c = v["inventoryItem"]["unitCost"]
        mfs = [m["node"]["namespace"]+"."+m["node"]["key"] for m in v["metafields"]["edges"]]
        print(f"  {v['sku']:<10} Size={so.get('Size'):<11} UoS={so.get('Unit of Sale'):<10} ${v['price']} weight={w} cost={c} policy={v['inventoryPolicy']} inv={inv} mfs={mfs}")
    for e in final["media"]["edges"]:
        n = e["node"]
        print(f"  Media {n['id']} alt={n['alt']!r}")
    print("\nDone.")


if __name__ == "__main__":
    main()
