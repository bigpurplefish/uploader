#!/usr/bin/env python3
"""Set custom.hide_online_price=true on aggregate products that lack it.

Excludes any product explicitly listed in EXCLUDE_TITLES (mis-tagged non-aggregates).
Dry-run by default; --execute to apply.
"""
import argparse, logging, os, sys, time
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from uploader_modules.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
API_VERSION = "2025-10"

EXCLUDE_TITLES = {
    "Prestone Windshield De-Icer Aerosol Can",
}

FETCH_QUERY = """
query($cursor: String) {
  products(first: 100, after: $cursor, query: "tag:Aggregates") {
    pageInfo { hasNextPage endCursor }
    edges { node { id title metafield(namespace: "custom", key: "hide_online_price") { value } } }
  }
}
"""

SET_MUTATION = """
mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id key value }
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
    r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}}, headers=headers(cfg), timeout=60)
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        raise RuntimeError(d["errors"])
    return d["data"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    cfg = load_config()

    targets = []
    excluded = []
    already_set = []
    cursor = None
    while True:
        d = gql(cfg, FETCH_QUERY, {"cursor": cursor})
        for e in d["products"]["edges"]:
            n = e["node"]
            if n["metafield"] and n["metafield"]["value"] == "true":
                already_set.append(n["title"])
                continue
            if n["title"] in EXCLUDE_TITLES:
                excluded.append(n["title"])
                continue
            targets.append({"id": n["id"], "title": n["title"]})
        if not d["products"]["pageInfo"]["hasNextPage"]:
            break
        cursor = d["products"]["pageInfo"]["endCursor"]

    print()
    print("=" * 70)
    print(f"PLAN: set custom.hide_online_price=true on {len(targets)} products")
    print("=" * 70)
    print(f"Already set: {len(already_set)}  |  Excluded: {len(excluded)}  |  Will set: {len(targets)}")
    print()
    print("TARGETS:")
    for t in targets:
        print(f"  {t['title']}")
    if excluded:
        print(f"\nEXCLUDED (mis-tagged):")
        for t in excluded:
            print(f"  {t}")

    if not args.execute:
        print("\nDRY RUN — rerun with --execute.")
        return 0

    if not targets:
        print("Nothing to do.")
        return 0

    # Batch in chunks of 25 (Shopify metafieldsSet limit)
    errors = []
    for i in range(0, len(targets), 25):
        batch = targets[i:i+25]
        mfs = [{
            "ownerId": t["id"],
            "namespace": "custom",
            "key": "hide_online_price",
            "type": "boolean",
            "value": "true",
        } for t in batch]
        d = gql(cfg, SET_MUTATION, {"metafields": mfs})
        ue = d["metafieldsSet"]["userErrors"]
        if ue:
            log.error(f"  Batch {i} errors: {ue}")
            errors.append(ue)
        else:
            log.info(f"  Set {len(batch)} products (batch {i//25 + 1})")
        time.sleep(0.5)

    print()
    if errors:
        print(f"COMPLETED WITH ERRORS: {errors}")
        return 1
    print(f"COMPLETED: hide_online_price=true set on {len(targets)} products")
    return 0


if __name__ == "__main__":
    sys.exit(main())
