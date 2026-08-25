#!/usr/bin/env python3
"""Create 'Natural Fieldstone Slabs' with 2 variants.

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

DESCRIPTION_HTML = """<p>Add natural character to your landscape with Natural Fieldstone Slabs. These rugged, irregular slabs deliver the authentic look of quarried fieldstone for steps, outcroppings, retaining accents, and walkway features. Buy by the pallet for full projects or by the pound for individual pieces and accent work.</p>

<h3>Choose Your Unit of Sale</h3>
<ul>
  <li><strong>Per Pallet:</strong> A full pallet of natural fieldstone slabs (approx. 3,000 lbs) &mdash; ideal for steps, outcroppings, retaining features, and larger builds.</li>
  <li><strong>Per LB:</strong> Buy exactly the amount you need by weight &mdash; perfect for accent pieces, single steps, and topping off a project.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Natural fieldstone:</strong> Through-body color and texture that resists fading and weathering over time.</li>
  <li><strong>Slab format:</strong> Substantial thickness for structural applications and visual impact.</li>
  <li><strong>Irregular shapes:</strong> Natural edges and varied dimensions for organic, site-specific installations.</li>
  <li><strong>Mixed earth tones:</strong> Warm blend of greys, tans, and browns that complements any landscape.</li>
  <li><strong>Low maintenance:</strong> Rinse with a hose as needed &mdash; no sealing required for typical use.</li>
</ul>

<h3>Applications</h3>
<p>Build natural stone steps, bridge creek crossings, and create retaining features with authentic mass. Set as walkway landings, patio focal stones, or garden outcroppings. Stack for seat-height walls or place individually as stepping slabs through lawn and garden areas.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural fieldstone slabs</li>
  <li><strong>Finish:</strong> Natural split and weathered faces</li>
  <li><strong>Slab sizes:</strong> Irregular lengths, widths, and thicknesses (varies by piece)</li>
  <li><strong>Colors:</strong> Mixed earth tones &mdash; greys, tans, and browns with natural variation</li>
  <li><strong>Pallet weight:</strong> Approx. 3,000 lbs</li>
</ul>

<p>Handle with proper equipment &mdash; individual slabs can weigh several hundred pounds. Set on a compacted, level base and seat each piece securely. For steps, ensure full bearing contact and pitch slightly forward for drainage.</p>"""

PRODUCT_INPUT = {
    "title": "Natural Fieldstone Slabs",
    "handle": "natural-fieldstone-slabs",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Natural Stone", "Slabs"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Unit of Sale", "position": 1, "values": [{"name": "Per Pallet"}, {"name": "Per LB"}]},
    ],
    "metafields": [
        {"namespace": "custom", "key": "purchase_options", "type": "json",
         "value": json.dumps({"2": "Store Pickup", "3": "Local Delivery (within service area)"})},
        {"namespace": "custom", "key": "hide_online_price", "type": "boolean", "value": "true"},
    ],
    "variants": [
        {
            "optionValues": [
                {"optionName": "Unit of Sale", "name": "Per Pallet"},
            ],
            "price": "420.00",
            "sku": "38590",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "38590", "cost": "295.71",
                "measurement": {"weight": {"value": 3000.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 2}],
        },
        {
            "optionValues": [
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.20",
            "sku": "36781",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "36781", "cost": "0.10",
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
    log.info(f"Create Natural Fieldstone Slabs — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variants:")
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
