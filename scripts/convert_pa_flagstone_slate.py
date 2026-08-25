#!/usr/bin/env python3
"""Convert single-variant 'Flagstone FC 18x36x1.5 Thermal' (SKU 41504) into
multi-variant 'PA Flagstone Full Color Slate' with 3 variants.

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
LOCATION_ID = "gid://shopify/Location/110377107748"
TAXONOMY_ID = "gid://shopify/TaxonomyCategory/bi-4-3"

PUB_ONLINE_STORE = "gid://shopify/Publication/286630838564"
PUB_POS = "gid://shopify/Publication/286630871332"

OLD_PRODUCT_ID = "gid://shopify/Product/10409593831716"

DESCRIPTION_HTML = """<p>Set a clean, modern surface with PA Flagstone Full Color Slate. These thermally finished pieces deliver a smooth, consistent texture with the rich earth tones of Pennsylvania full color stone. Buy individual pieces in three sizes to build patios, walkways, landings, and pool surrounds with precise, tight-joint installations.</p>

<h3>Choose Your Size</h3>
<ul>
  <li><strong>12&rdquo; &times; 24&rdquo; &times; 1 1/2&rdquo;:</strong> Compact pieces for borders, accent bands, and smaller patio areas.</li>
  <li><strong>18&rdquo; &times; 24&rdquo; &times; 1 1/2&rdquo;:</strong> Versatile mid-size pieces for walkways and mixed-pattern layouts.</li>
  <li><strong>18&rdquo; &times; 36&rdquo; &times; 1 1/2&rdquo;:</strong> Large-format pieces for broad patios, entry landings, and pool decks.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Thermal finish:</strong> Heat-treated surface provides a smooth, slip-resistant texture with clean edges.</li>
  <li><strong>Full color blend:</strong> Warm earth tones with natural veining that varies piece to piece.</li>
  <li><strong>1 1/2&rdquo; thickness:</strong> Suitable for dry-laid installations on compacted base or mortar-set over concrete.</li>
  <li><strong>Precision cut:</strong> Consistent dimensions for tight joints and clean geometric patterns.</li>
  <li><strong>Sold per piece:</strong> Buy exactly the quantity you need for your layout.</li>
</ul>

<h3>Applications</h3>
<p>Build formal patios, entry landings, and pool surrounds with a refined, contemporary look. Set walkways with uniform joints or combine sizes for running bond and basketweave patterns. Use for step treads, coping, and transitions between indoor and outdoor living spaces.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural Pennsylvania flagstone</li>
  <li><strong>Finish:</strong> Thermal (heat-treated smooth surface)</li>
  <li><strong>Thickness:</strong> 1 1/2&rdquo;</li>
  <li><strong>Colors:</strong> Full color blend &mdash; warm earth tones with natural variation</li>
  <li><strong>Sizes:</strong> 12&rdquo;&times;24&rdquo;, 18&rdquo;&times;24&rdquo;, 18&rdquo;&times;36&rdquo;</li>
</ul>

<p>Prepare a compacted, level base with proper drainage pitch. Set on a minimum 6&rdquo; compacted aggregate base for dry-laid installations, or bond with mortar over stable, cured concrete. Fill joints with polymeric sand. Consider a breathable sealer to enhance color and ease maintenance.</p>"""

PRODUCT_INPUT = {
    "title": "PA Flagstone Full Color Slate",
    "handle": "pa-flagstone-full-color-slate",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Natural Stone", "Slate"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Size", "position": 1, "values": [
            {"name": '12"x24"x1 1/2"'}, {"name": '18"x24"x1 1/2"'}, {"name": '18"x36"x1 1/2"'},
        ]},
        {"name": "Type", "position": 2, "values": [{"name": "Thermal"}]},
        {"name": "Unit of Sale", "position": 3, "values": [{"name": "Per Piece"}]},
    ],
    "metafields": [
        {"namespace": "custom", "key": "purchase_options", "type": "json",
         "value": json.dumps({"2": "Store Pickup", "3": "Local Delivery (within service area)"})},
        {"namespace": "custom", "key": "hide_online_price", "type": "boolean", "value": "true"},
    ],
    "variants": [
        {
            "optionValues": [
                {"optionName": "Size", "name": '12"x24"x1 1/2"'},
                {"optionName": "Type", "name": "Thermal"},
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "23.00",
            "sku": "41503",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "41503", "cost": "17.80",
                "measurement": {"weight": {"value": 41.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '18"x24"x1 1/2"'},
                {"optionName": "Type", "name": "Thermal"},
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "28.00",
            "sku": "41502",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "41502", "cost": "22.25",
                "measurement": {"weight": {"value": 62.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '18"x36"x1 1/2"'},
                {"optionName": "Type", "name": "Thermal"},
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "49.00",
            "sku": "41504",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "41504", "cost": "39.96",
                "measurement": {"weight": {"value": 93.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
    ],
}

PRODUCT_SET = """
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
  productSet(synchronous: $synchronous, input: $input) {
    product {
      id handle title
      variants(first: 10) { edges { node { id sku title price inventoryQuantity selectedOptions { name value } } } }
    }
    userErrors { field message }
  }
}
"""

PUBLISH_MUTATION = """
mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    userErrors { field message }
  }
}
"""

DELETE_MUTATION = """
mutation productDelete($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
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
    r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}}, headers=headers(cfg), timeout=90)
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        raise RuntimeError(f"GraphQL errors: {d['errors']}")
    return d["data"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Convert PA Flagstone Full Color Slate — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Delete old single-variant product:")
    print(f"     {OLD_PRODUCT_ID}  (Flagstone FC 18x36x1.5 Thermal, SKU 41504)")
    print(f"2. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variants:")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<55} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<6} inv={qty}")
    print(f"3. Publish to Online Store + Point of Sale")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

    log.info("Deleting old single-variant product...")
    dd = gql(cfg, DELETE_MUTATION, {"input": {"id": OLD_PRODUCT_ID}})
    ue = dd["productDelete"]["userErrors"]
    if ue:
        log.error(f"  delete errors: {ue}")
        return 1
    log.info(f"  OK deleted {dd['productDelete']['deletedProductId']}")
    time.sleep(1)

    log.info("Creating multi-variant product via productSet...")
    data = gql(cfg, PRODUCT_SET, {"synchronous": True, "input": PRODUCT_INPUT})
    ue = data["productSet"]["userErrors"]
    if ue:
        log.error(f"productSet userErrors: {ue}")
        return 1
    new_prod = data["productSet"]["product"]
    log.info(f"  OK  {new_prod['id']}  handle={new_prod['handle']}")
    for e in new_prod["variants"]["edges"]:
        v = e["node"]
        opts = " / ".join(f"{o['name']}={o['value']}" for o in v["selectedOptions"])
        log.info(f"    variant SKU={v['sku']} inv={v['inventoryQuantity']}  [{opts}]  ${v['price']}")

    log.info("Publishing to Online Store + Point of Sale...")
    pub_inputs = [{"publicationId": PUB_ONLINE_STORE}, {"publicationId": PUB_POS}]
    pd = gql(cfg, PUBLISH_MUTATION, {"id": new_prod["id"], "input": pub_inputs})
    if pd["publishablePublish"]["userErrors"]:
        log.error(f"publish errors: {pd['publishablePublish']['userErrors']}")
    else:
        log.info(f"  Published to 2 channels")

    print()
    print("=" * 70)
    print("COMPLETED")
    print(f"New product URL path: /products/{new_prod['handle']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
