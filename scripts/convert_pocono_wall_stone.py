#!/usr/bin/env python3
"""Convert single-variant 'Wallstone Pocono Blend Thin' (SKU 36945) into
multi-variant 'Pocono Blend Wall Stone' with 2 variants.

Steps:
 1. Delete old single-variant product (gid://shopify/Product/10409575678244).
 2. Create new 'Pocono Blend Wall Stone' with 2 variants via productSet.
 3. Publish to all sales channels.

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

OLD_PRODUCT_ID = "gid://shopify/Product/10409575678244"  # Wallstone Pocono Blend Thin (SKU 36945)

DESCRIPTION_HTML = """<p>Build clean, low-profile walls and edging with Pocono Blend Wall Stone. Stack lightweight, thin-profile pieces quickly and achieve a natural look that blends cool grays, warm tans, and earthy browns. Buy by the pallet for full projects or by the pound for small repairs and accent work.</p>

<h3>Choose Your Unit of Sale</h3>
<ul>
  <li><strong>Per Pallet:</strong> A full pallet of 2&rdquo;&ndash;4&rdquo; wall stone &mdash; ideal for garden walls, retaining features, fire pit surrounds, and larger builds.</li>
  <li><strong>Per LB:</strong> Buy exactly the amount you need by weight &mdash; perfect for filling gaps, small repairs, accent pieces, and topping off a project.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Thin profile:</strong> Handle lighter pieces to speed up layout and stacking.</li>
  <li><strong>Natural stone:</strong> Rely on through-body color that won&rsquo;t chip or look artificial.</li>
  <li><strong>Split-face texture:</strong> Add depth and shadow lines that read crisp from the curb.</li>
  <li><strong>Random sizing:</strong> Stagger joints for tighter seams and a more custom finish.</li>
  <li><strong>Flexible install:</strong> Dry-stack for planters and accents or set with mortar/adhesive for added hold.</li>
</ul>

<h3>Applications</h3>
<p>Outline beds, edge walkways, and build low seating or garden walls that look established on day one. Create fire pit surrounds, mailbox bases, or tiered planters without heavy equipment. Blend new work into existing stone features with the versatile Pocono color mix.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural stone</li>
  <li><strong>Thickness:</strong> 2&rdquo;&ndash;4&rdquo;</li>
  <li><strong>Finish:</strong> Split-face surface with natural edges</li>
  <li><strong>Colors:</strong> Pocono blend &mdash; mixed grays, tans, and browns</li>
  <li><strong>Piece sizes:</strong> Random lengths and varied heights for organic coursing</li>
  <li><strong>Pallet weight:</strong> Approx. 3,000 lbs</li>
</ul>

<p>Plan a compacted, level base and include drainage behind any retained soil. Dry lay your pattern first, then set permanently for best results. Expect natural variation &mdash; sort pieces and face the best sides forward for a clean finish.</p>"""

PRODUCT_INPUT = {
    "title": "Pocono Blend Wall Stone",
    "handle": "pocono-blend-wall-stone",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Stone"],
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
            "price": "399.00",
            "sku": "36945",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "36945",
                "cost": "249.12",
                "measurement": {"weight": {"value": 3000.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 1}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '2"-4"'},
                {"optionName": "Unit of Sale", "name": "Per LB"},
            ],
            "price": "0.24",
            "sku": "36496",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": "36496",
                "cost": "0.09",
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
    log.info(f"Convert Pocono Blend Wall Stone — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Delete old single-variant product:")
    print(f"     {OLD_PRODUCT_ID}  (Wallstone Pocono Blend Thin, SKU 36945)")
    print(f"2. Create product '{PRODUCT_INPUT['title']}' (vendor={PRODUCT_INPUT['vendor']})")
    print(f"   handle={PRODUCT_INPUT['handle']}  tags={PRODUCT_INPUT['tags']}")
    print(f"   {len(PRODUCT_INPUT['variants'])} variants:")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        qty = v["inventoryQuantities"][0]["quantity"]
        print(f"     SKU {v['sku']:<7} {opts:<35} ${v['price']:<8} cost=${v['inventoryItem']['cost']:<7} wt={v['inventoryItem']['measurement']['weight']['value']:<8} inv={qty}")
    print(f"3. Publish new product to all sales channels")
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

    # 3. Publish
    log.info("Publishing to all sales channels...")
    pubs = gql(cfg, PUBLICATIONS_QUERY)["publications"]["edges"]
    pub_inputs = [{"publicationId": e["node"]["id"]} for e in pubs]
    pd = gql(cfg, PUBLISH_MUTATION, {"id": new_prod["id"], "input": pub_inputs})
    if pd["publishablePublish"]["userErrors"]:
        log.error(f"publish errors: {pd['publishablePublish']['userErrors']}")
    else:
        log.info(f"  Published to {len(pub_inputs)} channels")

    print()
    print("=" * 70)
    print("COMPLETED")
    print(f"New product URL path: /products/{new_prod['handle']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
