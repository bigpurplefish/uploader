#!/usr/bin/env python3
"""Create a new Shopify product (Pro Lime Pelletized Dolomitic Lime).

Parameterized — product spec lives in the CONSTANTS block below. Use this as
a template for creating single-variant lawn & garden products. To reuse for
another product, copy the constants block, edit values, rename the file.

Phases:
  1. Pre-check — query for SKU or exact title collisions; stop if found
  2. Create via productSet(synchronous: true, input: ProductSetInput)
  3. Verify publications; unpublish from anything other than Online Store + POS
  4. Re-query and confirm final state

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

# =============================================================================
# PUBLICATION IDs (per project memory — Online Store + POS only)
# =============================================================================
PUB_ONLINE_STORE = "gid://shopify/Publication/286630838564"
PUB_POS          = "gid://shopify/Publication/286630871332"
ALLOWED_PUB_IDS  = {PUB_ONLINE_STORE, PUB_POS}

LOCATION_ID = "gid://shopify/Location/110377107748"  # 1200 Harding Hwy

# =============================================================================
# PRODUCT SPEC — edit this block for new products
# =============================================================================
SKU                 = "3492"
TITLE               = "Pro Lime Pelletized Dolomitic Lime"
HANDLE              = "pro-lime-pelletized-dolomitic-lime"
VENDOR              = "Gardenscape"
PRODUCT_TYPE        = "Lawn and Garden"
TAGS                = ["Garden Supplies", "Soil Conditioners"]
CATEGORY_ID         = "gid://shopify/TaxonomyCategory/hg-12-1-18-2"  # Soil
STATUS              = "ACTIVE"

SIZE_VALUE          = "50 LB"
UOS_VALUE           = "Bag"
PRICE               = "5.75"
COST                = "4.10"
WEIGHT_VALUE        = 50.0
WEIGHT_UNIT         = "POUNDS"
INITIAL_QUANTITY    = 0
INVENTORY_POLICY    = "DENY"

DESCRIPTION_HTML = (
    '<p>Sweeten acidic soil and unlock healthy growth with Pro Lime Pelletized '
    'Dolomitic Lime. Raise soil pH, neutralize acidity, and feed lawns and '
    'gardens with the calcium and magnesium plants need to green up, root '
    'deep, and stand up to drought and disease.</p>'

    '<p>Apply it in spring or fall to turf that looks tired, yellowed, or '
    'moss-prone, and work it into vegetable beds, flower gardens, and new '
    'plantings before seed or transplant goes in. The pelletized form loads '
    'cleanly into drop and broadcast spreaders, lays down a uniform pattern '
    'without the dust of powdered lime, and starts working as soon as it '
    'hits moisture.</p>'

    '<p>One 50 lb bag treats roughly 1,000 sq ft at standard lawn '
    'application rates &mdash; plenty for a front yard, a garden plot, or a '
    'maintenance round across beds. Check your soil with a simple pH test '
    'first, then spread, water in, and let the calcium and magnesium do the '
    'rest.</p>'
)

SEO_TITLE = 'Pro Lime Pelletized Dolomitic Lime \u2014 50 lb Bag | Raise Soil pH'
SEO_DESCRIPTION = (
    'Pelletized dolomitic lime, 50 lb bag. Raises soil pH, adds calcium and '
    'magnesium, and spreads cleanly on lawns and gardens. Sweeten acidic soil fast.'
)

# =============================================================================
# GraphQL
# =============================================================================
PRE_CHECK = """
query($sku: String!, $titleQuery: String!) {
  bySku: products(first: 5, query: $sku) {
    edges { node { id title handle variants(first: 5) { edges { node { sku } } } } }
  }
  byTitle: products(first: 5, query: $titleQuery) {
    edges { node { id title handle } }
  }
}
"""

PRODUCT_SET = """
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
  productSet(synchronous: $synchronous, input: $input) {
    product {
      id handle title status vendor productType tags
      descriptionHtml
      seo { title description }
      category { id fullName }
      options { id name position values }
      variants(first: 10) {
        edges { node {
          id sku title price
          selectedOptions { name value }
          inventoryItem {
            id
            tracked
            unitCost { amount }
            measurement { weight { value unit } }
            inventoryLevels(first: 5) {
              edges { node {
                location { id name }
                quantities(names: ["available"]) { name quantity }
              } }
            }
          }
        } }
      }
      resourcePublications(first: 20, onlyPublished: true) {
        edges { node { publication { id name } } }
      }
    }
    userErrors { field message }
  }
}
"""

PRODUCT_DETAIL = """
query($id: ID!) {
  product(id: $id) {
    id handle title status vendor productType tags
    descriptionHtml
    seo { title description }
    category { id fullName }
    options { id name position values }
    variants(first: 10) {
      edges { node {
        id sku title price
        selectedOptions { name value }
        inventoryItem {
          id
          tracked
          unitCost { amount }
          measurement { weight { value unit } }
          inventoryLevels(first: 5) {
            edges { node {
              location { id name }
              quantities(names: ["available"]) { name quantity }
            } }
          }
        }
      } }
    }
    resourcePublications(first: 20, onlyPublished: true) {
      edges { node { publication { id name } } }
    }
  }
}
"""

PUBLISHABLE_UNPUBLISH = """
mutation($id: ID!, $input: [PublicationInput!]!) {
  publishableUnpublish(id: $id, input: $input) {
    userErrors { field message }
  }
}
"""

PUBLISHABLE_PUBLISH = """
mutation($id: ID!, $input: [PublicationInput!]!) {
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


def gql(cfg, q, v=None, retries=5):
    for _ in range(retries):
        r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}},
                          headers=headers(cfg), timeout=120)
        r.raise_for_status()
        d = r.json()
        if "errors" in d:
            if any("THROTTLED" in str(e).upper() for e in d["errors"]):
                time.sleep(2); continue
            raise RuntimeError(f"GraphQL errors: {d['errors']}")
        return d["data"]
    raise RuntimeError("retries exhausted")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Create {TITLE!r}  mode={mode}")

    # --- Phase 1: Pre-check collisions ---
    print("\n" + "=" * 72)
    print("PHASE 1 — PRE-CHECK")
    print("=" * 72)
    pc = gql(cfg, PRE_CHECK, {"sku": f"sku:{SKU}", "titleQuery": f'title:"{TITLE}"'})
    sku_hits = pc["bySku"]["edges"]
    title_hits = pc["byTitle"]["edges"]
    if sku_hits:
        log.error(f"SKU {SKU} already exists on {len(sku_hits)} product(s):")
        for e in sku_hits:
            n = e["node"]
            skus = [v["node"]["sku"] for v in n["variants"]["edges"]]
            log.error(f"    {n['id']}  title={n['title']!r}  skus={skus}")
        log.error("STOP — would create a duplicate SKU. Exiting.")
        return 1
    else:
        log.info(f"  [ok] no product uses SKU {SKU}")

    if title_hits:
        # Exact-title match check
        exact = [e for e in title_hits if e["node"]["title"].strip().lower() == TITLE.lower()]
        if exact:
            log.error(f"Product with exact title {TITLE!r} already exists:")
            for e in exact:
                n = e["node"]
                log.error(f"    {n['id']}  handle={n['handle']}")
            log.error("STOP — would create a duplicate product. Exiting.")
            return 1
        else:
            log.info(f"  [ok] title {TITLE!r} does not collide exactly (found {len(title_hits)} partial matches)")
    else:
        log.info(f"  [ok] no product matches title {TITLE!r}")

    # --- Plan ---
    print("\n" + "=" * 72)
    print("PLAN")
    print("=" * 72)
    print(f"Title:        {TITLE}")
    print(f"Handle:       {HANDLE}")
    print(f"Vendor:       {VENDOR}")
    print(f"Product Type: {PRODUCT_TYPE}")
    print(f"Tags:         {TAGS}")
    print(f"Category:     {CATEGORY_ID}")
    print(f"Status:       {STATUS}")
    print(f"Variant:      SKU={SKU}  Size={SIZE_VALUE!r}  UoS={UOS_VALUE!r}  ${PRICE}  cost=${COST}  wt={WEIGHT_VALUE}{WEIGHT_UNIT}")
    print(f"Inventory:    {INITIAL_QUANTITY} at {LOCATION_ID}")
    print(f"Description:  {len(DESCRIPTION_HTML)} chars")
    print(f"SEO title:    ({len(SEO_TITLE)} chars)  {SEO_TITLE!r}")
    print(f"SEO desc:     ({len(SEO_DESCRIPTION)} chars)  {SEO_DESCRIPTION!r}")
    print(f"Target pubs:  Online Store + POS only")
    assert len(SEO_TITLE) <= 70, f"SEO title too long: {len(SEO_TITLE)}"
    assert len(SEO_DESCRIPTION) <= 160, f"SEO desc too long: {len(SEO_DESCRIPTION)}"

    if not args.execute:
        print("\nDRY RUN — rerun with --execute to create the product.")
        return 0

    # --- Phase 2: Create via productSet ---
    print("\n" + "=" * 72)
    print("PHASE 2 — productSet")
    print("=" * 72)
    product_input = {
        "handle": HANDLE,
        "title": TITLE,
        "vendor": VENDOR,
        "productType": PRODUCT_TYPE,
        "tags": TAGS,
        "category": CATEGORY_ID,
        "status": STATUS,
        "descriptionHtml": DESCRIPTION_HTML,
        "seo": {"title": SEO_TITLE, "description": SEO_DESCRIPTION},
        "productOptions": [
            {"name": "Size", "position": 1, "values": [{"name": SIZE_VALUE}]},
            {"name": "Unit of Sale", "position": 2, "values": [{"name": UOS_VALUE}]},
        ],
        "variants": [
            {
                "optionValues": [
                    {"optionName": "Size", "name": SIZE_VALUE},
                    {"optionName": "Unit of Sale", "name": UOS_VALUE},
                ],
                "price": PRICE,
                "sku": SKU,
                "inventoryPolicy": INVENTORY_POLICY,
                "inventoryItem": {
                    "tracked": True,
                    "sku": SKU,
                    "cost": COST,
                    "measurement": {
                        "weight": {"value": WEIGHT_VALUE, "unit": WEIGHT_UNIT}
                    },
                },
                "inventoryQuantities": [
                    {"locationId": LOCATION_ID, "name": "available", "quantity": INITIAL_QUANTITY}
                ],
            }
        ],
    }
    log.info("Calling productSet (synchronous=true)...")
    data = gql(cfg, PRODUCT_SET, {"synchronous": True, "input": product_input})
    ue = data["productSet"]["userErrors"]
    if ue:
        log.error(f"productSet userErrors: {ue}")
        return 1
    p = data["productSet"]["product"]
    log.info(f"  OK  id={p['id']}  handle={p['handle']}")
    new_pid = p["id"]
    v = p["variants"]["edges"][0]["node"]
    log.info(f"  variant: id={v['id']}  sku={v['sku']}  price={v['price']}")
    log.info(f"  inventoryItem: id={v['inventoryItem']['id']}  cost={(v['inventoryItem'].get('unitCost') or {}).get('amount')}")
    pubs = [e["node"]["publication"] for e in p["resourcePublications"]["edges"]]
    log.info(f"  publications immediately after create ({len(pubs)}):")
    for pub in pubs:
        log.info(f"    {pub['name']:<25} id={pub['id']}")

    # --- Phase 3: Fix publications ---
    print("\n" + "=" * 72)
    print("PHASE 3 — Reconcile publications")
    print("=" * 72)
    current_pub_ids = {pub["id"] for pub in pubs}
    to_unpublish = [pid for pid in current_pub_ids if pid not in ALLOWED_PUB_IDS]
    to_publish = [pid for pid in ALLOWED_PUB_IDS if pid not in current_pub_ids]

    if to_unpublish:
        log.info(f"  Unpublishing from {len(to_unpublish)} non-allowed channel(s)...")
        resp = gql(cfg, PUBLISHABLE_UNPUBLISH, {
            "id": new_pid,
            "input": [{"publicationId": pid} for pid in to_unpublish],
        })
        ue_u = resp["publishableUnpublish"]["userErrors"]
        if ue_u:
            log.error(f"    publishableUnpublish errors: {ue_u}")
        else:
            for pid in to_unpublish:
                log.info(f"    OK unpublished from {pid}")
    else:
        log.info("  No extra publications to remove")

    if to_publish:
        log.info(f"  Publishing to {len(to_publish)} required channel(s)...")
        resp = gql(cfg, PUBLISHABLE_PUBLISH, {
            "id": new_pid,
            "input": [{"publicationId": pid} for pid in to_publish],
        })
        ue_p = resp["publishablePublish"]["userErrors"]
        if ue_p:
            log.error(f"    publishablePublish errors: {ue_p}")
        else:
            for pid in to_publish:
                log.info(f"    OK published to {pid}")
    else:
        log.info("  Already published to all allowed channels")

    # --- Phase 4: Final verification ---
    print("\n" + "=" * 72)
    print("PHASE 4 — Verify")
    print("=" * 72)
    time.sleep(1)
    final = gql(cfg, PRODUCT_DETAIL, {"id": new_pid})["product"]

    print(f"\nID:           {final['id']}")
    print(f"Handle:       {final['handle']}")
    print(f"Title:        {final['title']!r}")
    print(f"Vendor:       {final['vendor']}")
    print(f"Product Type: {final['productType']}")
    print(f"Status:       {final['status']}")
    print(f"Tags:         {final['tags']}")
    cat = final.get("category")
    print(f"Category:     {cat.get('fullName') if cat else None}")
    print(f"Description:  ({len(final.get('descriptionHtml') or '')} chars)")
    seo = final.get("seo") or {}
    print(f"SEO title:    ({len(seo.get('title') or '')}) {seo.get('title')!r}")
    print(f"SEO desc:     ({len(seo.get('description') or '')}) {seo.get('description')!r}")
    print(f"Options:")
    for o in final.get("options") or []:
        print(f"  [{o['position']}] {o['name']} = {o['values']}")
    for e in final["variants"]["edges"]:
        v = e["node"]
        item = v.get("inventoryItem") or {}
        cost = (item.get("unitCost") or {}).get("amount")
        wt = (item.get("measurement") or {}).get("weight") or {}
        levels = (item.get("inventoryLevels") or {}).get("edges") or []
        opts = ", ".join(f"{o['name']}={o['value']}" for o in v["selectedOptions"])
        print(f"Variant:")
        print(f"  id={v['id']}  sku={v['sku']}  price=${v['price']}  cost={cost}")
        print(f"  weight={wt.get('value')}{wt.get('unit')}  tracked={item.get('tracked')}")
        print(f"  inventoryItem id={item.get('id')}")
        print(f"  options: {opts}")
        for le in levels:
            loc = le["node"]["location"]
            qty = 0
            for qq in le["node"].get("quantities") or []:
                if qq["name"] == "available":
                    qty = qq["quantity"] or 0
            print(f"  inventory: {loc['name']}={qty}")
    pubs_final = [e["node"]["publication"] for e in final["resourcePublications"]["edges"]]
    print(f"Publications ({len(pubs_final)}):")
    for pub in pubs_final:
        flag = " [ALLOWED]" if pub["id"] in ALLOWED_PUB_IDS else " [UNEXPECTED]"
        print(f"  {pub['name']:<25} id={pub['id']}{flag}")

    store_host = cfg["SHOPIFY_STORE_URL"].replace("https://","").replace("http://","").strip("/")
    print()
    print("=" * 72)
    print("COMPLETED")
    print("=" * 72)
    print(f"Storefront: https://garoppos.com/products/{final['handle']}")
    print(f"Admin:      https://{store_host}/admin/products/{new_pid.rsplit('/',1)[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
