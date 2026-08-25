#!/usr/bin/env python3
"""READ-ONLY investigation script for duplicate products titled
'Flagstone Full Color Standing Irregulars' in the Garoppo's Shopify store.

Queries both products fully, dumps comparison JSON to
/tmp/flagstone_duplicates_investigation.json, and prints a human summary.

No mutations. No state changes.
"""

import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config

API_VERSION = "2025-10"
TITLE_QUERY = "Flagstone Full Color Standing Irregulars"
OUTPUT_PATH = "/tmp/flagstone_duplicates_investigation.json"


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


SEARCH_QUERY = """
query ProductsByTitle($query: String!) {
  products(first: 20, query: $query) {
    edges {
      node {
        id
        title
        handle
        status
        vendor
        productType
        tags
        createdAt
        updatedAt
        totalInventory
        onlineStoreUrl
        onlineStorePreviewUrl
        variantsCount { count }
        mediaCount { count }
      }
    }
  }
}
"""


PRODUCT_DETAIL_QUERY = """
query ProductDetail($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    status
    vendor
    productType
    tags
    createdAt
    updatedAt
    descriptionHtml
    totalInventory
    options {
      id
      name
      position
      values
    }
    variants(first: 250) {
      edges {
        node {
          id
          title
          sku
          barcode
          price
          compareAtPrice
          inventoryQuantity
          inventoryPolicy
          position
          selectedOptions { name value }
          image { id url altText }
          metafields(first: 30) {
            edges {
              node { namespace key type value }
            }
          }
          inventoryItem {
            id
            unitCost { amount currencyCode }
            measurement { weight { value unit } }
          }
        }
      }
    }
    media(first: 250) {
      edges {
        node {
          id
          alt
          mediaContentType
          status
          preview { image { url } }
          ... on MediaImage {
            image { url width height }
          }
          ... on Video {
            sources { url format mimeType }
          }
          ... on Model3d {
            sources { url format mimeType }
          }
        }
      }
    }
    metafields(first: 100) {
      edges {
        node { namespace key type value }
      }
    }
    resourcePublicationsV2(first: 20) {
      edges {
        node {
          isPublished
          publishDate
          publication { id name }
        }
      }
    }
  }
}
"""


def variant_option_key(variant):
    parts = []
    for opt in variant.get("selectedOptions", []):
        parts.append(f"{opt['name']}={opt['value']}")
    return " | ".join(parts)


def summarize_product(p):
    variants = [e["node"] for e in p["variants"]["edges"]]
    media = [e["node"] for e in p["media"]["edges"]]
    metafields = [e["node"] for e in p["metafields"]["edges"]]
    publications = [e["node"] for e in p["resourcePublicationsV2"]["edges"]]

    return {
        "id": p["id"],
        "title": p["title"],
        "handle": p["handle"],
        "status": p["status"],
        "vendor": p["vendor"],
        "productType": p["productType"],
        "tags": p["tags"],
        "createdAt": p["createdAt"],
        "updatedAt": p["updatedAt"],
        "totalInventory": p.get("totalInventory"),
        "options": p["options"],
        "variant_count": len(variants),
        "media_count": len(media),
        "image_count": sum(1 for m in media if m["mediaContentType"] == "IMAGE"),
        "model_count": sum(1 for m in media if m["mediaContentType"] == "MODEL_3D"),
        "video_count": sum(1 for m in media if m["mediaContentType"] in ("VIDEO", "EXTERNAL_VIDEO")),
        "variants": [
            {
                "id": v["id"],
                "title": v["title"],
                "sku": v["sku"],
                "barcode": v["barcode"],
                "price": v["price"],
                "compareAtPrice": v["compareAtPrice"],
                "inventoryQuantity": v["inventoryQuantity"],
                "inventoryPolicy": v["inventoryPolicy"],
                "position": v["position"],
                "selectedOptions": v["selectedOptions"],
                "option_key": variant_option_key(v),
                "image_url": (v["image"] or {}).get("url"),
                "image_alt": (v["image"] or {}).get("altText"),
                "unit_cost": (v.get("inventoryItem") or {}).get("unitCost"),
                "weight": ((v.get("inventoryItem") or {}).get("measurement") or {}).get("weight"),
                "metafields": [e["node"] for e in v["metafields"]["edges"]],
            }
            for v in variants
        ],
        "media": [
            {
                "id": m["id"],
                "alt": m["alt"],
                "mediaContentType": m["mediaContentType"],
                "status": m["status"],
                "image_url": (m.get("image") or {}).get("url") if m.get("image") else (m.get("preview", {}) or {}).get("image", {}).get("url"),
                "preview_url": (m.get("preview", {}) or {}).get("image", {}).get("url"),
                "sources": m.get("sources"),
            }
            for m in media
        ],
        "metafields": metafields,
        "publications": publications,
        "descriptionHtml_length": len(p.get("descriptionHtml") or ""),
        "descriptionHtml_preview": (p.get("descriptionHtml") or "")[:400],
    }


def diff_products(a, b):
    a_keys = {v["option_key"] for v in a["variants"]}
    b_keys = {v["option_key"] for v in b["variants"]}

    shared = sorted(a_keys & b_keys)
    only_a = sorted(a_keys - b_keys)
    only_b = sorted(b_keys - a_keys)

    # Per-shared variant comparison
    a_by_key = {v["option_key"]: v for v in a["variants"]}
    b_by_key = {v["option_key"]: v for v in b["variants"]}
    shared_detail = []
    for k in shared:
        av = a_by_key[k]
        bv = b_by_key[k]
        shared_detail.append({
            "option_key": k,
            "a": {"sku": av["sku"], "price": av["price"], "qty": av["inventoryQuantity"]},
            "b": {"sku": bv["sku"], "price": bv["price"], "qty": bv["inventoryQuantity"]},
            "same_sku": av["sku"] == bv["sku"],
            "same_price": av["price"] == bv["price"],
        })

    a_mf = {(m["namespace"], m["key"]): m for m in a["metafields"]}
    b_mf = {(m["namespace"], m["key"]): m for m in b["metafields"]}
    mf_only_a = sorted(a_mf.keys() - b_mf.keys())
    mf_only_b = sorted(b_mf.keys() - a_mf.keys())
    mf_shared_diff = []
    for k in a_mf.keys() & b_mf.keys():
        if a_mf[k]["value"] != b_mf[k]["value"]:
            mf_shared_diff.append({
                "namespace_key": list(k),
                "a_value": (a_mf[k]["value"] or "")[:200],
                "b_value": (b_mf[k]["value"] or "")[:200],
            })

    return {
        "variant_option_keys_shared": shared,
        "variant_option_keys_only_in_a": only_a,
        "variant_option_keys_only_in_b": only_b,
        "shared_variant_comparison": shared_detail,
        "metafields_only_in_a": [list(k) for k in mf_only_a],
        "metafields_only_in_b": [list(k) for k in mf_only_b],
        "metafields_shared_but_differ": mf_shared_diff,
        "options_match": a["options"] == b["options"],
    }


def main():
    cfg = load_config()
    store = cfg["SHOPIFY_STORE_URL"].replace("https://", "").replace("http://", "").rstrip("/")
    token = cfg["SHOPIFY_ACCESS_TOKEN"]
    url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}

    print(f"Store: {store}")
    print(f"Searching for products titled: {TITLE_QUERY!r}")

    # Try several search variations; Shopify title search is loose
    queries_to_try = [
        f'title:"{TITLE_QUERY}"',
        f'title:*{TITLE_QUERY}*',
        'title:"Standing Irregulars"',
        'title:Flagstone AND title:Standing AND title:Irregulars',
        'Flagstone Full Color Standing Irregulars',
    ]
    edges = []
    for q in queries_to_try:
        print(f"  trying query: {q!r}")
        search = gql(url, headers, SEARCH_QUERY, {"query": q})
        these = search["products"]["edges"]
        print(f"    -> {len(these)} hits")
        if these:
            edges = these
            break
    matches = [e["node"] for e in edges if TITLE_QUERY.lower() in e["node"]["title"].strip().lower()]
    print(f"Loose-title matches containing {TITLE_QUERY!r}: {len(matches)} (total query hits: {len(edges)})")
    for m in matches:
        print(f"  - {m['id']}  handle={m['handle']}  status={m['status']}  created={m['createdAt']}  variants={m['variantsCount']['count']}  media={m['mediaCount']['count']}")

    if len(matches) < 2:
        print("\nFewer than 2 duplicates found. Dumping all hits for debug.")
        for e in edges:
            n = e["node"]
            print(f"  hit: {n['id']}  title={n['title']!r}")
        # Continue if we have at least one to inspect
        if not matches:
            return

    # Fetch full detail on up to 2 matches (or more if user has more)
    products = []
    for m in matches[:2]:
        detail = gql(url, headers, PRODUCT_DETAIL_QUERY, {"id": m["id"]})
        products.append(summarize_product(detail["product"]))

    report = {
        "store": store,
        "query_title": TITLE_QUERY,
        "matches_found": len(matches),
        "products": products,
    }
    if len(products) == 2:
        report["diff"] = diff_products(products[0], products[1])

    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote full report to {OUTPUT_PATH}")

    if len(products) < 2:
        return

    a, b = products[0], products[1]
    print("\n=== PRODUCT A ===")
    print(f"  id={a['id']}")
    print(f"  handle={a['handle']}  status={a['status']}")
    print(f"  createdAt={a['createdAt']}  updatedAt={a['updatedAt']}")
    print(f"  vendor={a['vendor']}  productType={a['productType']}")
    print(f"  tags={a['tags']}")
    print(f"  options={[(o['name'], o['values']) for o in a['options']]}")
    print(f"  variants={a['variant_count']}  media={a['media_count']} (images={a['image_count']}, 3d={a['model_count']}, video={a['video_count']})")
    print(f"  metafield_count={len(a['metafields'])}")
    print(f"  publications={[(p['publication']['name'], p['isPublished']) for p in a['publications']]}")
    print(f"  description_len={a['descriptionHtml_length']}")

    print("\n=== PRODUCT B ===")
    print(f"  id={b['id']}")
    print(f"  handle={b['handle']}  status={b['status']}")
    print(f"  createdAt={b['createdAt']}  updatedAt={b['updatedAt']}")
    print(f"  vendor={b['vendor']}  productType={b['productType']}")
    print(f"  tags={b['tags']}")
    print(f"  options={[(o['name'], o['values']) for o in b['options']]}")
    print(f"  variants={b['variant_count']}  media={b['media_count']} (images={b['image_count']}, 3d={b['model_count']}, video={b['video_count']})")
    print(f"  metafield_count={len(b['metafields'])}")
    print(f"  publications={[(p['publication']['name'], p['isPublished']) for p in b['publications']]}")
    print(f"  description_len={b['descriptionHtml_length']}")

    d = report["diff"]
    print("\n=== DIFF ===")
    print(f"  options_match: {d['options_match']}")
    print(f"  shared variant option keys ({len(d['variant_option_keys_shared'])}): {d['variant_option_keys_shared']}")
    print(f"  only in A ({len(d['variant_option_keys_only_in_a'])}): {d['variant_option_keys_only_in_a']}")
    print(f"  only in B ({len(d['variant_option_keys_only_in_b'])}): {d['variant_option_keys_only_in_b']}")
    print(f"  metafields_only_in_a: {d['metafields_only_in_a']}")
    print(f"  metafields_only_in_b: {d['metafields_only_in_b']}")
    if d["metafields_shared_but_differ"]:
        print(f"  metafields_shared_but_differ: {len(d['metafields_shared_but_differ'])} keys with diff values")
    print("\nShared variant detail:")
    for s in d["shared_variant_comparison"]:
        print(f"  {s['option_key']}: A(sku={s['a']['sku']},price={s['a']['price']},qty={s['a']['qty']}) vs B(sku={s['b']['sku']},price={s['b']['price']},qty={s['b']['qty']})  same_sku={s['same_sku']} same_price={s['same_price']}")


if __name__ == "__main__":
    main()
