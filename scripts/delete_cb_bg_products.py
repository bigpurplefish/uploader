#!/usr/bin/env python3
"""Archive Hardscaping products whose titles start with 'Cb-' or 'BG-'.

These are legacy imports with no Unit of Sale option — not sold by the square foot.
Sets status to ARCHIVED (hidden from storefront, reversible, inventory preserved).
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
PREFIXES = ("cb-", "bg-")

PRODUCTS_QUERY = """
query getProducts($cursor: String) {
  products(first: 100, after: $cursor, query: "product_type:'Landscape and Construction' AND tag:'Pavers and Hardscaping'") {
    pageInfo { hasNextPage endCursor }
    edges { node { id title handle status totalInventory } }
  }
}
"""

ARCHIVE_MUTATION = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id status }
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
        for e in conn["edges"]:
            yield e["node"]
        if not conn["pageInfo"]["hasNextPage"]:
            return
        cursor = conn["pageInfo"]["endCursor"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Archive Cb-/BG- Hardscaping products — mode: {mode}")

    targets = []
    for p in fetch_all_products(cfg):
        tl = p["title"].strip().lower()
        if any(tl.startswith(pfx) for pfx in PREFIXES):
            targets.append(p)

    print()
    print("=" * 70)
    print(f"PRODUCTS TO ARCHIVE: {len(targets)}")
    print("=" * 70)
    for p in targets:
        print(f"  {p['id']}  status={p.get('status','?'):<10} inv={p.get('totalInventory', '?'):<6}  {p['title']}")
    print()

    if args.report:
        with open(args.report, "w") as f:
            json.dump(targets, f, indent=2)
        log.info(f"Wrote target list to {args.report}")

    if not args.execute:
        print("DRY RUN — no changes made. Rerun with --execute to archive.")
        return 0

    if not targets:
        print("Nothing to archive.")
        return 0

    print(f"Archiving {len(targets)} products...")
    errors = []
    for i, p in enumerate(targets, 1):
        log.info(f"[{i}/{len(targets)}] Archiving {p['title']}")
        try:
            data = graphql(cfg, ARCHIVE_MUTATION, {"input": {"id": p["id"], "status": "ARCHIVED"}})
            user_errors = data["productUpdate"]["userErrors"]
            if user_errors:
                log.error(f"  userErrors: {user_errors}")
                errors.append({"product": p["title"], "errors": user_errors})
            else:
                new_status = data["productUpdate"]["product"]["status"]
                log.info(f"  OK (status={new_status})")
        except Exception as e:
            log.exception(f"  FAILED: {e}")
            errors.append({"product": p["title"], "error": str(e)})
        time.sleep(args.delay)

    print()
    if errors:
        print(f"COMPLETED WITH {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("COMPLETED SUCCESSFULLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
