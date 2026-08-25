#!/usr/bin/env python3
"""
Set the `custom.color_swatch_image` metafield on every Lilac variant of the
"Retail Pack Standing Irregulars" product (handle: retail-pack-standing-irregulars).

Steps:
  1. Load Shopify credentials from uploader/config.json.
  2. Look up product by handle (retail-pack-standing-irregulars) via GraphQL.
  3. Filter variants where the color option value == "Lilac" — fresh from the API,
     NOT hardcoded.
  4. Read existing `custom.color_swatch_image` metafield value for each variant
     (before state).
  5. STOP if any existing metafield has a non-matching type (e.g. not
     `single_line_text_field`) — metafield type mismatches must be resolved
     manually.
  6. Set `custom.color_swatch_image` to the target CDN URL via `metafieldsSet`
     on every Lilac variant.
  7. Re-query metafield value on each variant and confirm it equals the target
     CDN URL. Fail loud (exit non-zero) on mismatch.

Usage:
    python set_lilac_swatch_metafield.py --dry-run
    python set_lilac_swatch_metafield.py

Hard constraints:
  - Shopify GraphQL API 2025-10.
  - Only touches variants whose color option value == "Lilac".
  - STOPs if zero Lilac variants match, or color option cannot be identified.
  - STOPs on metafield type mismatch — does not mutate in that case.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # uploader/
CONFIG_PATH = REPO_ROOT / "config.json"
PRODUCT_HANDLE = "retail-pack-standing-irregulars"
TARGET_COLOR = "Lilac"
API_VERSION = "2025-10"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"
TARGET_CDN_URL = (
    "https://cdn.shopify.com/s/files/1/0968/5322/9860/files/"
    "40971_processed.png?v=1776690946"
)


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


def gql(api_url, headers, query, variables=None, timeout=60):
    resp = requests.post(
        api_url,
        json={"query": query, "variables": variables or {}},
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    result = resp.json()
    if "errors" in result:
        raise RuntimeError(
            f"GraphQL errors: {json.dumps(result['errors'], indent=2)}"
        )
    return result["data"]


# ---------------------------------------------------------------------------
# Product + variant lookup (fresh gids — don't trust hardcoded values)
# ---------------------------------------------------------------------------

PRODUCT_QUERY = """
query getProductByHandle($handle: String!, $ns: String!, $key: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    options { id name position values }
    variants(first: 250) {
      edges {
        node {
          id
          sku
          title
          selectedOptions { name value }
          metafield(namespace: $ns, key: $key) {
            id
            namespace
            key
            type
            value
          }
        }
      }
    }
  }
}
"""


def fetch_product(api_url, headers, handle):
    data = gql(
        api_url,
        headers,
        PRODUCT_QUERY,
        {"handle": handle, "ns": METAFIELD_NAMESPACE, "key": METAFIELD_KEY},
    )
    product = data.get("productByHandle")
    if not product:
        sys.exit(f"ERROR: Product with handle '{handle}' not found.")
    return product


def find_color_option_name(product):
    """Return the option name that represents color (case-insensitive match)."""
    for opt in product.get("options", []):
        if "color" in opt["name"].lower():
            return opt["name"]
    return None


def filter_target_color_variants(product, color_option_name, target_color):
    matches = []
    for edge in product["variants"]["edges"]:
        v = edge["node"]
        for sel in v["selectedOptions"]:
            if (
                sel["name"] == color_option_name
                and sel["value"].strip().lower() == target_color.lower()
            ):
                matches.append(v)
                break
    return matches


# ---------------------------------------------------------------------------
# metafieldsSet
# ---------------------------------------------------------------------------

METAFIELDS_SET_MUTATION = """
mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      id
      namespace
      key
      type
      value
      ownerType
      owner {
        ... on ProductVariant { id sku }
      }
    }
    userErrors { field message code }
  }
}
"""


def set_metafields_batch(api_url, headers, variant_ids, value):
    inputs = [
        {
            "ownerId": vid,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "type": METAFIELD_TYPE,
            "value": value,
        }
        for vid in variant_ids
    ]
    data = gql(
        api_url,
        headers,
        METAFIELDS_SET_MUTATION,
        {"metafields": inputs},
    )
    return data["metafieldsSet"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            f"Set custom.color_swatch_image on every {TARGET_COLOR} variant "
            f"of {PRODUCT_HANDLE}."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan and before state; do not mutate.",
    )
    args = parser.parse_args()

    store, token = load_config()
    api_url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }

    print(f"Store: {store}")
    print(f"API version: {API_VERSION}")
    print(f"Product handle: {PRODUCT_HANDLE}")
    print(f"Target color: {TARGET_COLOR}")
    print(f"Metafield: {METAFIELD_NAMESPACE}.{METAFIELD_KEY} ({METAFIELD_TYPE})")
    print(f"Target value: {TARGET_CDN_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    # 1. Lookup product (fresh)
    product = fetch_product(api_url, headers, PRODUCT_HANDLE)
    product_id = product["id"]
    variant_edges = product["variants"]["edges"]
    print(f"Product: {product['title']}")
    print(f"Product id: {product_id}")
    print(f"Total variants: {len(variant_edges)}")
    opt_summary = ", ".join(
        f"{o['name']}@{o['position']}" for o in product.get("options", [])
    )
    print(f"Options: {opt_summary}")

    # 2. Find color option
    color_opt = find_color_option_name(product)
    if not color_opt:
        sys.exit("ERROR: Could not identify a Color option on this product. STOP.")
    print(f"Color option detected: {color_opt}")

    # 3. Filter target-color variants (fresh ids from API)
    target_variants = filter_target_color_variants(product, color_opt, TARGET_COLOR)
    if not target_variants:
        sys.exit(
            f"ERROR: No variants with {color_opt} == '{TARGET_COLOR}'. STOP."
        )
    print(f"\n{TARGET_COLOR} variants matched ({len(target_variants)}):")
    for v in target_variants:
        opts = ", ".join(f"{s['name']}={s['value']}" for s in v["selectedOptions"])
        mf = v.get("metafield")
        mf_summary = (
            f"{mf['type']}={mf['value']!r}" if mf else "(not set)"
        )
        print(
            f"  SKU={v.get('sku'):<8} id={v['id']}  title={v['title']!r}  "
            f"({opts})  metafield: {mf_summary}"
        )

    # 4. Check metafield type compatibility before any mutation
    before = {}
    type_mismatches = []
    for v in target_variants:
        mf = v.get("metafield")
        before[v["id"]] = {
            "sku": v.get("sku"),
            "title": v["title"],
            "metafield": mf,
        }
        if mf is not None and mf.get("type") != METAFIELD_TYPE:
            type_mismatches.append((v["id"], v.get("sku"), mf.get("type")))

    if type_mismatches:
        print("\nERROR: Existing metafield(s) have a type that differs from "
              f"'{METAFIELD_TYPE}':")
        for vid, sku, t in type_mismatches:
            print(f"  SKU={sku} id={vid}  existing type={t!r}")
        sys.exit(
            "STOP — metafield type mismatch must be resolved manually "
            "(a Shopify metafield definition may be locked to a different type)."
        )

    # 5. Dry-run stop
    if args.dry_run:
        print("\n[DRY RUN] Would call metafieldsSet with:")
        for v in target_variants:
            print(f"  ownerId={v['id']}  sku={v.get('sku')}  value={TARGET_CDN_URL}")
        print("\nRe-run without --dry-run to execute.")
        return 0

    # 6. Execute mutation
    variant_ids = [v["id"] for v in target_variants]
    print(f"\nSetting metafield on {len(variant_ids)} variants via metafieldsSet…")
    payload = set_metafields_batch(api_url, headers, variant_ids, TARGET_CDN_URL)

    user_errors = payload.get("userErrors") or []
    if user_errors:
        print("\nmetafieldsSet userErrors:")
        for err in user_errors:
            print(f"  {err}")

    set_metafields = payload.get("metafields") or []
    print(f"\nmetafieldsSet returned {len(set_metafields)} metafield(s).")
    for mf in set_metafields:
        owner = mf.get("owner") or {}
        print(
            f"  id={mf['id']}  owner={owner.get('id')} "
            f"sku={owner.get('sku')} value={mf['value']!r}"
        )

    # 7. Verify by re-querying the product
    print("\nVerifying via re-query…")
    refreshed = fetch_product(api_url, headers, PRODUCT_HANDLE)
    refreshed_variants = {
        e["node"]["id"]: e["node"] for e in refreshed["variants"]["edges"]
    }

    print("\n=== Metafield transitions ===")
    all_ok = True
    for v in target_variants:
        vid = v["id"]
        b = before[vid]
        before_val = (b["metafield"] or {}).get("value")
        before_type = (b["metafield"] or {}).get("type")
        r = refreshed_variants.get(vid) or {}
        after_mf = r.get("metafield") or {}
        after_val = after_mf.get("value")
        after_type = after_mf.get("type")

        ok = after_val == TARGET_CDN_URL and after_type == METAFIELD_TYPE
        all_ok = all_ok and ok

        print(
            f"  SKU={b['sku']:<8} id={vid}"
            f"\n    before: type={before_type!r} value={before_val!r}"
            f"\n    after:  type={after_type!r} value={after_val!r}"
            f"\n    match target: {ok}"
        )

    if user_errors or not all_ok:
        print("\nFAILED: userErrors present or value mismatch after verification.")
        return 1

    print("\nAll Lilac variants now have the target color_swatch_image value.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
