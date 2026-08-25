#!/usr/bin/env python3
"""Create 'Autumn Silver Stepping Stones' with 1 variant.

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

DESCRIPTION_HTML = """<p>Add natural charm to your garden paths and yard transitions with Autumn Silver Stepping Stones. These irregular natural stone pieces feature soft silver-grey tones with subtle warm highlights, creating an inviting path that looks like it has always belonged in your landscape.</p>

<h3>Key Features</h3>
<ul>
  <li><strong>Natural stone:</strong> Through-body color that resists fading and stands up to weather year after year.</li>
  <li><strong>Autumn Silver tones:</strong> Cool silver-grey with warm undertones that complement plantings and mulch beds.</li>
  <li><strong>Irregular shapes:</strong> Each piece is unique, creating organic, natural-looking pathways.</li>
  <li><strong>Natural cleft surface:</strong> Textured finish provides traction underfoot in wet and dry conditions.</li>
  <li><strong>Sold per piece:</strong> Buy exactly the number of stones your path requires.</li>
</ul>

<h3>Applications</h3>
<p>Set stepping-stone paths through gardens, lawn areas, and between outdoor living spaces. Use as accent pavers in gravel beds, ground cover plantings, or along the edges of patios. Place through mulch beds to create low-maintenance walkways that blend with the surrounding landscape.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural flagstone</li>
  <li><strong>Finish:</strong> Natural cleft surface</li>
  <li><strong>Dimensions:</strong> Irregular; sizes vary piece to piece</li>
  <li><strong>Color:</strong> Autumn Silver &mdash; silver-grey with warm highlights</li>
  <li><strong>Approximate weight:</strong> 35 lbs per piece (varies by size)</li>
</ul>

<p>Set each stone on a compacted sand or gravel bed, pitched slightly for drainage. Space stones at a comfortable stride length (typically 24&ndash;30&rdquo; center to center). Fill gaps with ground cover, gravel, or polymeric sand for a finished look.</p>"""

PRODUCT_INPUT = {
    "title": "Autumn Silver Stepping Stones",
    "handle": "autumn-silver-stepping-stones",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Natural Stone", "Natural Stepping Stones"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Unit of Sale", "position": 1, "values": [{"name": "Per Piece"}]},
    ],
    "metafields": [
        {"namespace": "custom", "key": "purchase_options", "type": "json",
         "value": json.dumps({"2": "Store Pickup", "3": "Local Delivery (within service area)"})},
        {"namespace": "custom", "key": "hide_online_price", "type": "boolean", "value": "true"},
    ],
    "variants": [
        {
            "optionValues": [
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "23.50",
            "sku": "36958",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "36958", "cost": "15.04",
                "measurement": {"weight": {"value": 35.0, "unit": "POUNDS"}},
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
    log.info(f"Create Autumn Silver Stepping Stones — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variant:")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<30} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<6} inv={qty}")
    print(f"2. Publish to Online Store + Point of Sale")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

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
