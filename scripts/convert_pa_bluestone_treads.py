#!/usr/bin/env python3
"""Consolidate 'Blue Super Treads 12x4x2 RF' (SKU 41510) and
'Blue Super Treads 12X72X2 Ther' (SKU 41958) into
'PA Bluestone Treads' with 3 variants.

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

OLD_PRODUCT_IDS = [
    "gid://shopify/Product/10409594028324",  # Blue Super Treads 12x4x2 RF (SKU 41510)
    "gid://shopify/Product/10409597796644",  # Blue Super Treads 12X72X2 Ther (SKU 41958)
]

DESCRIPTION_HTML = """<p>Finish steps and transitions with PA Bluestone Treads. These solid bluestone pieces deliver the weight and durability needed for stair treads, coping, and sitting walls. Choose rockfaced for a natural split edge or thermal for a smooth, clean finish. Buy individual pieces in the size that fits your project.</p>

<h3>Choose Your Size</h3>
<ul>
  <li><strong>12&rdquo; &times; 4&rsquo; &times; 2&rdquo;:</strong> Standard 4-foot tread for residential steps, stoops, and low walls.</li>
  <li><strong>12&rdquo; &times; 6&rsquo; &times; 2&rdquo;:</strong> Extended 6-foot tread for wider staircases, landings, and coping applications.</li>
</ul>

<h3>Choose Your Type</h3>
<ul>
  <li><strong>Rockfaced:</strong> Natural split edge with a rugged, traditional profile. Available in 12&rdquo;&times;4&rsquo;&times;2&rdquo;.</li>
  <li><strong>Thermal:</strong> Heat-treated smooth surface and sawn edges for a refined, contemporary look.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Solid 2&rdquo; thickness:</strong> Built-in mass for structural stability on steps and wall caps.</li>
  <li><strong>Natural bluestone:</strong> Classic blue-grey tones that age gracefully and complement any hardscape.</li>
  <li><strong>Slip-resistant surface:</strong> Both rockfaced and thermal finishes provide traction underfoot.</li>
  <li><strong>Sold per piece:</strong> Buy exactly the quantity you need for your layout.</li>
</ul>

<h3>Applications</h3>
<p>Set step treads on masonry or dry-laid stone risers. Cap retaining walls and seat walls for a finished edge. Use as pool coping, porch edging, or transition strips between grade changes. Combine rockfaced and thermal finishes for contrasting textures on the same project.</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> Natural Pennsylvania bluestone</li>
  <li><strong>Finishes:</strong> Rockfaced (natural split) and Thermal (heat-treated smooth)</li>
  <li><strong>Thickness:</strong> 2&rdquo;</li>
  <li><strong>Color:</strong> Classic blue-grey</li>
  <li><strong>Sizes:</strong> 12&rdquo;&times;4&rsquo; and 12&rdquo;&times;6&rsquo;</li>
</ul>

<p>Set treads with a slight forward pitch for drainage. Bed on a full mortar setting or use construction adhesive over stable, level risers. Overhang the riser face by 1&ndash;1.5&rdquo; for a clean shadow line. Seal to enhance color and protect against staining.</p>"""

PRODUCT_INPUT = {
    "title": "PA Bluestone Treads",
    "handle": "pa-bluestone-treads",
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Natural Stone", "Treads"],
    "category": TAXONOMY_ID,
    "descriptionHtml": DESCRIPTION_HTML,
    "productOptions": [
        {"name": "Size", "position": 1, "values": [
            {"name": '12"x4\'x2"'}, {"name": '12"x6\'x2"'},
        ]},
        {"name": "Type", "position": 2, "values": [{"name": "Rockfaced"}, {"name": "Thermal"}]},
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
                {"optionName": "Size", "name": '12"x4\'x2"'},
                {"optionName": "Type", "name": "Rockfaced"},
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "98.00",
            "sku": "41510",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "41510", "cost": "77.25",
                "measurement": {"weight": {"value": 121.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 3}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '12"x4\'x2"'},
                {"optionName": "Type", "name": "Thermal"},
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "50.00",
            "sku": "41511",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "41511", "cost": "33.59",
                "measurement": {"weight": {"value": 121.0, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 0}],
        },
        {
            "optionValues": [
                {"optionName": "Size", "name": '12"x6\'x2"'},
                {"optionName": "Type", "name": "Thermal"},
                {"optionName": "Unit of Sale", "name": "Per Piece"},
            ],
            "price": "140.00",
            "sku": "41958",
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True, "sku": "41958", "cost": "100.32",
                "measurement": {"weight": {"value": 181.5, "unit": "POUNDS"}},
            },
            "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": 62}],
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
    log.info(f"Convert PA Bluestone Treads — mode: {mode}")

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Delete old products:")
    for pid in OLD_PRODUCT_IDS:
        print(f"     {pid}")
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

    log.info("Deleting old products...")
    for pid in OLD_PRODUCT_IDS:
        dd = gql(cfg, DELETE_MUTATION, {"input": {"id": pid}})
        ue = dd["productDelete"]["userErrors"]
        if ue:
            log.error(f"  delete errors for {pid}: {ue}")
        else:
            log.info(f"  OK deleted {dd['productDelete']['deletedProductId']}")
        time.sleep(0.5)
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
