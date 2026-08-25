#!/usr/bin/env python3
"""Convert single-variant 'Flagstone Irregular Lilac 1-1/' (SKU 36775) into
multi-variant 'PA Flagstone Full Color Standing Irregulars' with 4 variants.

Steps:
 1. Delete old single-variant product.
 2. Create new product with 4 variants via productSet.
 3. Publish to Online Store and Point of Sale.

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
TAXONOMY_ID = "gid://shopify/TaxonomyCategory/bi-4-3"  # Raw Structural Components

PUB_ONLINE_STORE = "gid://shopify/Publication/286630838564"
PUB_POS = "gid://shopify/Publication/286630871332"

OLD_PRODUCT_ID = "gid://shopify/Product/10409575153956"  # Flagstone Irregular Lilac 1-1/ (SKU 36775)

DESCRIPTION_HTML = """<p>Build natural-looking patios, walkways, and landings with PA Flagstone Full Color Standing Irregulars. Fit together irregular shapes like a custom mosaic and gain the rugged look of real Pennsylvania stone with surfaces that grip underfoot and stand up to the seasons. Buy by the pallet for full projects or by the pound for repairs and fill pieces.</p>

<h3>Choose Your Size</h3>
<ul>
  <li><strong>1&rdquo;:</strong> Thinner profile for overlays on existing concrete, stepping-stone paths, and areas where minimal excavation is preferred.</li>
  <li><strong>1 1/2&rdquo;:</strong> Heavier profile for dry-laid patios, walkways on compacted base, and areas that need added durability under regular foot traffic.</li>
</ul>

<h3>Choose Your Unit of Sale</h3>
<ul>
  <li><strong>Per Pallet:</strong> A full pallet of standing irregular flagstone &mdash; ideal for patios, walkways, and larger projects.</li>
  <li><strong>Per LB:</strong> Buy exactly the amount you need by weight &mdash; perfect for filling gaps, small repairs, and accent pieces.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Natural stone:</strong> Bring authentic color and character to outdoor living areas.</li>
  <li><strong>Full color blend:</strong> Rich mix of warm earth tones with natural veining and variation.</li>
  <li><strong>Irregular shapes:</strong> Create organic curves and fewer straight cuts for faster layout.</li>
  <li><strong>Natural cleft texture:</strong> Add traction that helps reduce slips when surfaces are wet.</li>
  <li><strong>Weather-ready durability:</strong> Handle foot traffic and changing climates with proper base.</li>
</ul>

<h3>Applications</h3>
<p>Lay inviting patios, garden walkways, and stepping-stone paths that blend into the landscape. Use 1&rdquo; stone for mortar-set overlays on concrete or lightweight paths. Choose 1 1/2&rdquo; for dry-laid patios on compacted base where added mass improves stability.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural Pennsylvania flagstone</li>
  <li><strong>Thicknesses:</strong> 1&rdquo; and 1 1/2&rdquo;</li>
  <li><strong>Finish:</strong> Natural cleft surface with split edges</li>
  <li><strong>Colors:</strong> Full color blend &mdash; warm earth tones with natural variation</li>
  <li><strong>Piece sizes:</strong> Standing irregulars; lengths and widths vary</li>
  <li><strong>Pallet weight:</strong> Approx. 2,000 lbs (1&rdquo;) / 3,200 lbs (1 1/2&rdquo;)</li>
</ul>

<p>Plan a stable base, pitch surfaces for drainage, and keep joint widths consistent. Fill joints with polymeric sand or fine gravel, and consider sealing to aid cleanup and highlight the stone&rsquo;s natural tones.</p>"""

PRODUCT_INPUT = {
    "title": "PA Flagstone Full Color Standing Irregulars",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Stone"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Size", "position": 1, "values": [{"name": '1"'}, {"name": '1 1/2"'}]},
        {"name": "Unit of Sale", "position": 2, "values": [{"name": "Per Pallet"}, {"name": "Per LB"}]},
    ],
    "metafields": [
        {"namespace": "custom", "key": "purchase_options", "type": "json",
         "value": json.dumps({"2": "Store Pickup", "3": "Local Delivery (within service area)"})},
        {"namespace": "custom", "key": "hide_online_price", "type": "boolean", "value": "true"},
    ],
    "variants": [
        {
            "optionValues": [
                {"optionName": "Size", "name": '1"'},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "575.00",
            "sku": "40370",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "40370",
                "cost": "404.24",
                "measurement": {"weight": {"value": 2000.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '1"'},
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.24",
            "sku": "40372",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "40372",
                "cost": "0.13",
                "measurement": {"weight": {"value": 1.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '1 1/2"'},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "750.00",
            "sku": "36775",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "36775",
                "cost": "538.50",
                "measurement": {"weight": {"value": 3200.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 2}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '1 1/2"'},
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.54",
            "sku": "40452",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "40452",
                "cost": "0.27",
                "measurement": {"weight": {"value": 1.0, "unit": "POUNDS"}},
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
    log.info(f"Convert PA Flagstone (Lilac) — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Delete old single-variant product:")
    print(f"     {OLD_PRODUCT_ID}  (Flagstone Irregular Lilac 1-1/, SKU 36775)")
    print(f"2. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variants (in order):")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<35} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<8} inv={qty}")
    print(f"3. Publish to Online Store + Point of Sale")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

    # 1. Delete old product
    log.info("Deleting old single-variant product...")
    dd = gql(cfg, DELETE_MUTATION, {"input": {"id": OLD_PRODUCT_ID}})
    ue = dd["productDelete"]["userErrors"]
    if ue:
        log.error(f"  delete errors: {ue}")
        return 1
    log.info(f"  OK deleted {dd['productDelete']['deletedProductId']}")
    time.sleep(1)

    # 2. Create new multi-variant product
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

    # 3. Publish to Online Store + POS only
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
