#!/usr/bin/env python3
"""Expand Fieldstone Boulder product: rename to plural, add 4 new variants.

New variants: 47715, 47716, 47717 (migrated from legacy), 47718.
Also deletes legacy standalone product 'Fieldstone Boulders (6-7 Per Pallet)' (SKU 47717).

Dry-run by default; --execute to apply.
"""
import argparse, json, logging, os, sys, time
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from uploader_modules.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_VERSION = "2025-10"
LOCATION_ID = "gid://shopify/Location/110377107748"
TAXONOMY_ID = "gid://shopify/TaxonomyCategory/bi-4-3"

PRODUCT_ID = "gid://shopify/Product/10426830913828"
LEGACY_47717_PRODUCT_ID = "gid://shopify/Product/10409644359972"

EXISTING_VARIANTS = {
    "39859": "gid://shopify/ProductVariant/53320943763748",
    "36955": "gid://shopify/ProductVariant/53320943796516",
    "37529": "gid://shopify/ProductVariant/53320943829284",
}

DESCRIPTION_HTML = """<p>Anchor your landscape with natural fieldstone boulders that deliver instant structure, weathered texture, and long-term stability. Place these rugged stones to frame entries, build retaining accents, terrace slopes, or create focal points that look like they've always belonged on your property.</p>

<h3>Choose Your Size and Unit of Sale</h3>
<ul>
  <li><strong>1 Per Pallet:</strong> A single large anchor boulder delivered on its own pallet &mdash; ideal for statement pieces.</li>
  <li><strong>2 Per Pallet:</strong> Two mid-size boulders on a shared pallet &mdash; available by the pallet or by the stone (drawn from 2-per pallet stock).</li>
  <li><strong>4&ndash;5 Per Pallet:</strong> Four to five medium boulders per pallet &mdash; available by the pallet or by the pound for flexible project sizing.</li>
  <li><strong>6&ndash;7 Per Pallet:</strong> Six to seven smaller boulders per pallet &mdash; available by the pallet or by the pound. Great for tight-joint walls and edging.</li>
</ul>

<h3>Key Features</h3>
<ul>
  <li><strong>Natural stone mass:</strong> Add real weight and stability for walls, borders, and outcrops.</li>
  <li><strong>Weathered faces:</strong> Showcase organic texture that blends into surrounding terrain.</li>
  <li><strong>Durable in all climates:</strong> Stand up to freeze&ndash;thaw cycles and heavy use.</li>
  <li><strong>Varied shapes:</strong> Fit stones together for tight joints and a cleaner finished look.</li>
  <li><strong>Flexible purchase units:</strong> Buy by the pallet, by the stone, or by the pound &mdash; whatever fits your project.</li>
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


def variant_spec(sku, size, uos, price, cost, weight_lbs, qty, existing_id=None):
    v = {
        "optionValues": [
            {"optionName": "Size", "name": size},
            {"optionName": "Unit of Sale", "name": uos},
        ],
        "price": price,
        "sku": sku,
        "inventoryPolicy": "DENY",
        "inventoryItem": {
            "tracked": True,
            "sku": sku,
            "measurement": {"weight": {"value": weight_lbs, "unit": "POUNDS"}},
        },
        "inventoryQuantities": [{"locationId": LOCATION_ID, "name": "available", "quantity": qty}],
    }
    if cost is not None:
        v["inventoryItem"]["cost"] = cost
    if existing_id:
        v["id"] = existing_id
    return v


PRODUCT_INPUT = {
    "id": PRODUCT_ID,
    "title": "Fieldstone Boulders",
    "descriptionHtml": DESCRIPTION_HTML,
    "vendor": "Everlast",
    "productType": "Landscape and Construction",
    "status": "ACTIVE",
    "tags": ["Aggregates", "Stone"],
    "category": TAXONOMY_ID,
    "productOptions": [
        {"name": "Size", "position": 1, "values": [
            {"name": "2 Per Pallet"},
            {"name": "1 Per Pallet"},
            {"name": "4-5 Per Pallet"},
            {"name": "6-7 Per Pallet"},
        ]},
        {"name": "Unit of Sale", "position": 2, "values": [
            {"name": "Per Pallet"},
            {"name": "Per Stone"},
            {"name": "Per LB"},
        ]},
    ],
    "variants": [
        # Existing
        variant_spec("39859", "2 Per Pallet", "Per Pallet", "420.00", "114.00", 1200.0, 3, EXISTING_VARIANTS["39859"]),
        variant_spec("36955", "2 Per Pallet", "Per Stone",  "220.00", "114.00", 400.0,  0, EXISTING_VARIANTS["36955"]),
        variant_spec("37529", "1 Per Pallet", "Per Pallet", "402.60", "283.29", 400.0,  14, EXISTING_VARIANTS["37529"]),
        # New
        variant_spec("47715", "4-5 Per Pallet", "Per Pallet", "400.09", "295.21", 2100.0, 0),
        variant_spec("47716", "4-5 Per Pallet", "Per LB",     "0.24",   None,    1.0,    0),
        variant_spec("47717", "6-7 Per Pallet", "Per Pallet", "400.09", "272.50", 2500.0, 3),  # inv migrated from legacy
        variant_spec("47718", "6-7 Per Pallet", "Per LB",     "0.24",   None,    1.0,    0),
    ],
}

PRODUCT_SET = """
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
  productSet(synchronous: $synchronous, input: $input) {
    product {
      id title handle
      variants(first: 20) { edges { node { id sku price inventoryQuantity selectedOptions { name value } } } }
    }
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
    r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}}, headers=headers(cfg), timeout=120)
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

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    print(f"1. Update product {PRODUCT_ID}")
    print(f"   title: 'Fieldstone Boulder' -> 'Fieldstone Boulders'")
    print(f"   descriptionHtml: updated to cover all 7 variants")
    print(f"   variants (7 total):")
    for v in PRODUCT_INPUT["variants"]:
        opts = " / ".join(o["name"] for o in v["optionValues"])
        cost = v["inventoryItem"].get("cost", "—")
        wt = v["inventoryItem"]["measurement"]["weight"]["value"]
        qty = v["inventoryQuantities"][0]["quantity"]
        status = "KEEP " if "id" in v else "NEW  "
        print(f"     {status} SKU {v['sku']}  {opts:<32}  ${v['price']:<8} cost=${cost!s:<8} wt={wt:<6} inv={qty}")
    print(f"2. Delete legacy product: {LEGACY_47717_PRODUCT_ID}")
    print(f"   (Fieldstone Boulders (6-7 Per Pallet), SKU 47717, inv=3 migrated into new variant)")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to apply.")
        return 0

    log.info("Updating product via productSet...")
    data = gql(cfg, PRODUCT_SET, {"synchronous": True, "input": PRODUCT_INPUT})
    ue = data["productSet"]["userErrors"]
    if ue:
        log.error(f"productSet userErrors: {ue}")
        return 1
    p = data["productSet"]["product"]
    log.info(f"  OK  title={p['title']}  handle={p['handle']}")
    for e in p["variants"]["edges"]:
        v = e["node"]
        opts = " / ".join(f"{o['name']}={o['value']}" for o in v["selectedOptions"])
        log.info(f"    SKU={v['sku']}  ${v['price']}  inv={v['inventoryQuantity']}  [{opts}]")

    log.info("Deleting legacy standalone 47717 product...")
    dd = gql(cfg, DELETE_MUTATION, {"input": {"id": LEGACY_47717_PRODUCT_ID}})
    ue = dd["productDelete"]["userErrors"]
    if ue:
        log.error(f"  delete errors: {ue}")
    else:
        log.info(f"  OK deleted {dd['productDelete']['deletedProductId']}")

    print()
    print("COMPLETED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
