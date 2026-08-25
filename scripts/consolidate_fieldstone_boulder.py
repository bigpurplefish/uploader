#!/usr/bin/env python3
"""Consolidate two LNDS Boulder Fieldstone products into one 'Fieldstone Boulder' with 3 variants.

Steps:
 1. Create new 'Fieldstone Boulder' product (vendor=Everlast) with 3 variants via productSet.
 2. Publish to all sales channels.
 3. Delete the 2 legacy products.

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

OLD_PRODUCT_IDS = [
    "gid://shopify/Product/10409586196772",  # LNDS Boulder Fieldstone 2 Per (SKU 39859)
    "gid://shopify/Product/10409577251108",  # LNDS Boulder Fieldstone 1 Per (SKU 37529)
]

DESCRIPTION_HTML = """<p>Anchor your landscape with natural fieldstone boulders that deliver instant structure, weathered texture, and long-term stability. Place these rugged stones to frame entries, build retaining accents, terrace slopes, or create focal points that look like they've always belonged on your property.</p>

<h3>Choose Your Unit of Sale</h3>
<ul>
  <li><strong>Per Pallet (2 stones):</strong> Buy two boulders together on a single pallet &mdash; ideal for larger projects, wall bases, or matched pairs at driveway entries.</li>
  <li><strong>Per Stone (from a 2-stone pallet):</strong> Buy a single boulder drawn from the 2-per-pallet stock &mdash; perfect when you need one more piece to finish a layout.</li>
  <li><strong>Per Pallet (1 stone):</strong> Buy a single, larger boulder delivered on its own pallet &mdash; for statement pieces and large anchor stones.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Natural stone mass:</strong> Add real weight and stability for walls, borders, and outcrops.</li>
  <li><strong>Weathered faces:</strong> Showcase organic texture that blends into surrounding terrain.</li>
  <li><strong>Durable in all climates:</strong> Stand up to freeze&ndash;thaw cycles and heavy use.</li>
  <li><strong>Varied shapes:</strong> Fit stones together for tight joints and a cleaner finished look.</li>
  <li><strong>Low maintenance:</strong> Keep color and character with simple rinsing as needed.</li>
</ul>

<h3>Applications</h3>
<p>Define patios, walkways, and drive entrances with bold, natural edges. Build seat-height outcrops, garden berms, or dry-stack retaining features. Create focal pieces for water features and planting beds. Set a single statement stone near entries, anchor water features, or stack select pieces for steps and casual seating.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural fieldstone boulders</li>
  <li><strong>Dimensions:</strong> Varies by stone; select on site for size and shape</li>
  <li><strong>Finish:</strong> Naturally weathered faces; fractured and split edges</li>
  <li><strong>Colors:</strong> Mixed earth tones including gray, tan, brown, and rust</li>
</ul>

<p>Plan handling with proper equipment and a compacted base to seat each stone securely. Set courses with stable contact points and backfill well for drainage. Rinse occasionally to remove dust and keep surfaces looking clean.</p>"""

PRODUCT_INPUT = {
    "title": "Fieldstone Boulder",
    "handle": "fieldstone-boulder",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Stone"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Size", "position": 1, "values": [{"name": "2 Per Pallet"}, {"name": "1 Per Pallet"}]},
        {"name": "Unit of Sale", "position": 2, "values": [{"name": "Per Pallet"}, {"name": "Per Stone"}]},
    ],
    "metafields": [
        {"namespace": "custom", "key": "purchase_options", "type": "json",
         "value": json.dumps({"2": "Store Pickup", "3": "Local Delivery (within service area)"})},
    ],
    "variants": [
        {
            "optionValues": [
                {"optionName": "Size", "name": "2 Per Pallet"},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "420.00",
            "sku": "39859",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "39859",
                "cost": "114.00",
                "measurement": {"weight": {"value": 1200.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 3}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": "2 Per Pallet"},
                {"optionName": "Unit of Sale", "name": "Per Stone"},
            ],
            "price": "220.00",
            "sku": "36955",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "36955",
                "cost": "114.00",
                "measurement": {"weight": {"value": 400.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": "1 Per Pallet"},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "402.60",
            "sku": "37529",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "37529",
                "cost": "283.29",
                "measurement": {"weight": {"value": 400.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 14}],
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

PUBLICATIONS_QUERY = "{ publications(first: 20) { edges { node { id name } } } }"

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
    log.info(f"Consolidate Fieldstone Boulder — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   handle={PRODUCT_INPUT['handle']}  category=Raw Structural Components")
    print(f"   3 variants:")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<35} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<6} inv={qty}")
    print(f"2. Publish new product to all sales channels")
    print(f"3. Delete old products:")
    for pid in OLD_PRODUCT_IDS:
        print(f"     {pid}")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

    # 1. Create
    log.info("Creating consolidated product via productSet...")
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

    # 2. Publish
    log.info("Publishing to all sales channels...")
    pubs = gql(cfg, PUBLICATIONS_QUERY)["publications"]["edges"]
    pub_inputs = [{"publicationId": e["node"]["id"]} for e in pubs]
    pd = gql(cfg, PUBLISH_MUTATION, {"id": new_prod["id"], "input": pub_inputs})
    if pd["publishablePublish"]["userErrors"]:
        log.error(f"publish errors: {pd['publishablePublish']['userErrors']}")
    else:
        log.info(f"  Published to {len(pub_inputs)} channels")

    # 3. Delete old products
    log.info("Deleting old products...")
    for pid in OLD_PRODUCT_IDS:
        dd = gql(cfg, DELETE_MUTATION, {"input": {"id": pid}})
        ue = dd["productDelete"]["userErrors"]
        if ue:
            log.error(f"  delete errors for {pid}: {ue}")
        else:
            log.info(f"  OK deleted {dd['productDelete']['deletedProductId']}")
        time.sleep(0.5)

    print()
    print("=" * 70)
    print("COMPLETED")
    print(f"New product URL path: /products/{new_prod['handle']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
