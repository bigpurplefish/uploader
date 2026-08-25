#!/usr/bin/env python3
"""Create 'Snapped Blue Wallstone' with 2 variants.

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

DESCRIPTION_HTML = """<p>Build clean, structured walls with Snapped Blue Wallstone. These natural bluestone pieces feature snapped edges that create tight, uniform joints and a refined dry-stack or mortared look. The classic blue-grey tones bring a timeless quality to garden walls, retaining features, and architectural accents. Buy by the pallet for full projects or by the pound for repairs and accent work.</p>

<h3>Choose Your Unit of Sale</h3>
<ul>
  <li><strong>Per Pallet:</strong> A full pallet of 2&rdquo;&ndash;4&rdquo; snapped blue wallstone &mdash; ideal for garden walls, retaining features, raised beds, and larger builds.</li>
  <li><strong>Per LB:</strong> Buy exactly the amount you need by weight &mdash; perfect for filling gaps, small repairs, accent pieces, and topping off a project.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Snapped edges:</strong> Clean, angular breaks that stack tightly and create uniform coursing.</li>
  <li><strong>Natural bluestone:</strong> Through-body blue-grey color that resists fading and weathers gracefully.</li>
  <li><strong>2&rdquo;&ndash;4&rdquo; thickness:</strong> Select pieces that stack neatly and reduce shimming.</li>
  <li><strong>Dry stack or mortar set:</strong> Build freestanding features quickly or bond permanently for added hold.</li>
  <li><strong>Low maintenance:</strong> Hose off debris; no sealing required for typical use.</li>
</ul>

<h3>Applications</h3>
<p>Build garden walls, raised planting beds, step risers, and low retaining features with clean lines and a professional finish. Use as facing stone on columns, mailbox bases, and outdoor kitchen surrounds. The snapped edges create a more structured appearance than irregular wallstone while retaining natural stone character.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural bluestone</li>
  <li><strong>Thickness:</strong> 2&rdquo;&ndash;4&rdquo;</li>
  <li><strong>Finish:</strong> Snapped edges with natural cleft face</li>
  <li><strong>Color:</strong> Classic blue-grey</li>
  <li><strong>Piece sizes:</strong> Varied lengths and heights for coursed or random pattern</li>
  <li><strong>Pallet weight:</strong> Approx. 3,000 lbs</li>
</ul>

<p>Prepare a compacted, level base and include drainage behind any retained soil. Stagger joints, batter the face slightly for stability, and consult local guidelines for walls over 3 feet. Expect natural variation in size, shape, and tone between pieces.</p>"""

PRODUCT_INPUT = {
    "title": "Snapped Blue Wallstone",
    "handle": "snapped-blue-wallstone",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Natural Stone", "Wall Stone"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Size", "position": 1, "values": [{"name": '2"-4"'}]},
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
                {"optionName": "Size", "name": '2"-4"'},
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "399.99",
            "sku": "47713",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "47713", "cost": "269.38",
                "measurement": {"weight": {"value": 3000.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '2"-4"'},
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.25",
            "sku": "47714",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "47714", "cost": "0.10",
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
    log.info(f"Create Snapped Blue Wallstone — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   tags={PRODUCT_INPUT['tags']}")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<30} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<8} inv={qty}")
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
