#!/usr/bin/env python3
"""
Enable oversell (inventoryPolicy: CONTINUE) on every variant of every product
tagged "Natural Stone" in the garoppos Shopify store.

Steps:
  1. Load Shopify credentials from uploader/config.json.
  2. Paginate products with `query: "tag:'Natural Stone'"`, fetching id, handle,
     title, and all variants with id, sku, inventoryPolicy, selectedOptions, title.
  3. Print a plan: product count, total variants, variants currently DENY,
     variants already CONTINUE, and a sample list of products (cap 20).
  4. Default to dry-run. Require --execute to mutate.
  5. Call productVariantsBulkUpdate per product with only the variants that are
     currently DENY, sending {id, inventoryPolicy: CONTINUE}. Per-product
     userErrors are logged and execution continues.
  6. After mutations, sample 3-5 products and re-query to confirm CONTINUE.

Constraints (Shopify GraphQL Admin API 2025-10):
  - Uses productVariantsBulkUpdate (not deprecated variant mutations).
  - Does NOT touch inventoryQuantity.
  - Stops with a diagnostic if zero products match "Natural Stone".
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # uploader/
CONFIG_PATH = REPO_ROOT / "config.json"
API_VERSION = "2025-10"

TARGET_TAG = "Natural Stone"
SHOPIFY_QUERY = f"tag:'{TARGET_TAG}'"

VARIANT_PAGE_SIZE = 250  # Shopify max per connection page
PRODUCT_PAGE_SIZE = 50   # keep cost reasonable while paginating

MUTATION_SLEEP_SEC = 0.4  # small pause between mutations to respect rate limits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    store = (
        cfg.get("SHOPIFY_STORE_URL", "")
        .replace("https://", "")
        .replace("http://", "")
        .strip()
        .rstrip("/")
    )
    token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()
    if not store or not token:
        sys.exit(
            "ERROR: SHOPIFY_STORE_URL or SHOPIFY_ACCESS_TOKEN missing from config.json"
        )
    return store, token


def gql(api_url, headers, query, variables=None, timeout=60, retries=3):
    """POST a GraphQL query with basic retry on 429/5xx."""
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                api_url,
                json={"query": query, "variables": variables or {}},
                headers=headers,
                timeout=timeout,
            )
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                time.sleep(2 ** attempt)
                last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                continue
            resp.raise_for_status()
            result = resp.json()
            if "errors" in result:
                raise RuntimeError(
                    f"GraphQL errors: {json.dumps(result['errors'], indent=2)}"
                )
            return result["data"]
        except requests.exceptions.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GraphQL call failed after {retries} retries: {last_err}")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

PRODUCTS_QUERY = """
query productsByTag($query: String!, $first: Int!, $after: String) {
  products(query: $query, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        handle
        title
        variants(first: 250) {
          edges {
            node {
              id
              sku
              title
              inventoryPolicy
              selectedOptions { name value }
            }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
  }
}
"""

VARIANTS_PAGE_QUERY = """
query productVariantsPage($id: ID!, $first: Int!, $after: String) {
  product(id: $id) {
    id
    variants(first: $first, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges {
        node {
          id
          sku
          title
          inventoryPolicy
          selectedOptions { name value }
        }
      }
    }
  }
}
"""


def fetch_all_products(api_url, headers):
    products = []
    cursor = None
    while True:
        data = gql(
            api_url,
            headers,
            PRODUCTS_QUERY,
            {"query": SHOPIFY_QUERY, "first": PRODUCT_PAGE_SIZE, "after": cursor},
        )
        conn = data["products"]
        for edge in conn["edges"]:
            node = edge["node"]
            variants = [ve["node"] for ve in node["variants"]["edges"]]
            # Handle products with >250 variants (rare but possible)
            if node["variants"]["pageInfo"]["hasNextPage"]:
                variants.extend(
                    fetch_remaining_variants(
                        api_url,
                        headers,
                        node["id"],
                        node["variants"]["pageInfo"]["endCursor"],
                    )
                )
            products.append(
                {
                    "id": node["id"],
                    "handle": node["handle"],
                    "title": node["title"],
                    "variants": variants,
                }
            )
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return products


def fetch_remaining_variants(api_url, headers, product_id, after_cursor):
    variants = []
    cursor = after_cursor
    while True:
        data = gql(
            api_url,
            headers,
            VARIANTS_PAGE_QUERY,
            {"id": product_id, "first": VARIANT_PAGE_SIZE, "after": cursor},
        )
        conn = data["product"]["variants"]
        variants.extend(ve["node"] for ve in conn["edges"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return variants


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def build_plan(products):
    total_variants = 0
    deny_count = 0
    continue_count = 0
    other_count = 0
    for p in products:
        for v in p["variants"]:
            total_variants += 1
            pol = (v.get("inventoryPolicy") or "").upper()
            if pol == "DENY":
                deny_count += 1
            elif pol == "CONTINUE":
                continue_count += 1
            else:
                other_count += 1
    return {
        "product_count": len(products),
        "total_variants": total_variants,
        "deny_count": deny_count,
        "continue_count": continue_count,
        "other_count": other_count,
    }


def print_plan(products, plan):
    print("=" * 72)
    print(f"Target tag: '{TARGET_TAG}' (query: {SHOPIFY_QUERY})")
    print(f"Products found:           {plan['product_count']}")
    print(f"Total variants:           {plan['total_variants']}")
    print(f"Variants DENY → CONTINUE: {plan['deny_count']}")
    print(f"Variants already CONTINUE (skip): {plan['continue_count']}")
    if plan["other_count"]:
        print(f"Variants with other policy:       {plan['other_count']}")
    print("-" * 72)
    shown = products[:20]
    for p in shown:
        print(
            f"  {p['handle']:<55} {len(p['variants']):>4}v  {p['title']}"
        )
    if len(products) > 20:
        print(f"  ... and {len(products) - 20} more")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

BULK_UPDATE_MUTATION = """
mutation productVariantsBulkUpdate(
  $productId: ID!,
  $variants: [ProductVariantsBulkInput!]!
) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    product { id }
    productVariants { id inventoryPolicy }
    userErrors { field message code }
  }
}
"""


def update_product_variants(api_url, headers, product, dry_run=True):
    """Return (changed, already_correct, errors) for the product."""
    to_update = [
        {"id": v["id"], "inventoryPolicy": "CONTINUE"}
        for v in product["variants"]
        if (v.get("inventoryPolicy") or "").upper() != "CONTINUE"
    ]
    already_correct = len(product["variants"]) - len(to_update)

    if not to_update:
        return 0, already_correct, []

    if dry_run:
        return len(to_update), already_correct, []

    data = gql(
        api_url,
        headers,
        BULK_UPDATE_MUTATION,
        {"productId": product["id"], "variants": to_update},
    )
    payload = data["productVariantsBulkUpdate"]
    errors = payload.get("userErrors") or []
    if errors:
        return 0, already_correct, errors

    updated = payload.get("productVariants") or []
    return len(updated), already_correct, []


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

VERIFY_QUERY = """
query verify($id: ID!) {
  product(id: $id) {
    id
    handle
    title
    variants(first: 250) {
      edges {
        node { id sku title inventoryPolicy }
      }
    }
  }
}
"""


def verify_sample(api_url, headers, products, sample_size=5):
    if not products:
        return []
    chosen = random.sample(products, min(sample_size, len(products)))
    results = []
    for p in chosen:
        data = gql(api_url, headers, VERIFY_QUERY, {"id": p["id"]})
        fresh = data["product"]
        variant_nodes = [e["node"] for e in fresh["variants"]["edges"]]
        policies = [(v["sku"] or v["title"], v["inventoryPolicy"]) for v in variant_nodes]
        results.append(
            {
                "handle": fresh["handle"],
                "title": fresh["title"],
                "variant_count": len(variant_nodes),
                "all_continue": all(
                    (v["inventoryPolicy"] or "").upper() == "CONTINUE"
                    for v in variant_nodes
                ),
                "sample_policies": policies[:5],
            }
        )
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Enable oversell on all Natural Stone variants."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run mutations (default is dry-run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run (default behavior; mutually exclusive w/ --execute).",
    )
    args = parser.parse_args()

    if args.execute and args.dry_run:
        sys.exit("ERROR: --execute and --dry-run are mutually exclusive.")

    dry_run = not args.execute

    store, token = load_config()
    api_url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}

    print(f"Shopify store: {store}")
    print(f"API version:   {API_VERSION}")
    print(f"Mode:          {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print()
    print(f"Querying products with tag '{TARGET_TAG}'...")

    products = fetch_all_products(api_url, headers)
    plan = build_plan(products)
    print_plan(products, plan)

    # Sanity checks
    if plan["product_count"] == 0:
        print()
        print("STOP: zero products matched the query. Checking tag spelling...")
        # Probe plural / alternative
        for probe in ("Natural Stones", "natural stone", "natural-stone"):
            data = gql(
                api_url,
                headers,
                PRODUCTS_QUERY,
                {"query": f"tag:'{probe}'", "first": 1, "after": None},
            )
            count = len(data["products"]["edges"])
            has_more = data["products"]["pageInfo"]["hasNextPage"]
            print(f"  probe tag:'{probe}' => {count}{'+' if has_more else ''} product(s)")
        sys.exit(1)

    if plan["product_count"] > 500:
        sys.exit(
            f"STOP: {plan['product_count']} products is unexpectedly large. "
            "Aborting as a sanity check."
        )

    if plan["deny_count"] == 0:
        print()
        print("All variants already have inventoryPolicy = CONTINUE. Nothing to do.")
        return

    if dry_run:
        print()
        print("Dry-run complete. Re-run with --execute to apply changes.")
        return

    # Execute
    print()
    print("Executing mutations...")
    total_changed = 0
    total_already = 0
    errored_products = []

    for i, p in enumerate(products, 1):
        try:
            changed, already, errors = update_product_variants(
                api_url, headers, p, dry_run=False
            )
        except Exception as e:
            print(f"  [{i}/{len(products)}] {p['handle']}: EXCEPTION {e}")
            errored_products.append((p["handle"], [{"message": str(e)}]))
            continue

        total_already += already
        if errors:
            errored_products.append((p["handle"], errors))
            print(
                f"  [{i}/{len(products)}] {p['handle']}: userErrors={len(errors)}"
            )
            for err in errors:
                print(f"     - {err.get('field')}: {err.get('message')}")
        else:
            total_changed += changed
            if changed:
                print(
                    f"  [{i}/{len(products)}] {p['handle']}: {changed} variant(s) DENY → CONTINUE"
                )
            else:
                print(
                    f"  [{i}/{len(products)}] {p['handle']}: already fully CONTINUE"
                )

        time.sleep(MUTATION_SLEEP_SEC)

    print()
    print("-" * 72)
    print("Mutation summary:")
    print(f"  Variants changed DENY → CONTINUE:  {total_changed}")
    print(f"  Variants already CONTINUE (skip):  {total_already}")
    print(f"  Products with userErrors:          {len(errored_products)}")
    if errored_products:
        for handle, errs in errored_products:
            print(f"    {handle}:")
            for e in errs:
                print(f"      - {e.get('field')}: {e.get('message')}")

    # Verify
    print()
    print("Verifying a random sample of products...")
    sample = verify_sample(api_url, headers, products, sample_size=5)
    for s in sample:
        flag = "OK" if s["all_continue"] else "MISMATCH"
        print(
            f"  [{flag}] {s['handle']} ({s['variant_count']} variants): "
            f"{s['title']}"
        )
        for sku, pol in s["sample_policies"]:
            print(f"      {sku}: {pol}")


if __name__ == "__main__":
    main()
