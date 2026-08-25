#!/usr/bin/env python3
"""Create smart collections for brand vendors (vendor EQUALS rule).

Initial scope: Cambridge Pavers, Techo-Bloc.
Dry-run by default; pass --execute to create.
"""

import argparse
import json
import logging
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_VERSION = "2025-10"

BRANDS = [
    {"title": "Cambridge Pavers", "handle": "cambridge-pavers", "vendor": "Cambridge Pavers"},
    {"title": "Techo-Bloc",       "handle": "techo-bloc",       "vendor": "Techo-Bloc"},
]

EXISTING_QUERY = """
query findCollection($handle: String!) {
  collectionByHandle(handle: $handle) { id title handle }
}
"""

CREATE_MUTATION = """
mutation collectionCreate($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection { id title handle ruleSet { rules { column relation condition } } }
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Create brand smart collections — mode: {mode}")

    plan = []
    for brand in BRANDS:
        existing = graphql(cfg, EXISTING_QUERY, {"handle": brand["handle"]})["collectionByHandle"]
        if existing:
            plan.append({"brand": brand, "action": "skip", "reason": f"collection already exists: {existing['id']}"})
        else:
            plan.append({"brand": brand, "action": "create"})

    print()
    print("=" * 70)
    print("PLAN")
    print("=" * 70)
    for p in plan:
        b = p["brand"]
        if p["action"] == "skip":
            print(f"  SKIP   {b['title']:<20} ({b['handle']})  — {p['reason']}")
        else:
            print(f"  CREATE {b['title']:<20} ({b['handle']})  rule: vendor EQUALS {b['vendor']!r}")
    print()

    if not args.execute:
        print("DRY RUN — rerun with --execute to create collections.")
        return 0

    to_create = [p for p in plan if p["action"] == "create"]
    if not to_create:
        print("Nothing to create.")
        return 0

    pub_inputs = [{"publicationId": e["node"]["id"]} for e in graphql(cfg, PUBLICATIONS_QUERY)["publications"]["edges"]]
    log.info(f"Will publish each new collection to {len(pub_inputs)} sales channels")

    for p in to_create:
        b = p["brand"]
        log.info(f"Creating {b['title']}...")
        input_obj = {
            "title": b["title"],
            "handle": b["handle"],
            "ruleSet": {
                "appliedDisjunctively": False,
                "rules": [{"column": "VENDOR", "relation": "EQUALS", "condition": b["vendor"]}],
            },
        }
        data = graphql(cfg, CREATE_MUTATION, {"input": input_obj})
        ue = data["collectionCreate"]["userErrors"]
        if ue:
            log.error(f"  userErrors: {ue}")
            continue
        c = data["collectionCreate"]["collection"]
        log.info(f"  OK  {c['id']}  handle={c['handle']}")
        pub_data = graphql(cfg, PUBLISH_MUTATION, {"id": c["id"], "input": pub_inputs})
        pub_ue = pub_data["publishablePublish"]["userErrors"]
        if pub_ue:
            log.error(f"  publish userErrors: {pub_ue}")
        else:
            log.info(f"  Published to {len(pub_inputs)} channels")

    print("\nCOMPLETED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
