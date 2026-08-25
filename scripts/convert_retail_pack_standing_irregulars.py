#!/usr/bin/env python3
"""Convert single-variant 'Flagstone Irregular Lilac Reta' (SKU 40971) into
multi-variant 'Retail Pack Standing Irregulars' with 6 variants.

Steps:
 1. Delete old single-variant product.
 2. Create new product with 6 variants via productSet.
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

OLD_PRODUCT_ID = "gid://shopify/Product/10409590292772"  # Flagstone Irregular Lilac Reta (SKU 40971)

DESCRIPTION_HTML = """<p>Take on smaller flagstone projects without committing to a full pallet. Retail Pack Standing Irregulars delivers a manageable pack of natural Pennsylvania flagstone in three color options, so you can build patios, walkways, and accent features at a scale that fits your project. Buy by the pallet pack for larger areas or by the pound for fill pieces and repairs.</p>

<h3>Choose Your Color</h3>
<ul>
  <li><strong>Chocolate Grey:</strong> Rich blend of dark brown and grey tones that complements both modern and traditional landscapes.</li>
  <li><strong>Lilac:</strong> Soft purple-grey hues with warm undertones that add character to garden paths and patios.</li>
  <li><strong>PA Flagstone Full Color:</strong> Classic Pennsylvania blend of warm earth tones with natural veining and color variation.</li>
</ul>

<h3>Choose Your Unit of Sale</h3>
<ul>
  <li><strong>Per Pallet:</strong> A retail-size pallet of standing irregular flagstone &mdash; sized for patios, walkways, and medium-scale projects.</li>
  <li><strong>Per LB:</strong> Buy exactly the amount you need by weight &mdash; perfect for filling gaps, small repairs, and accent pieces.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Retail-size pallet:</strong> Manageable quantity for residential projects without excess material.</li>
  <li><strong>Natural stone:</strong> Through-body color that resists fading and weathering over time.</li>
  <li><strong>Irregular shapes:</strong> Create organic curves and patterns with fewer straight cuts.</li>
  <li><strong>Natural cleft texture:</strong> Add traction that helps reduce slips when surfaces are wet.</li>
  <li><strong>Standing orientation:</strong> Pieces ship upright on pallet for easy selection and handling.</li>
</ul>

<h3>Applications</h3>
<p>Build patios, garden walkways, stepping-stone paths, and entry landings that blend naturally into the landscape. Set pieces on a compacted base for dry-laid installations or mortar-set on existing concrete for overlays. Mix colors across projects or keep a consistent palette throughout the yard.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural Pennsylvania flagstone</li>
  <li><strong>Finish:</strong> Natural cleft surface with split edges</li>
  <li><strong>Piece sizes:</strong> Standing irregulars; lengths, widths, and thicknesses vary</li>
  <li><strong>Colors:</strong> Chocolate Grey, Lilac, PA Flagstone Full Color</li>
  <li><strong>Pack weight:</strong> Approx. 500 lbs per retail pallet</li>
</ul>

<p>Plan a stable base, pitch surfaces for drainage, and keep joint widths consistent. Fill joints with polymeric sand or fine gravel. Sort pieces before setting to face the best sides forward and achieve even spacing.</p>"""

PRODUCT_INPUT = {
    "title": "Retail Pack Standing Irregulars",
    "handle": "retail-pack-standing-irregulars",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Stone"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Color", "position": 1, "values": [
            {"name": "Chocolate Grey"}, {"name": "Lilac"}, {"name": "PA Flagstone Full Color"},
        ]},
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
                {"optionName": "Color", "name": "Chocolate Grey"},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "256.00",
            "sku": "37527",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "37527",
                "cost": "177.90",
                "measurement": {"weight": {"value": 500.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Color", "name": "Chocolate Grey"},
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
        {
            "optionValues": [
                {"optionName": "Color", "name": "Lilac"},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "350.00",
            "sku": "40971",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "40971",
                "cost": "186.31",
                "measurement": {"weight": {"value": 500.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 1}],
        },
        {
            "optionValues": [
                {"optionName": "Color", "name": "Lilac"},
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.24",
            "sku": "40972",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "40972",
                "cost": "0.16",
                "measurement": {"weight": {"value": 1.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Color", "name": "PA Flagstone Full Color"},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "350.00",
            "sku": "39837",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "39837",
                "cost": "212.83",
                "measurement": {"weight": {"value": 500.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Color", "name": "PA Flagstone Full Color"},
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.54",
            "sku": "40452-FC",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "40452-FC",
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
    log.info(f"Convert Retail Pack Standing Irregulars — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Delete old single-variant product:")
    print(f"     {OLD_PRODUCT_ID}  (Flagstone Irregular Lilac Reta, SKU 40971)")
    print(f"2. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   handle={PRODUCT_INPUT['handle']}  tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variants (in order):")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<10} {opts:<50} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<6} inv={qty}")
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
