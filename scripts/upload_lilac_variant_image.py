#!/usr/bin/env python3
"""
Upload a new canonical product image for the "Retail Pack Standing Irregulars" product
and link it to every Lilac variant.

Steps:
  1. Load Shopify credentials from uploader/config.json.
  2. Look up product by handle (retail-pack-standing-irregulars) via GraphQL.
  3. Filter variants where the color option value == "Lilac".
  4. Stage the PNG upload (stagedUploadsCreate IMAGE), POST bytes to target.
  5. Attach via productCreateMedia, poll until MediaImage is READY.
  6. Link the new MediaImage to every Lilac variant via productVariantAppendMedia.
  7. Re-query and confirm each targeted variant now shows the new image id.

Usage:
    python upload_lilac_variant_image.py --dry-run
    python upload_lilac_variant_image.py

Hard constraints enforced by this script:
  - Uses Shopify GraphQL API 2025-10.
  - Only touches variants whose color option == "Lilac".
  - Does NOT delete existing media.
  - STOPs if zero Lilac variants match or color option cannot be identified.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # uploader/
CONFIG_PATH = REPO_ROOT / "config.json"
IMAGE_PATH = "/tmp/garoppos_product_images/40971_processed.png"
PRODUCT_HANDLE = "retail-pack-standing-irregulars"
TARGET_COLOR = "Lilac"
IMAGE_ALT = "PA Flagstone Lilac Standing Irregulars"
API_VERSION = "2025-10"
READY_POLL_TIMEOUT = 60  # seconds
READY_POLL_INTERVAL = 2  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    store = cfg.get("SHOPIFY_STORE_URL", "").replace("https://", "").replace("http://", "").strip().rstrip("/")
    token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()
    if not store or not token:
        sys.exit("ERROR: SHOPIFY_STORE_URL or SHOPIFY_ACCESS_TOKEN missing from config.json")
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
        raise RuntimeError(f"GraphQL errors: {json.dumps(result['errors'], indent=2)}")
    return result["data"]


# ---------------------------------------------------------------------------
# Product + variant lookup
# ---------------------------------------------------------------------------

PRODUCT_QUERY = """
query getProductByHandle($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    vendor
    options { id name position values }
    variants(first: 250) {
      edges {
        node {
          id
          sku
          title
          selectedOptions { name value }
          image { id url altText }
        }
      }
    }
  }
}
"""


def fetch_product(api_url, headers, handle):
    data = gql(api_url, headers, PRODUCT_QUERY, {"handle": handle})
    product = data.get("productByHandle")
    if not product:
        sys.exit(f"ERROR: Product with handle '{handle}' not found.")
    return product


def find_color_option_name(product):
    """Return the option name that represents color. Matches 'color' case-insensitively."""
    for opt in product.get("options", []):
        if "color" in opt["name"].lower():
            return opt["name"]
    return None


def filter_lilac_variants(product, color_option_name):
    matches = []
    for edge in product["variants"]["edges"]:
        v = edge["node"]
        for sel in v["selectedOptions"]:
            if sel["name"] == color_option_name and sel["value"].strip().lower() == TARGET_COLOR.lower():
                matches.append(v)
                break
    return matches


# ---------------------------------------------------------------------------
# Staged upload + productCreateMedia
# ---------------------------------------------------------------------------

STAGED_UPLOAD_MUTATION = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets {
      url
      resourceUrl
      parameters { name value }
    }
    userErrors { field message }
  }
}
"""

PRODUCT_CREATE_MEDIA_MUTATION = """
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media {
      ... on MediaImage {
        id
        status
        alt
        image { id url }
        mediaContentType
      }
    }
    mediaUserErrors { field message }
    userErrors { field message }
  }
}
"""

PRODUCT_MEDIA_POLL_QUERY = """
query productMedia($id: ID!) {
  product(id: $id) {
    media(first: 100, sortKey: ID, reverse: true) {
      edges {
        node {
          ... on MediaImage {
            id
            status
            alt
            image { id url }
            mediaContentType
          }
        }
      }
    }
  }
}
"""


def stage_upload(api_url, headers, file_path):
    file_bytes = Path(file_path).read_bytes()
    file_size = len(file_bytes)
    filename = Path(file_path).name
    variables = {
        "input": [
            {
                "resource": "IMAGE",
                "filename": filename,
                "mimeType": "image/png",
                "fileSize": str(file_size),
                "httpMethod": "POST",
            }
        ]
    }
    data = gql(api_url, headers, STAGED_UPLOAD_MUTATION, variables)
    staged = data["stagedUploadsCreate"]
    if staged["userErrors"]:
        sys.exit(f"ERROR: stagedUploadsCreate userErrors: {staged['userErrors']}")
    target = staged["stagedTargets"][0]
    return target, file_bytes, filename


def upload_bytes_to_target(target, file_bytes, filename):
    params = {p["name"]: p["value"] for p in target["parameters"]}
    files = {"file": (filename, file_bytes, "image/png")}
    resp = requests.post(target["url"], data=params, files=files, timeout=180)
    resp.raise_for_status()


def create_media_on_product(api_url, headers, product_id, resource_url, alt):
    variables = {
        "productId": product_id,
        "media": [
            {
                "originalSource": resource_url,
                "alt": alt,
                "mediaContentType": "IMAGE",
            }
        ],
    }
    data = gql(api_url, headers, PRODUCT_CREATE_MEDIA_MUTATION, variables, timeout=120)
    payload = data["productCreateMedia"]
    if payload.get("userErrors"):
        sys.exit(f"ERROR: productCreateMedia userErrors: {payload['userErrors']}")
    if payload.get("mediaUserErrors"):
        sys.exit(f"ERROR: productCreateMedia mediaUserErrors: {payload['mediaUserErrors']}")
    media = payload.get("media", [])
    if not media:
        sys.exit("ERROR: productCreateMedia returned no media")
    return media[0]


def poll_media_ready(api_url, headers, product_id, media_id):
    """Poll the product's media connection until the target media node has status READY."""
    start = time.time()
    last_status = None
    while time.time() - start < READY_POLL_TIMEOUT:
        data = gql(api_url, headers, PRODUCT_MEDIA_POLL_QUERY, {"id": product_id})
        edges = data["product"]["media"]["edges"]
        for edge in edges:
            node = edge["node"] or {}
            if node.get("id") == media_id:
                last_status = node.get("status")
                if last_status == "READY":
                    return node
                break
        time.sleep(READY_POLL_INTERVAL)
    sys.exit(f"ERROR: Media {media_id} did not reach READY within {READY_POLL_TIMEOUT}s (last status: {last_status})")


# ---------------------------------------------------------------------------
# Variant → media association
# ---------------------------------------------------------------------------

VARIANT_APPEND_MEDIA_MUTATION = """
mutation productVariantAppendMedia($productId: ID!, $variantMedia: [ProductVariantAppendMediaInput!]!) {
  productVariantAppendMedia(productId: $productId, variantMedia: $variantMedia) {
    product { id }
    productVariants {
      id
      image { id url }
    }
    userErrors { field message }
  }
}
"""


def append_media_to_variants(api_url, headers, product_id, variant_ids, media_id):
    variant_media_input = [{"variantId": vid, "mediaIds": [media_id]} for vid in variant_ids]
    variables = {"productId": product_id, "variantMedia": variant_media_input}
    data = gql(api_url, headers, VARIANT_APPEND_MEDIA_MUTATION, variables, timeout=120)
    payload = data["productVariantAppendMedia"]
    return payload


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print plan without mutating")
    args = parser.parse_args()

    # Pre-flight
    if not Path(IMAGE_PATH).exists():
        sys.exit(f"ERROR: Image not found at {IMAGE_PATH}")

    store, token = load_config()
    api_url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }

    print(f"Store: {store}")
    print(f"API version: {API_VERSION}")
    print(f"Image: {IMAGE_PATH} ({Path(IMAGE_PATH).stat().st_size:,} bytes)")
    print(f"Product handle: {PRODUCT_HANDLE}")
    print(f"Target color: {TARGET_COLOR}")
    print(f"Dry run: {args.dry_run}")
    print()

    # 1. Lookup product
    product = fetch_product(api_url, headers, PRODUCT_HANDLE)
    product_id = product["id"]
    variant_edges = product["variants"]["edges"]
    print(f"Product: {product['title']}")
    print(f"Product id: {product_id}")
    print(f"Vendor: {product.get('vendor')}")
    print(f"Total variants: {len(variant_edges)}")
    opt_summary = ", ".join(f"{o['name']}@{o['position']}" for o in product.get("options", []))
    print(f"Options: {opt_summary}")

    # 2. Find color option
    color_opt = find_color_option_name(product)
    if not color_opt:
        sys.exit("ERROR: Could not identify a Color option on this product. STOP.")
    print(f"Color option detected: {color_opt}")

    # 3. Filter Lilac variants
    lilac_variants = filter_lilac_variants(product, color_opt)
    if not lilac_variants:
        sys.exit(f"ERROR: No variants with {color_opt} == '{TARGET_COLOR}'. STOP.")
    print(f"\nLilac variants matched ({len(lilac_variants)}):")
    for v in lilac_variants:
        cur_img = (v.get("image") or {}).get("id") or "(none)"
        opts = ", ".join(f"{s['name']}={s['value']}" for s in v["selectedOptions"])
        print(f"  SKU={v.get('sku'):<8} id={v['id']}  title={v['title']!r}  image={cur_img}  ({opts})")

    variant_ids = [v["id"] for v in lilac_variants]

    if args.dry_run:
        print("\n[DRY RUN] Would:")
        print(f"  1. Stage upload {Path(IMAGE_PATH).name} ({Path(IMAGE_PATH).stat().st_size:,} bytes)")
        print(f"  2. productCreateMedia with alt='{IMAGE_ALT}' on product {product_id}")
        print(f"  3. Poll until MediaImage status=READY")
        print(f"  4. productVariantAppendMedia to {len(variant_ids)} Lilac variants")
        print("\nDry run complete. Rerun without --dry-run to execute.")
        return 0

    # 4. Stage upload
    print("\nStaging upload…")
    target, file_bytes, filename = stage_upload(api_url, headers, IMAGE_PATH)
    resource_url = target["resourceUrl"]
    print(f"  resourceUrl: {resource_url}")
    print(f"  upload target: {target['url']}")

    print("Uploading bytes to staged target…")
    upload_bytes_to_target(target, file_bytes, filename)
    print("  Upload complete.")

    # 5. productCreateMedia
    print("\nCreating media on product…")
    media = create_media_on_product(api_url, headers, product_id, resource_url, IMAGE_ALT)
    media_id = media["id"]
    print(f"  MediaImage id: {media_id}")
    print(f"  Initial status: {media.get('status')}")

    # 6. Poll for READY
    print("Polling until media is READY…")
    ready_media = poll_media_ready(api_url, headers, product_id, media_id)
    image = ready_media.get("image") or {}
    image_id = image.get("id")
    image_url = image.get("url")
    print(f"  Status: {ready_media['status']}")
    print(f"  image.id: {image_id}")
    print(f"  image.url: {image_url}")

    # Record before image ids
    before_images = {v["id"]: ((v.get("image") or {}).get("id")) for v in lilac_variants}

    # 7. Append media to variants
    print(f"\nLinking media {media_id} to {len(variant_ids)} Lilac variants…")
    payload = append_media_to_variants(api_url, headers, product_id, variant_ids, media_id)
    if payload.get("userErrors"):
        print(f"  userErrors: {payload['userErrors']}")
    else:
        print(f"  OK")

    # 8. Verify: re-query product
    print("\nVerifying…")
    refreshed = fetch_product(api_url, headers, PRODUCT_HANDLE)
    refreshed_variants = {e["node"]["id"]: e["node"] for e in refreshed["variants"]["edges"]}

    print("\n=== Variant image transitions ===")
    all_ok = True
    for v in lilac_variants:
        vid = v["id"]
        before_img = before_images.get(vid)
        after_node = refreshed_variants.get(vid, {})
        after_img = (after_node.get("image") or {}).get("id")
        match = after_img == image_id
        marker = "OK" if match else "MISMATCH"
        if not match:
            all_ok = False
        print(f"  [{marker}] {v.get('sku')} ({vid})")
        print(f"          before: {before_img}")
        print(f"          after:  {after_img}")

    print("\n=== Summary ===")
    print(f"Product id:           {product_id}")
    print(f"Product handle:       {PRODUCT_HANDLE}")
    print(f"Total variants:       {len(variant_edges)}")
    print(f"Lilac variants:       {len(lilac_variants)}")
    print(f"Uploaded MediaImage:  {media_id}")
    print(f"Uploaded image id:    {image_id}")
    print(f"Uploaded image url:   {image_url}")
    print(f"Staged resourceUrl:   {resource_url}")
    print(f"All variants linked:  {all_ok}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
