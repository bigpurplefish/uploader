#!/usr/bin/env python3
"""Rename product 10429334028580 from 'PA Flagstone Full Color Standing Irregulars'
to 'Lilac Standing Irregulars' (handle: lilac-standing-irregulars).

Uses productUpdate on Shopify Admin API 2025-10.
Shopify auto-creates a URL redirect from the old handle to the new handle.
"""

import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config

API_VERSION = "2025-10"
PRODUCT_ID = "gid://shopify/Product/10429334028580"
NEW_TITLE = "Lilac Standing Irregulars"
NEW_HANDLE = "lilac-standing-irregulars"


def gql(url, headers, query, variables=None):
    resp = requests.post(
        url,
        headers=headers,
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


READ_QUERY = """
query GetProduct($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    onlineStoreUrl
  }
}
"""

UPDATE_MUTATION = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      onlineStoreUrl
    }
    userErrors {
      field
      message
    }
  }
}
"""

REDIRECT_QUERY = """
query FindRedirect($query: String!) {
  urlRedirects(first: 5, query: $query) {
    edges {
      node {
        id
        path
        target
      }
    }
  }
}
"""


def main():
    cfg = load_config()
    store = cfg.get("SHOPIFY_STORE_URL")
    token = cfg.get("SHOPIFY_ACCESS_TOKEN")
    if not store or not token:
        print("ERROR: Missing SHOPIFY_STORE_URL or SHOPIFY_ACCESS_TOKEN in config.json")
        sys.exit(1)

    # SHOPIFY_STORE_URL may or may not include a scheme; normalize.
    host = store.replace("https://", "").replace("http://", "").rstrip("/")
    url = f"https://{host}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }

    # 1) Read current state
    before = gql(url, headers, READ_QUERY, {"id": PRODUCT_ID})["product"]
    if before is None:
        print(f"ERROR: Product {PRODUCT_ID} not found")
        sys.exit(1)
    old_title = before["title"]
    old_handle = before["handle"]
    print(f"BEFORE: title={old_title!r} handle={old_handle!r}")

    # 2) Update
    res = gql(
        url,
        headers,
        UPDATE_MUTATION,
        {"input": {"id": PRODUCT_ID, "title": NEW_TITLE, "handle": NEW_HANDLE}},
    )["productUpdate"]
    if res.get("userErrors"):
        print(f"ERROR: userErrors: {res['userErrors']}")
        sys.exit(1)
    updated = res["product"]
    print(f"AFTER:  title={updated['title']!r} handle={updated['handle']!r}")

    # 3) Verify via re-read
    after = gql(url, headers, READ_QUERY, {"id": PRODUCT_ID})["product"]
    ok = after["title"] == NEW_TITLE and after["handle"] == NEW_HANDLE
    print(f"VERIFY: title_match={after['title'] == NEW_TITLE} handle_match={after['handle'] == NEW_HANDLE}")

    # 4) Check for auto-created redirect
    redirect_path = f"/products/{old_handle}"
    redirects = gql(
        url, headers, REDIRECT_QUERY, {"query": f"path:{redirect_path}"}
    )["urlRedirects"]["edges"]
    redirect_found = False
    for edge in redirects:
        node = edge["node"]
        if node["path"] == redirect_path:
            print(f"REDIRECT: {node['path']} -> {node['target']} (id={node['id']})")
            redirect_found = True
            break
    if not redirect_found:
        print(f"REDIRECT: NOT FOUND for {redirect_path} (may take a moment to appear)")

    result = {
        "product_id": PRODUCT_ID,
        "before": {"title": old_title, "handle": old_handle},
        "after": {"title": after["title"], "handle": after["handle"]},
        "online_store_url": after.get("onlineStoreUrl"),
        "verified": ok,
        "redirect_found": redirect_found,
    }
    print(json.dumps(result, indent=2))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
