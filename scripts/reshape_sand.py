#!/usr/bin/env python3
"""
Reshape "Sand" (gid://shopify/Product/10368016285988): already 2-option
Color x Unit of Sale; add 50 LB Bag counterparts and normalize metadata.

Existing variants:
  24601 Concrete   Ton $24.00  2000 lb  inv 10
  24600 Yellow Bar Ton $23.00  2000 lb  inv 10
  24602 White Bar  Ton $35.00  2000 lb  inv 10

Target:
  Options: Color [Concrete, Yellow Bar, White Bar] x Unit of Sale [Ton, 50 LB Bag]
  Rename 3 existing variants' SKUs to *-01, flip policy to CONTINUE
  Create 3 new bag variants (*-02) at $6, null cost, 50 lb, CONTINUE, copy color_swatch_image mf
  Normalize 3 image alts to canonical `#<Color>#Ton`
  Set SEO + rewrite description with Pack Sizes section

Additive path - no productSet, no inventory destruction.

Usage:
  python reshape_sand.py            # dry run
  python reshape_sand.py --execute  # execute
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("/Users/moosemarketer/Code/garoppos/uploader/config.json")
PRODUCT_GID = "gid://shopify/Product/10368016285988"
PACE_SECONDS = 0.08
POLICY = "CONTINUE"
BAG_PRICE = "6.00"
BAG_WEIGHT_LB = 50.0

NEW_SEO_TITLE = "Sand \u2014 Concrete, Yellow Bar, White Bar | Ton or 50 lb Bag"
NEW_SEO_DESC = (
    "Concrete, Yellow Bar, and White Bar sand for masonry, concrete mixing, "
    "and paver bedding. Bulk by the ton or 50 lb bags. Pickup or delivery."
)

NEW_DESCRIPTION_HTML = """<p>Build a stable, level base, mix durable concrete, and set masonry work with sand that performs on every job. Choose Concrete, Yellow Bar, or White Bar from Garoppo's to match local specs, mortar mixes, or paver-setting requirements. Order bulk by the ton for full projects or grab a 50 lb bag for repairs, mortar batches, and smaller jobs.</p>

<h3>Pack Sizes</h3>
<ul>
  <li><strong>Per Ton (bulk):</strong> Cover paver bedding layers, concrete pours, masonry projects, and sand-set walkways at scale. Approximately 100 sq ft coverage at 2 in depth per ton.</li>
  <li><strong>50 LB Bag (retail):</strong> Easy to handle for mortar mixes, paver joint top-ups, sandbox fills, small concrete repairs, and winter ice traction.</li>
</ul>

<h3>Color Options</h3>
<ul>
  <li><strong>Concrete Sand:</strong> Washed, coarse sand meeting ASTM C-33 specs for general concrete work and as a paver bedding layer.</li>
  <li><strong>Yellow Bar Sand:</strong> Fine, natural masonry sand for mortar mixes, block work, and brick laying.</li>
  <li><strong>White Bar Sand:</strong> Clean, light-colored fine sand for premium masonry, lighter mortar joints, and visible decorative work.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Dependable base:</strong> Create flat, even bedding for pavers, slabs, and edging.</li>
  <li><strong>Concrete-ready:</strong> Mix Concrete sand with cement and aggregate per project specifications.</li>
  <li><strong>Clean finish:</strong> Achieve smooth screeding for faster setting and consistent results.</li>
  <li><strong>Color options:</strong> Match site conditions or aesthetics with three sand grades.</li>
  <li><strong>Reliable coverage:</strong> Estimate quantities quickly to keep crews moving.</li>
</ul>

<h3>Applications</h3>
<p>Use as bedding and leveling sand for patios, walkways, and hardscape borders. Fill joints where appropriate and top off settled areas during maintenance. Blend Concrete sand with cement for slabs and walls; use Yellow Bar or White Bar for mortar, block work, and tuck-pointing. Keep a bag on hand for winter ice traction and sandbox top-ups.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural sand aggregate</li>
  <li><strong>Texture:</strong> Granular; suitable for screeding, compaction, and mixing</li>
  <li><strong>Colors:</strong> Concrete, Yellow Bar, White Bar</li>
  <li><strong>Bag weight:</strong> 50 lb</li>
  <li><strong>Coverage:</strong> Approx. 100 sq ft at 2 in depth per ton</li>
</ul>

<p>Follow local codes and manufacturer instructions for base prep, bedding thickness, and mortar ratios. Compact sub-base first, then screed a uniform layer and set units promptly to maintain a true surface. Color and appearance may vary by source. Pick up in-store at 1200 Harding Hwy or arrange local delivery within our service area.</p>"""

# Normalized alt tags: keep the positional #<Color>#Ton pattern that already
# exists, just tidy wording for consistency with other aggregate reshapes.
ALT_UPDATES = {
    "gid://shopify/MediaImage/45190794576164":
        "Concrete sand for concrete mixing and paver bedding, sold by the ton. #Concrete#Ton",
    "gid://shopify/MediaImage/45190794608932":
        "Yellow Bar sand for masonry mortar and block work, sold by the ton. #Yellow Bar#Ton",
    "gid://shopify/MediaImage/45190794641700":
        "White Bar sand for premium masonry and decorative mortar, sold by the ton. #White Bar#Ton",
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
    id title handle status
    options { name position values }
    media(first:20){ edges { node { id alt } } }
    variants(first:50){ edges { node {
      id sku price inventoryPolicy
      selectedOptions { name value }
      inventoryItem {
        id measurement { weight { value unit } } unitCost { amount }
        inventoryLevels(first:10){ edges { node {
          location { name }
          quantities(names:["on_hand"]){ name quantity }
        } } }
      }
      metafields(first:10){ edges { node { namespace key value type } } }
    } } }
  }
}
"""

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

# productUpdate userErrors is UserError (no `code` field) unlike most mutations
PRODUCT_UPDATE_MUTATION = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id seo { title description } }
    userErrors { field message }
  }
}
"""


def fetch_product(store_url, token):
    d = gql(store_url, token, SNAPSHOT_QUERY, {"id": PRODUCT_GID})
    if "errors" in d: print("errors:", json.dumps(d["errors"], indent=2)); sys.exit(1)
    return d["data"]["product"]


def build_existing_updates(product):
    """Return list of ProductVariantsBulkInput for all existing variants."""
    updates = []
    for e in product["variants"]["edges"]:
        v = e["node"]
        updates.append({
            "id": v["id"],
            "inventoryPolicy": POLICY,
            "inventoryItem": {"sku": f"{v['sku']}-01"},
        })
    return updates


def build_bag_creates(product):
    """Return list of new bag ProductVariantsBulkInput (one per existing variant)."""
    creates = []
    for e in product["variants"]["edges"]:
        v = e["node"]
        color = next((s["value"] for s in v["selectedOptions"] if s["name"] == "Color"), None)
        if color is None: continue
        mfs = []
        for me in v["metafields"]["edges"]:
            n = me["node"]
            if n["namespace"] == "custom" and n["key"] == "color_swatch_image":
                mfs.append({"namespace": n["namespace"], "key": n["key"],
                            "value": n["value"], "type": n["type"]})
        creates.append({
            "optionValues": [
                {"optionName": "Color", "name": color},
                {"optionName": "Unit of Sale", "name": "50 LB Bag"},
            ],
            "price": BAG_PRICE,
            "taxable": True,
            "inventoryPolicy": POLICY,
            "inventoryItem": {
                "sku": f"{v['sku']}-02",
                "tracked": True,
                "measurement": {"weight": {"value": BAG_WEIGHT_LB, "unit": "POUNDS"}},
            },
            "metafields": mfs,
        })
    return creates


def print_plan(product, updates, creates):
    print("=" * 72)
    print("DRY RUN - Sand reshape (additive)")
    print("=" * 72)
    print(f"\nProduct: {product['title']!r}  {product['id']}  handle={product['handle']}  status={product['status']}")
    print(f"Options: {[(o['name'], o['position'], o['values']) for o in product['options']]}")
    print("\n--- Existing variants to update (SKU rename + policy=CONTINUE) ---")
    for upd in updates:
        orig = next(e["node"] for e in product["variants"]["edges"] if e["node"]["id"] == upd["id"])
        new_sku = upd["inventoryItem"]["sku"]
        print(f"  {orig['id']}  sku {orig['sku']!r} -> {new_sku!r}  policy {orig['inventoryPolicy']}->{upd['inventoryPolicy']}")
    print("\n--- New bag variants to create ---")
    for c in creates:
        color = next(o["name"] for o in c["optionValues"] if o["optionName"] == "Color")
        uos = next(o["name"] for o in c["optionValues"] if o["optionName"] == "Unit of Sale")
        print(f"  sku={c['inventoryItem']['sku']!r}  Color={color!r}  UoS={uos!r}  price=${c['price']}  weight=50 lb  policy={c['inventoryPolicy']}  mfs={len(c['metafields'])}")
    print("\n--- Media alt updates ---")
    for e in product["media"]["edges"]:
        n = e["node"]
        new_alt = ALT_UPDATES.get(n["id"])
        if new_alt:
            print(f"  {n['id']}")
            print(f"    OLD: {n['alt']!r}")
            print(f"    NEW: {new_alt!r}")
    print(f"\n--- SEO ---")
    print(f"  title: {NEW_SEO_TITLE}  ({len(NEW_SEO_TITLE)} chars)")
    print(f"  desc : {NEW_SEO_DESC}  ({len(NEW_SEO_DESC)} chars)")
    if len(NEW_SEO_TITLE) > 70: print("  WARN: SEO title > 70 chars")
    if len(NEW_SEO_DESC) > 160: print("  WARN: SEO desc > 160 chars")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    store_url, token = load_config()
    product = fetch_product(store_url, token)

    # Safety checks
    if product["title"] != "Sand":
        print(f"ABORT: unexpected title {product['title']!r}"); sys.exit(1)
    opt_names = [o["name"] for o in product["options"]]
    if opt_names != ["Color", "Unit of Sale"]:
        print(f"ABORT: unexpected option structure {opt_names}"); sys.exit(1)
    # Every variant should have weight 2000 lb
    for e in product["variants"]["edges"]:
        v = e["node"]
        w = v["inventoryItem"]["measurement"]["weight"]
        if not w or w["value"] != 2000.0 or w["unit"] != "POUNDS":
            print(f"ABORT: variant {v['sku']!r} weight is {w} (expected 2000 lb)"); sys.exit(1)

    updates = build_existing_updates(product)
    creates = build_bag_creates(product)
    print_plan(product, updates, creates)

    if not args.execute:
        print("\nDRY RUN. Re-run with --execute.")
        return

    print("\n>>> EXECUTING <<<\n")

    # [1/4] bulk update: rename + policy
    print("[1/4] productVariantsBulkUpdate ...")
    r = gql(store_url, token, BULK_UPDATE_MUTATION, {"productId": PRODUCT_GID, "variants": updates})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    pl = r["data"]["productVariantsBulkUpdate"]
    if pl["userErrors"]:
        print("userErrors:", json.dumps(pl["userErrors"], indent=2)); sys.exit(1)
    for pv in pl["productVariants"]:
        print(f"    updated: {pv['id']} sku={pv['sku']} policy={pv['inventoryPolicy']}")
    time.sleep(PACE_SECONDS)

    # [2/4] bulk create bags
    print("\n[2/4] productVariantsBulkCreate ...")
    r = gql(store_url, token, BULK_CREATE_MUTATION,
            {"productId": PRODUCT_GID, "variants": creates, "strategy": "REMOVE_STANDALONE_VARIANT"})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    pl = r["data"]["productVariantsBulkCreate"]
    if pl["userErrors"]:
        print("userErrors:", json.dumps(pl["userErrors"], indent=2)); sys.exit(1)
    for pv in pl["productVariants"]:
        so = {s["name"]: s["value"] for s in pv["selectedOptions"]}
        w = pv["inventoryItem"]["measurement"]["weight"]
        print(f"    created: {pv['id']} sku={pv['sku']} opts={so} ${pv['price']} policy={pv['inventoryPolicy']} weight={w}")
    if pl.get("product"):
        print(f"    UoS option values now: {[o['values'] for o in pl['product']['options'] if o['name']=='Unit of Sale']}")
    time.sleep(PACE_SECONDS)

    # [3/4] alt updates
    print("\n[3/4] fileUpdate (3 alts) ...")
    files = [{"id": gid, "alt": alt} for gid, alt in ALT_UPDATES.items()]
    r = gql(store_url, token, FILE_UPDATE_MUTATION, {"files": files})
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    pl = r["data"]["fileUpdate"]
    if pl["userErrors"]:
        print("userErrors:", json.dumps(pl["userErrors"], indent=2)); sys.exit(1)
    for f in pl["files"]:
        print(f"    {f['id']} alt={f['alt']!r}")
    time.sleep(PACE_SECONDS)

    # [4/4] productUpdate (SEO + description)
    print("\n[4/4] productUpdate (SEO + description) ...")
    r = gql(store_url, token, PRODUCT_UPDATE_MUTATION, {
        "input": {
            "id": PRODUCT_GID,
            "seo": {"title": NEW_SEO_TITLE, "description": NEW_SEO_DESC},
            "descriptionHtml": NEW_DESCRIPTION_HTML,
        }
    })
    if "errors" in r: print("errors:", json.dumps(r["errors"], indent=2)); sys.exit(1)
    pl = r["data"]["productUpdate"]
    if pl["userErrors"]:
        print("userErrors:", json.dumps(pl["userErrors"], indent=2)); sys.exit(1)
    print(f"    SEO set: {pl['product']['seo']}")
    time.sleep(PACE_SECONDS)

    # Verify
    print("\n--- VERIFYING ---")
    final = fetch_product(store_url, token)
    print(f"Options: {[(o['name'], o['position'], o['values']) for o in final['options']]}")
    print(f"Variants ({len(final['variants']['edges'])}):")
    for e in final["variants"]["edges"]:
        v = e["node"]
        so = {s["name"]: s["value"] for s in v["selectedOptions"]}
        inv = {}
        for le in v["inventoryItem"]["inventoryLevels"]["edges"]:
            ln = le["node"]
            qs = {q["name"]: q["quantity"] for q in ln["quantities"]}
            inv[ln["location"]["name"]] = qs.get("on_hand", 0)
        w = v["inventoryItem"]["measurement"]["weight"]
        mfs = [m["node"]["namespace"]+"."+m["node"]["key"] for m in v["metafields"]["edges"]]
        print(f"  {v['sku']:<10} Color={so.get('Color'):<10} UoS={so.get('Unit of Sale'):<10} ${v['price']} weight={w} policy={v['inventoryPolicy']} inv={inv} mfs={mfs}")
    print("\nMedia:")
    for e in final["media"]["edges"]:
        n = e["node"]
        print(f"  {n['id']} alt={n['alt']!r}")
    print("\nDone.")


if __name__ == "__main__":
    main()
