#!/usr/bin/env python3
"""
Upload and attach 50 LB Bag product images for River Rock Stone variants.

For each of the 4 bag variants (3/8", 3/4", 1-1/2", 1-3"), this script:
  1. stagedUploadsCreate (IMAGE) + POST bytes to staged target.
  2. productCreateMedia with alt = "River rock stone, SIZE_DESC. #SIZE#50 LB Bag".
  3. Poll product.media until READY, capture CDN URL.
  4. productVariantAppendMedia attaches media to the bag variant.
  5. metafieldsSet custom.color_swatch_image (single_line_text_field) on variant.

Usage:
    python attach_river_rock_bag_images.py --dry-run
    python attach_river_rock_bag_images.py
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

import requests

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
API_VERSION = "2025-10"
PRODUCT_GID = "gid://shopify/Product/10368017137956"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"

POLL_TIMEOUT = 90
POLL_INTERVAL = 2

# (size_label, size_slug, desc_for_alt, variant_gid, sku, generated_image_path)
VARIANTS = [
    (
        '3/8"', "3-8",
        "3/8 inch size",
        "gid://shopify/ProductVariant/53321860022500",
        "24614-02",
        "/tmp/garoppos_product_images/river_rock/rr_3-8_processed.png",
    ),
    (
        '3/4"', "3-4",
        "3/4 inch size",
        "gid://shopify/ProductVariant/53321860055268",
        "24626-02",
        "/tmp/garoppos_product_images/river_rock/rr_3-4_processed.png",
    ),
    (
        '1-1/2"', "1-1-2",
        "1-1/2 inch size",
        "gid://shopify/ProductVariant/53321860088036",
        "24628-02",
        "/tmp/garoppos_product_images/river_rock/rr_1-1-2_processed.png",
    ),
    (
        '1-3"', "1-3",
        "between 1 and 3 inches",
        "gid://shopify/ProductVariant/53321860120804",
        "24629-02",
        "/tmp/garoppos_product_images/river_rock/rr_1-3_processed.png",
    ),
]


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


def verify_variants(store, token):
    q = """
    query($id: ID!) {
      product(id: $id) {
        title
        variants(first: 50) {
          nodes { id sku selectedOptions { name value } image { url } }
        }
      }
    }
    """
    data = gql(store, token, q, {"id": PRODUCT_GID})
    by_sku = {v["sku"]: v for v in data["product"]["variants"]["nodes"]}
    print(f"Product: {data['product']['title']}")
    resolved = []
    for size_label, slug, desc, expected_gid, sku, img_path in VARIANTS:
        v = by_sku.get(sku)
        if v is None:
            raise SystemExit(f"Variant sku {sku} not found")
        # Re-resolve GID in case of reshape history; prefer actual
        if v["id"] != expected_gid:
            print(f"  NOTE: {sku} GID is {v['id']}, expected {expected_gid} -- using actual")
        resolved.append((size_label, slug, desc, v["id"], sku, img_path, v["image"]))
        print(f"  {sku} {size_label} current image: {v['image']['url'] if v['image'] else None}")
    return resolved


def staged_upload(store, token, img_path):
    q = """
    mutation($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets { url resourceUrl parameters { name value } }
        userErrors { field message }
      }
    }
    """
    name = Path(img_path).name
    size = Path(img_path).stat().st_size
    data = gql(store, token, q, {
        "input": [{
            "filename": name,
            "mimeType": "image/png",
            "resource": "IMAGE",
            "httpMethod": "POST",
            "fileSize": str(size),
        }],
    })
    res = data["stagedUploadsCreate"]
    if res["userErrors"]:
        raise RuntimeError(f"staged userErrors: {res['userErrors']}")
    t = res["stagedTargets"][0]
    # POST bytes
    files = {"file": (name, Path(img_path).read_bytes(), "image/png")}
    fields = {p["name"]: p["value"] for p in t["parameters"]}
    resp = requests.post(t["url"], data=fields, files=files, timeout=120)
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"staged POST failed {resp.status_code}: {resp.text[:400]}")
    return t["resourceUrl"]


def create_media(store, token, resource_url, alt):
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
        "media": [{"originalSource": resource_url, "mediaContentType": "IMAGE", "alt": alt}],
    })
    res = data["productCreateMedia"]
    if res["mediaUserErrors"]:
        raise RuntimeError(f"mediaUserErrors: {res['mediaUserErrors']}")
    return res["media"][0]["id"]


def poll_ready(store, token, media_id):
    q = """
    query($id: ID!) {
      product(id: $id) {
        media(first: 60) {
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
                return node["image"]["url"]
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"Media {media_id} did not become READY")


def append_to_variant(store, token, variant_gid, media_id):
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
        "variantMedia": [{"variantId": variant_gid, "mediaIds": [media_id]}],
    })
    res = data["productVariantAppendMedia"]
    if res["userErrors"]:
        raise RuntimeError(f"userErrors: {res['userErrors']}")


def set_metafield(store, token, variant_gid, cdn_url):
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
            "ownerId": variant_gid,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "type": METAFIELD_TYPE,
            "value": cdn_url,
        }],
    })
    res = data["metafieldsSet"]
    if res["userErrors"]:
        raise RuntimeError(f"userErrors: {res['userErrors']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    store, token = load_cfg()
    resolved = verify_variants(store, token)

    # Preflight: confirm all 4 images exist
    missing = [(r[4], r[5]) for r in resolved if not Path(r[5]).exists()]
    if missing:
        print("\nMISSING images:")
        for sku, p in missing:
            print(f"  {sku}: {p}")
        raise SystemExit("Generate images first.")

    print("\nAll 4 generated images present.")
    for size_label, slug, desc, variant_gid, sku, img_path, _ in resolved:
        print(f"  {sku} {size_label} -> {img_path} ({Path(img_path).stat().st_size} bytes)")

    if args.dry_run:
        print("\n[dry-run] Would upload + attach 4 images. Exiting.")
        return

    for size_label, slug, desc, variant_gid, sku, img_path, _ in resolved:
        alt = f"River rock stone, {desc}. #{size_label}#50 LB Bag"
        print(f"\n--- {sku} {size_label} ---")
        print(f"  staged upload...")
        resource_url = staged_upload(store, token, img_path)
        print(f"  resourceUrl obtained")
        print(f"  productCreateMedia alt={alt!r}")
        media_id = create_media(store, token, resource_url, alt)
        print(f"  media_id={media_id}")
        cdn_url = poll_ready(store, token, media_id)
        print(f"  READY: {cdn_url}")
        append_to_variant(store, token, variant_gid, media_id)
        print(f"  attached to variant {variant_gid}")
        set_metafield(store, token, variant_gid, cdn_url)
        print(f"  color_swatch_image metafield set")

    print("\n=== Verification ===")
    verify_variants(store, token)


if __name__ == "__main__":
    main()
