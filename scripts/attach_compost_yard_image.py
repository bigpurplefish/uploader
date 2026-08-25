#!/usr/bin/env python3
"""
Re-attach the original Compost upscale image to the `Per Cubic Yard` variant.

Context:
  reshape_compost_variants.py (Apr 21 AM) reshaped compost into 2 variants,
  which destroyed the old variant GIDs. upload_compost_50lb_image.py then
  deleted the original MediaImage and attached a new scene render to the
  `50 LB Bag` variant only. The `Per Cubic Yard` variant was left with no
  image. This script restores it.

  The original upscale file (29895d43-...png) is still live on Shopify CDN
  — only its MediaImage record was deleted, not the underlying File.

Pipeline:
  1. productCreateMedia with originalSource = old CDN URL,
     alt = "Compost #Per Cubic Yard".
  2. Poll product.media until the new MediaImage is READY.
  3. productVariantAppendMedia for the Per Cubic Yard variant.
  4. metafieldsSet custom.color_swatch_image on the Per Cubic Yard variant
     with the CDN URL.

Usage:
    python attach_compost_yard_image.py --dry-run
    python attach_compost_yard_image.py
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
API_VERSION = "2025-10"

PRODUCT_GID = "gid://shopify/Product/10368015204644"
YARD_VARIANT_GID = "gid://shopify/ProductVariant/53342600790308"
YARD_VARIANT_SKU = "18163-01"
YARD_OPTION_VALUE = "Per Cubic Yard"

IMAGE_URL = (
    "https://cdn.shopify.com/s/files/1/0968/5322/9860/files/"
    "garoppo-s-stone-garden-and-feed-pet-supply_compost_18163_18163_"
    "compost_upscale_29895d43-60d1-4bc3-ae64-044498ec4109.png"
)
IMAGE_ALT = "Compost #Per Cubic Yard"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"

POLL_TIMEOUT = 60
POLL_INTERVAL = 2


def load_cfg():
    cfg = json.loads(CONFIG_PATH.read_text())
    store = cfg["SHOPIFY_STORE_URL"].replace("https://", "").replace("http://", "").rstrip("/")
    return store, cfg["SHOPIFY_ACCESS_TOKEN"]


def gql(store, token, query, variables=None):
    req = urllib.request.Request(
        f"https://{store}/admin/api/{API_VERSION}/graphql.json",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
    )
    with urllib.request.urlopen(req) as r:
        body = json.loads(r.read())
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]


def verify_state(store, token):
    q = """
    query($id: ID!) {
      product(id: $id) {
        id
        title
        variants(first: 10) {
          nodes {
            id sku title selectedOptions { name value } image { url }
          }
        }
      }
    }
    """
    data = gql(store, token, q, {"id": PRODUCT_GID})
    p = data["product"]
    if p is None:
        raise SystemExit("Product not found")
    print(f"Product: {p['title']} ({p['id']})")
    yard = next((v for v in p["variants"]["nodes"] if v["id"] == YARD_VARIANT_GID), None)
    if yard is None:
        raise SystemExit(f"Expected variant {YARD_VARIANT_GID} not found")
    if yard["sku"] != YARD_VARIANT_SKU:
        raise SystemExit(f"SKU mismatch: {yard['sku']} != {YARD_VARIANT_SKU}")
    if yard["image"] is not None:
        print(f"NOTE: Per Cubic Yard already has image {yard['image']['url']}")
    else:
        print("Per Cubic Yard: image=null (will be fixed)")
    return yard


def create_media(store, token):
    q = """
    mutation($productId: ID!, $media: [CreateMediaInput!]!) {
      productCreateMedia(productId: $productId, media: $media) {
        media { ... on MediaImage { id alt status } }
        mediaUserErrors { field message code }
      }
    }
    """
    data = gql(store, token, q, {
        "productId": PRODUCT_GID,
        "media": [{"originalSource": IMAGE_URL, "mediaContentType": "IMAGE", "alt": IMAGE_ALT}],
    })
    res = data["productCreateMedia"]
    if res["mediaUserErrors"]:
        raise RuntimeError(f"mediaUserErrors: {res['mediaUserErrors']}")
    m = res["media"][0]
    print(f"Created media {m['id']} status={m['status']}")
    return m["id"]


def poll_ready(store, token, media_id):
    q = """
    query($id: ID!) {
      product(id: $id) {
        media(first: 50) {
          nodes { ... on MediaImage { id status image { url } } }
        }
      }
    }
    """
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        data = gql(store, token, q, {"id": PRODUCT_GID})
        for node in data["product"]["media"]["nodes"]:
            if node and node.get("id") == media_id and node.get("status") == "READY":
                url = node["image"]["url"]
                print(f"Media READY: {url}")
                return url
        time.sleep(POLL_INTERVAL)
    raise RuntimeError("Media did not become READY in time")


def append_to_variant(store, token, media_id):
    q = """
    mutation($productId: ID!, $variantMedia: [ProductVariantAppendMediaInput!]!) {
      productVariantAppendMedia(productId: $productId, variantMedia: $variantMedia) {
        productVariants { id image { url } }
        userErrors { field message }
      }
    }
    """
    data = gql(store, token, q, {
        "productId": PRODUCT_GID,
        "variantMedia": [{"variantId": YARD_VARIANT_GID, "mediaIds": [media_id]}],
    })
    res = data["productVariantAppendMedia"]
    if res["userErrors"]:
        raise RuntimeError(f"userErrors: {res['userErrors']}")
    v = res["productVariants"][0]
    print(f"Variant image now: {v['image']['url']}")


def set_metafield(store, token, cdn_url):
    q = """
    mutation($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields { id namespace key value }
        userErrors { field message }
      }
    }
    """
    data = gql(store, token, q, {
        "metafields": [{
            "ownerId": YARD_VARIANT_GID,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "type": METAFIELD_TYPE,
            "value": cdn_url,
        }],
    })
    res = data["metafieldsSet"]
    if res["userErrors"]:
        raise RuntimeError(f"userErrors: {res['userErrors']}")
    mf = res["metafields"][0]
    print(f"Metafield set: {mf['namespace']}.{mf['key']} = {mf['value']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    store, token = load_cfg()
    yard = verify_state(store, token)

    if args.dry_run:
        print("\n[dry-run] Would:")
        print(f"  1. productCreateMedia({IMAGE_URL!r}, alt={IMAGE_ALT!r})")
        print(f"  2. Poll READY")
        print(f"  3. productVariantAppendMedia -> {YARD_VARIANT_GID}")
        print(f"  4. metafieldsSet {METAFIELD_NAMESPACE}.{METAFIELD_KEY} on variant")
        return

    media_id = create_media(store, token)
    cdn_url = poll_ready(store, token, media_id)
    append_to_variant(store, token, media_id)
    set_metafield(store, token, cdn_url)

    print("\nVerification:")
    verify_state(store, token)


if __name__ == "__main__":
    main()
