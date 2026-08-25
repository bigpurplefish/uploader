#!/usr/bin/env python3
"""Create new 'Retail Pack Wall Stone' product with 3 color variants.

Steps:
 1. Create product via productSet.
 2. Publish to Online Store and Point of Sale.

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

DESCRIPTION_HTML = """<p>Start a wall project without committing to a full pallet. Retail Pack Wall Stone delivers a manageable quarter-pallet of natural stone in three distinct colors, so you can build garden walls, raised beds, and accent features at a scale that fits your yard and your vehicle.</p>

<h3>Choose Your Color</h3>
<ul>
  <li><strong>Black Regency:</strong> Deep charcoal tones that anchor modern landscapes and contrast sharply with green plantings.</li>
  <li><strong>Dove Grey:</strong> Soft, neutral grey that blends with concrete, gravel, and existing stonework without competing for attention.</li>
  <li><strong>Emerald Grey:</strong> Cool grey-green hues that complement wooded settings and naturalized garden designs.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Quarter-pallet size:</strong> Approximately 500 lbs of stone &mdash; enough for small walls, borders, and accent projects without leftover waste.</li>
  <li><strong>Natural stone:</strong> Through-body color that resists fading, chipping, and weathering over time.</li>
  <li><strong>Irregular split faces:</strong> Rugged texture that stacks tightly and creates natural shadow lines.</li>
  <li><strong>Dry stack or mortar set:</strong> Build freestanding features quickly or bond permanently for added structural hold.</li>
  <li><strong>Low maintenance:</strong> Rinse with a hose as needed &mdash; no sealing required for typical use.</li>
</ul>

<h3>Applications</h3>
<p>Edge garden beds, frame walkways, build low seating walls, or create planter surrounds and fire pit bases. Use as facing stone on mailbox columns, step risers, or porch accents. Mix colors across projects or keep a consistent palette throughout the yard.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural wall stone</li>
  <li><strong>Thickness:</strong> 1&rdquo;&ndash;3&rdquo;</li>
  <li><strong>Finish:</strong> Natural split face with irregular edges</li>
  <li><strong>Pack size:</strong> 1/4 pallet (approx. 500 lbs)</li>
  <li><strong>Colors available:</strong> Black Regency, Dove Grey, Emerald Grey</li>
</ul>

<p>Prepare a compacted, level base and backfill behind retained sections with clean drainage stone. Stagger joints and batter the wall face slightly for stability. Sort pieces before setting to face the best sides forward.</p>"""

PRODUCT_INPUT = {
    "title": "Retail Pack Wall Stone",
    "handle": "retail-pack-wall-stone",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Stone"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Color", "position": 1, "values": [
            {"name": "Black Regency"}, {"name": "Dove Grey"}, {"name": "Emerald Grey"},
        ]},
        {"name": "Size", "position": 2, "values": [{"name": "1/4 Pallet"}]},
        {"name": "Unit of Sale", "position": 3, "values": [{"name": "Per 1/4 Pallet"}]},
    ],
    "metafields": [
        {"namespace": "custom", "key": "purchase_options", "type": "json",
         "value": json.dumps({"2": "Store Pickup", "3": "Local Delivery (within service area)"})},
        {"namespace": "custom", "key": "hide_online_price", "type": "boolean", "value": "true"},
    ],
    "variants": [
        {
            "optionValues": [
                {"optionName": "Color", "name": "Black Regency"},
                {"optionName": "Size", "name": "1/4 Pallet"},
                {"optionName": "Unit of Sale", "name": "Per 1/4 Pallet"},
            ],
            "price": "256.00",
            "sku": "37528",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "37528",
                "cost": "177.90",
                "measurement": {"weight": {"value": 500.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Color", "name": "Dove Grey"},
                {"optionName": "Size", "name": "1/4 Pallet"},
                {"optionName": "Unit of Sale", "name": "Per 1/4 Pallet"},
            ],
            "price": "256.00",
            "sku": "37525",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "37525",
                "cost": "177.90",
                "measurement": {"weight": {"value": 500.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Color", "name": "Emerald Grey"},
                {"optionName": "Size", "name": "1/4 Pallet"},
                {"optionName": "Unit of Sale", "name": "Per 1/4 Pallet"},
            ],
            "price": "215.00",
            "sku": "37526",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "37526",
                "cost": "162.59",
                "measurement": {"weight": {"value": 500.0, "unit": "POUNDS"}},
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
    log.info(f"Create Retail Pack Wall Stone — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   handle={PRODUCT_INPUT['handle']}  tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variants:")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<50} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<6} inv={qty}")
    print(f"2. Publish to Online Store + Point of Sale")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

    # 1. Create product
    log.info("Creating product via productSet...")
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

    # 2. Publish to Online Store + POS only
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
