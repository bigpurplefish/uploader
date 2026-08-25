#!/usr/bin/env python3
"""Delete non-"Sq Ft" variants from Hardscaping products.

Targets products with product_type="Landscape and Construction" AND tag="Pavers and Hardscaping".
For each product, inspects variant metafield `custom.unit_of_sale`:
  - Keeps variants whose unit_of_sale is "Sq Ft" (case/whitespace-insensitive).
  - Deletes variants with any other unit_of_sale value (e.g. "Pallet", "Row").
  - Skips products where NO variant has a Sq Ft unit (would delete all variants).
  - Skips products where NO variant has the unit_of_sale metafield (not a UoS product).

Dry-run by default. Pass --execute to actually delete.
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
PRODUCT_TYPE = "Landscape and Construction"
CATEGORY_TAG = "Pavers and Hardscaping"
KEEP_UNIT = "sq ft"

PRODUCTS_QUERY = """
query getProducts($cursor: String) {
  products(first: 50, after: $cursor, query: "product_type:'Landscape and Construction' AND tag:'Pavers and Hardscaping'") {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        handle
        variants(first: 250) {
          edges {
            node {
              id
              title
              selectedOptions { name value }
              metafields(first: 30) {
                edges { node { namespace key value } }
              }
            }
          }
        }
      }
    }
  }
}
"""

DELETE_MUTATION = """
mutation productVariantsBulkDelete($productId: ID!, $variantsIds: [ID!]!) {
  productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
    product { id }
    userErrors { field message }
  }
}
"""


def api_url(cfg):
    store = cfg["SHOPIFY_STORE_URL"].replace("https://", "").replace("http://", "").strip("/")
    return f"https://{store}/admin/api/{API_VERSION}/graphql.json"


def headers(cfg):
    return {"Content-Type": "application/json", "X-Shopify-Access-Token": cfg["SHOPIFY_ACCESS_TOKEN"]}


def graphql(cfg, query, variables=None):
    r = requests.post(api_url(cfg), json={"query": query, "variables": variables or {}}, headers=headers(cfg), timeout=60)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def fetch_all_products(cfg):
    cursor = None
    while True:
        data = graphql(cfg, PRODUCTS_QUERY, {"cursor": cursor})
        conn = data["products"]
        for edge in conn["edges"]:
            yield edge["node"]
        if not conn["pageInfo"]["hasNextPage"]:
            return
        cursor = conn["pageInfo"]["endCursor"]


def variant_unit(variant):
    # Prefer the metafield; fall back to the "Unit of Sale" selectedOption if metafield is missing.
    for edge in variant["metafields"]["edges"]:
        node = edge["node"]
        if node["namespace"] == "custom" and node["key"] == "unit_of_sale":
            return (node["value"] or "").strip()
    for opt in variant["selectedOptions"]:
        if opt["name"].strip().lower() == "unit of sale":
            return (opt["value"] or "").strip()
    return None


def classify(product):
    """Return (keep, delete, skip_reason_or_None)."""
    variants = [e["node"] for e in product["variants"]["edges"]]
    with_unit = [(v, variant_unit(v)) for v in variants]
    has_any_unit = any(u is not None for _, u in with_unit)
    if not has_any_unit:
        return [], [], "no variants have custom.unit_of_sale metafield"

    keep = [v for v, u in with_unit if u is not None and u.lower() == KEEP_UNIT]
    delete = [v for v, u in with_unit if u is not None and u.lower() != KEEP_UNIT]

    if not keep:
        units_seen = sorted({u for _, u in with_unit if u})
        return [], [], f"no Sq Ft variants exist (found units: {units_seen})"
    return keep, delete, None


def describe_variant(v):
    opts = ", ".join(f"{o['name']}={o['value']}" for o in v["selectedOptions"])
    unit = variant_unit(v) or "-"
    return f"    - {v['id']}  unit={unit!r:<12} [{opts}]"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually delete (default: dry run)")
    parser.add_argument("--report", default=None, help="Write JSON plan to this path")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info("=" * 70)
    log.info(f"Simplify Hardscaping to Sq Ft — mode: {mode}")
    log.info(f"Filter: product_type='{PRODUCT_TYPE}' AND tag='{CATEGORY_TAG}'")
    log.info("=" * 70)

    plan = []
    skipped = []
    nothing_to_do = []

    for product in fetch_all_products(cfg):
        keep, delete, skip_reason = classify(product)
        if skip_reason:
            skipped.append({"id": product["id"], "title": product["title"], "reason": skip_reason})
            continue
        if not delete:
            nothing_to_do.append({"id": product["id"], "title": product["title"]})
            continue
        plan.append({
            "product_id": product["id"],
            "title": product["title"],
            "handle": product["handle"],
            "keep": [{"id": v["id"], "title": v["title"], "unit": variant_unit(v)} for v in keep],
            "delete": [{"id": v["id"], "title": v["title"], "unit": variant_unit(v)} for v in delete],
        })

    print()
    print("=" * 70)
    print(f"PLAN ({len(plan)} products with deletions)")
    print("=" * 70)
    total_delete = 0
    for entry in plan:
        print(f"\n{entry['title']}  ({entry['product_id']})")
        print(f"  KEEP ({len(entry['keep'])}):")
        for v in entry["keep"]:
            print(f"    - {v['id']}  unit={v['unit']!r:<12} title={v['title']!r}")
        print(f"  DELETE ({len(entry['delete'])}):")
        for v in entry["delete"]:
            print(f"    - {v['id']}  unit={v['unit']!r:<12} title={v['title']!r}")
        total_delete += len(entry["delete"])

    print()
    print("-" * 70)
    print(f"Summary: {len(plan)} products to modify, {total_delete} variants to delete")
    print(f"         {len(nothing_to_do)} products already Sq Ft-only (no action)")
    print(f"         {len(skipped)} products skipped (see --report for reasons)")
    print("-" * 70)

    if skipped:
        print("\nSKIPPED (no action taken — review manually if needed):")
        for s in skipped:
            print(f"  - {s['title']} — {s['reason']}")

    if args.report:
        with open(args.report, "w") as f:
            json.dump({"plan": plan, "skipped": skipped, "nothing_to_do": nothing_to_do}, f, indent=2)
        log.info(f"Wrote plan to {args.report}")

    if not args.execute:
        print("\nDRY RUN — no changes made. Rerun with --execute to delete.")
        return 0

    if not plan:
        print("\nNothing to delete.")
        return 0

    print(f"\nExecuting deletions on {len(plan)} products ({total_delete} variants)...")
    errors = []
    for i, entry in enumerate(plan, 1):
        variant_ids = [v["id"] for v in entry["delete"]]
        log.info(f"[{i}/{len(plan)}] Deleting {len(variant_ids)} variants from {entry['title']}")
        try:
            data = graphql(cfg, DELETE_MUTATION, {"productId": entry["product_id"], "variantsIds": variant_ids})
            user_errors = data["productVariantsBulkDelete"]["userErrors"]
            if user_errors:
                log.error(f"  userErrors: {user_errors}")
                errors.append({"product": entry["title"], "errors": user_errors})
            else:
                log.info(f"  OK")
        except Exception as e:
            log.exception(f"  FAILED: {e}")
            errors.append({"product": entry["title"], "error": str(e)})
        time.sleep(args.delay)

    print()
    print("=" * 70)
    if errors:
        print(f"COMPLETED WITH {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("COMPLETED SUCCESSFULLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
