#!/usr/bin/env python3
"""Rename the `vendor` field on all Shopify products matching one or more
literal vendor strings to a single target vendor string.

Usage:
  python3 scripts/rename_vendor.py \
      --from "Old Vendor A" \
      --from "Old Vendor B" \
      --to   "New Vendor Consolidated" \
      [--execute]

Without --execute: dry-run (counts + first-10 preview + summary).
With --execute: paginate matching products, call productUpdate per product,
check userErrors, and verify post-condition via productsCount.

Shopify's `vendor:` search operator is case-insensitive. This script uses that
operator to locate candidates, but filters the result set locally against the
EXACT literal vendor string(s) supplied via --from to avoid unintended matches.
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
PAGE_SIZE = 100  # productUpdate is the bottleneck; paginate small
DELAY_SEC = 0.08  # ~80ms between update calls

COUNT_Q = """
query($q: String!) {
  productsCount(query: $q) { count }
}
"""

LIST_Q = """
query($q: String!, $cursor: String, $size: Int!) {
  products(first: $size, query: $q, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges { node { id title vendor } }
  }
}
"""

UPDATE_MUT = """
mutation($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product { id vendor }
    userErrors { field message }
  }
}
"""


def api_url(cfg):
    s = cfg["SHOPIFY_STORE_URL"].replace("https://", "").replace("http://", "").strip("/")
    return f"https://{s}/admin/api/{API_VERSION}/graphql.json"


def headers(cfg):
    return {"Content-Type": "application/json",
            "X-Shopify-Access-Token": cfg["SHOPIFY_ACCESS_TOKEN"]}


def gql(cfg, q, v=None, retries=5):
    for _ in range(retries):
        r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}},
                          headers=headers(cfg), timeout=60)
        r.raise_for_status()
        d = r.json()
        if "errors" in d:
            if any("THROTTLED" in str(e).upper() for e in d["errors"]):
                time.sleep(2); continue
            raise RuntimeError(f"GraphQL errors: {d['errors']}")
        return d["data"]
    raise RuntimeError("retries exhausted")


def shopify_quote(s):
    """Wrap a search-operator value in single quotes, escaping any embedded
    single quotes. Shopify search uses \\' to escape internal quotes."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def count_vendor(cfg, vendor):
    return gql(cfg, COUNT_Q, {"q": f"vendor:{shopify_quote(vendor)}"})["productsCount"]["count"]


def collect_products_by_vendor(cfg, vendor):
    """Paginate and return products where literal vendor == vendor (case-sensitive)."""
    out = []
    cursor = None
    while True:
        d = gql(cfg, LIST_Q, {
            "q": f"vendor:{shopify_quote(vendor)}",
            "cursor": cursor,
            "size": PAGE_SIZE,
        })
        for e in d["products"]["edges"]:
            n = e["node"]
            # Local case-sensitive filter — Shopify search is case-insensitive
            if n["vendor"] == vendor:
                out.append(n)
        pi = d["products"]["pageInfo"]
        if not pi["hasNextPage"]:
            break
        cursor = pi["endCursor"]
        time.sleep(0.1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_vendors", action="append", required=True,
                    help="Source vendor literal (can be passed multiple times)")
    ap.add_argument("--to", dest="to_vendor", required=True,
                    help="Target vendor literal")
    ap.add_argument("--execute", action="store_true",
                    help="Apply changes. Without this flag, dry-run only.")
    args = ap.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Rename vendor — from={args.from_vendors} to={args.to_vendor!r}  mode={mode}")

    # Pre-count each source and the target
    print("\n" + "=" * 72)
    print("PRE-COUNT (case-insensitive search, filtered to case-sensitive matches)")
    print("=" * 72)
    source_products = {}
    total_to_update = 0
    for v in args.from_vendors:
        case_insens = count_vendor(cfg, v)
        exact = collect_products_by_vendor(cfg, v)
        print(f"  FROM {v!r}")
        print(f"    case-insensitive count: {case_insens}")
        print(f"    exact-match count:      {len(exact)}")
        source_products[v] = exact
        total_to_update += len(exact)
    target_pre = count_vendor(cfg, args.to_vendor)
    print(f"  TO   {args.to_vendor!r}")
    print(f"    current count:          {target_pre}")
    print(f"\n  TOTAL TO UPDATE: {total_to_update}")

    # Preview
    print("\nSample first 10:")
    shown = 0
    for v, prods in source_products.items():
        for p in prods:
            if shown >= 10: break
            print(f"  {p['id']}  title={p['title']!r:<55}  current_vendor={p['vendor']!r}")
            shown += 1

    if not args.execute:
        print("\nDRY RUN — rerun with --execute to apply.")
        return 0

    if total_to_update == 0:
        log.info("Nothing to update.")
        return 0

    # --- Execute ---
    print("\n" + "=" * 72)
    print("EXECUTING productUpdate per product")
    print("=" * 72)
    ok_by_vendor = {v: 0 for v in args.from_vendors}
    errors = []
    processed = 0
    for v, prods in source_products.items():
        for p in prods:
            processed += 1
            res = gql(cfg, UPDATE_MUT, {"product": {"id": p["id"], "vendor": args.to_vendor}})
            ue = res["productUpdate"]["userErrors"]
            if ue:
                errors.append({"id": p["id"], "title": p["title"], "from_vendor": v, "errors": ue})
                log.error(f"  [{processed}/{total_to_update}] ERR  {p['id']}  {p['title']!r}  ue={ue}")
            else:
                ok_by_vendor[v] += 1
                if processed <= 5 or processed % 50 == 0 or processed == total_to_update:
                    log.info(f"  [{processed}/{total_to_update}] OK   {p['id']}  vendor={args.to_vendor!r}")
            time.sleep(DELAY_SEC)

    # --- Verify ---
    print("\n" + "=" * 72)
    print("VERIFY")
    print("=" * 72)
    # Re-count each source and target
    after_counts_from = {v: count_vendor(cfg, v) for v in args.from_vendors}
    after_count_to = count_vendor(cfg, args.to_vendor)
    expected_to_increase = total_to_update - len(errors)
    print(f"After counts:")
    for v, c in after_counts_from.items():
        status = "[OK — 0]" if c == 0 else f"[DRIFT — expected 0 but got {c}]"
        print(f"  FROM {v!r}: {c}  {status}")
    print(f"  TO   {args.to_vendor!r}: {after_count_to}  (was {target_pre}, delta={after_count_to - target_pre}, expected delta={expected_to_increase})")

    # Summary
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for v, prods in source_products.items():
        n_ok = ok_by_vendor[v]
        print(f"  {v!r} -> {args.to_vendor!r}: {n_ok}/{len(prods)} updated")
    print(f"  TOTAL updated: {sum(ok_by_vendor.values())}/{total_to_update}")
    print(f"  Errors: {len(errors)}")
    if errors:
        print("\nError details:")
        for e in errors:
            print(f"  {e['id']}  title={e['title']!r}  from={e['from_vendor']!r}  errors={e['errors']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
