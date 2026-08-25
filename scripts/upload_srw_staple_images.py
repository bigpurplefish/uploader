#!/usr/bin/env python3
"""Upload 2 PNGs for 'SRW Landscape Staples 1000/Bx' product, link to 5 variants,
set swatch metafields, and verify theme gallery filter behavior.

Option A (2-hashtag targeting for 2-option product):
  Product has 2 options:
    position 1 = Size (value '6"x1"x6"', same on all variants)
    position 2 = Unit of Sale (5 distinct values)
  26697_processed.png (single stake)     -> SKU 26697 only.
      Alt = "SRW Landscape Staples #<option1>#<option2>"
            e.g., 'SRW Landscape Staples #6"x1"x6"#1 Stake'
      Both hashtag segments must match for the filter JS to show the image.
  22978_processed.png (retail packaging) -> SKUs 22978, 24724, 24725, 41000.
      Alt = "SRW Landscape Staples"   (no '#', so filter JS leaves it visible
      on every variant including the stake variant).

Pipeline:
  1. Query product by handle; verify SKUs match; print plan
  2. Per image:
       a. stagedUploadsCreate (resource=IMAGE, image/png)
       b. POST bytes to staged target
       c. productCreateMedia (mediaContentType=IMAGE) with alt
       d. poll product.media until status=READY
  3. productVariantAppendMedia — 1 call per image (each links to its variant set)
  4. metafieldsSet — custom.color_swatch_image = CDN URL per variant
  5. Verification:
       - Re-query: confirm 2 MediaImages, alts correct
       - Confirm variant.image.url matches expected, metafield matches expected
       - curl live page with cache-buster, confirm CDN URLs present
       - Python simulation of theme filter JS for all 5 variants

Usage:
  python3 upload_srw_staple_images.py --dry-run
  python3 upload_srw_staple_images.py         # executes after dry-run sanity print

Hard constraints:
  - Shopify GraphQL API 2025-10
  - Config: /Users/moosemarketer/Code/garoppos/uploader/config.json
  - Does NOT modify existing uploader_modules/ or other scripts
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants / plan
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # uploader/
CONFIG_PATH = REPO_ROOT / "config.json"
API_VERSION = "2025-10"

PRODUCT_HANDLE = "srw-landscape-staples-1000-bx"
LIVE_URL = f"https://garoppos.com/products/{PRODUCT_HANDLE}"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"

READY_POLL_TIMEOUT = 90  # seconds
READY_POLL_INTERVAL = 2  # seconds

STAKE_IMAGE_PATH = "/tmp/garoppos_product_images/26697_processed.png"
BAG_IMAGE_PATH = "/tmp/garoppos_product_images/22978_processed.png"

# Expected SKU -> expected option1 value (for informational cross-check only;
# the real option1 value is pulled from the live product response).
EXPECTED = {
    "22978": "50 Per Bag",
    "24724": "500 Per Box",
    "24725": "1000 Per Box",
    "26697": "1 Stake",
    "41000": "10 Per Box",
}

STAKE_SKU = "26697"
BAG_SKUS = ["22978", "24724", "24725", "41000"]

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
# Product lookup
# ---------------------------------------------------------------------------

PRODUCT_QUERY = """
query getProductByHandle($handle: String!, $ns: String!, $key: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    options { id name position values }
    variants(first: 50) {
      edges {
        node {
          id
          sku
          title
          selectedOptions { name value }
          image { id url altText }
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
    media(first: 50) {
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


def fetch_product(api_url, headers):
    data = gql(
        api_url,
        headers,
        PRODUCT_QUERY,
        {"handle": PRODUCT_HANDLE, "ns": METAFIELD_NAMESPACE, "key": METAFIELD_KEY},
    )
    product = data.get("productByHandle")
    if not product:
        sys.exit(f"ERROR: Product with handle '{PRODUCT_HANDLE}' not found.")
    return product


def variants_by_sku(product):
    out = {}
    for edge in product["variants"]["edges"]:
        v = edge["node"]
        if v.get("sku"):
            out[v["sku"]] = v
    return out


# ---------------------------------------------------------------------------
# Staged upload + productCreateMedia + poll
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
    mediaUserErrors { field message code }
    userErrors { field message }
  }
}
"""

PRODUCT_MEDIA_POLL_QUERY = """
query productMedia($id: ID!) {
  product(id: $id) {
    media(first: 50, sortKey: ID, reverse: true) {
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
        raise RuntimeError(f"stagedUploadsCreate userErrors: {staged['userErrors']}")
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
        raise RuntimeError(f"productCreateMedia userErrors: {payload['userErrors']}")
    if payload.get("mediaUserErrors"):
        raise RuntimeError(f"productCreateMedia mediaUserErrors: {payload['mediaUserErrors']}")
    media = payload.get("media", [])
    if not media:
        raise RuntimeError("productCreateMedia returned no media")
    return media[0]


def poll_media_ready(api_url, headers, product_id, media_id):
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
    raise RuntimeError(
        f"Media {media_id} did not reach READY within {READY_POLL_TIMEOUT}s (last status: {last_status})"
    )


# ---------------------------------------------------------------------------
# Variant append media + metafieldsSet
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
    return data["productVariantAppendMedia"]


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


def set_swatch_metafields(api_url, headers, variant_url_pairs):
    inputs = [
        {
            "ownerId": vid,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "type": METAFIELD_TYPE,
            "value": url,
        }
        for vid, url in variant_url_pairs
    ]
    data = gql(api_url, headers, METAFIELDS_SET_MUTATION, {"metafields": inputs}, timeout=60)
    return data["metafieldsSet"]


# ---------------------------------------------------------------------------
# Theme filter simulation
# ---------------------------------------------------------------------------


def simulate_filter(variants, media_entries):
    """Python port of product-gallery.liquid:311-336 filter JS.

    For each variant, returns list of media ids the filter JS would keep visible.
    An image is visible if:
      - Its alt has no '#' (unfiltered, always visible), OR
      - All hashtag segments match corresponding lowercased selectedOptions
    """
    results = []
    for v in variants:
        sel = [o["value"].lower() for o in v.get("selectedOptions", [])]
        visible = []
        for m in media_entries:
            alt = m.get("alt") or ""
            if "#" not in alt:
                visible.append({"id": m.get("id"), "alt": alt, "reason": "no-hashtag"})
                continue
            parts = alt.split("#")
            hashtag_values = [p.strip().lower() for p in parts[1:] if p.strip()]
            if not hashtag_values:
                visible.append({"id": m.get("id"), "alt": alt, "reason": "empty-hashtags"})
                continue
            all_match = True
            k_max = min(len(hashtag_values), len(sel))
            for k in range(k_max):
                if hashtag_values[k] != sel[k] and not sel[k].startswith(hashtag_values[k] + " - "):
                    all_match = False
                    break
            if all_match:
                visible.append({"id": m.get("id"), "alt": alt, "reason": "hashtag-match"})
        results.append({
            "sku": v.get("sku"),
            "variant_title": v.get("title"),
            "selectedOptions": sel,
            "visible_media": visible,
        })
    return results


# ---------------------------------------------------------------------------
# Live page curl
# ---------------------------------------------------------------------------


def curl_live_page(expected_cdn_urls):
    url = f"{LIVE_URL}?cb={int(time.time())}"
    try:
        result = subprocess.run(
            ["curl", "-sL", url], capture_output=True, text=True, timeout=30
        )
        html = result.stdout
        found = {u: (u in html) for u in expected_cdn_urls}
        return {
            "url": url,
            "http_ok": result.returncode == 0,
            "html_length": len(html),
            "cdn_url_found": found,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print plan only, no mutations")
    args = parser.parse_args()

    # Pre-flight: verify inputs
    for p in (STAKE_IMAGE_PATH, BAG_IMAGE_PATH):
        if not Path(p).exists():
            sys.exit(f"ERROR: Image not found: {p}")

    store, token = load_config()
    api_url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}

    print(f"Store:      {store}")
    print(f"API ver:    {API_VERSION}")
    print(f"Handle:     {PRODUCT_HANDLE}")
    print(f"Dry run:    {args.dry_run}")
    print()

    product = fetch_product(api_url, headers)
    product_id = product["id"]
    print(f"Product:    {product['title']}")
    print(f"Product gid:{product_id}")

    # Option inspection
    options = product.get("options", []) or []
    print(f"\nOptions ({len(options)}):")
    for o in options:
        print(f"  - {o['name']} (position={o['position']}) values={o['values']}")

    if len(options) not in (1, 2):
        sys.exit(
            f"STOP: expected 1 or 2 options, found {len(options)}. "
            f"Option names: {[o['name'] for o in options]}."
        )

    # Sort options by position so option_name_1 is position 1, etc.
    options_sorted = sorted(options, key=lambda o: o.get("position", 0))
    option_name_1 = options_sorted[0]["name"]
    option_name_2 = options_sorted[1]["name"] if len(options_sorted) >= 2 else None
    print(f"Using option1: '{option_name_1}'")
    if option_name_2:
        print(f"Using option2: '{option_name_2}'")

    # Resolve variants by SKU
    variants_map = variants_by_sku(product)
    print(f"\nVariants ({len(variants_map)}) from API:")
    for sku, v in sorted(variants_map.items()):
        opt1 = next((o["value"] for o in v["selectedOptions"] if o["name"] == option_name_1), None)
        opt2 = (
            next((o["value"] for o in v["selectedOptions"] if o["name"] == option_name_2), None)
            if option_name_2
            else None
        )
        print(
            f"  SKU {sku}: variant_gid={v['id']}  option1='{opt1}'  option2='{opt2}'  title='{v.get('title')}'"
        )

    missing_skus = [s for s in EXPECTED if s not in variants_map]
    if missing_skus:
        sys.exit(f"STOP: expected SKUs missing from live product: {missing_skus}")

    # Cross-check SKU -> option2 values (Unit of Sale).  EXPECTED map values
    # reflect the Unit of Sale ("1 Stake", "50 Per Bag", etc.).
    print(f"\nSKU -> option2 ('{option_name_2}') cross-check:")
    actual_opt2 = {}
    for sku, expected_opt2 in EXPECTED.items():
        v = variants_map[sku]
        opt2 = (
            next((o["value"] for o in v["selectedOptions"] if o["name"] == option_name_2), None)
            if option_name_2
            else None
        )
        actual_opt2[sku] = opt2
        flag = "OK" if (opt2 or "").strip().lower() == expected_opt2.strip().lower() else "DIFF"
        print(f"  [{flag}] SKU {sku}: expected '{expected_opt2}' actual '{opt2}'")

    # Existing media snapshot
    existing_media = [e["node"] for e in product["media"]["edges"] if e.get("node") and e["node"].get("id")]
    print(f"\nExisting media on product: {len(existing_media)}")
    for m in existing_media:
        print(f"  - {m.get('id')} alt='{m.get('alt')}' status={m.get('status')}")
    if existing_media:
        print("NOTE: product already has media. Script will still append new images.")

    # Derive alt tags from the LIVE option values for SKU 26697 (Option A:
    # two hashtag segments so the filter JS matches both option positions).
    stake_variant = variants_map[STAKE_SKU]
    stake_opt1_live = next(
        (o["value"] for o in stake_variant["selectedOptions"] if o["name"] == option_name_1), None
    )
    stake_opt2_live = (
        next((o["value"] for o in stake_variant["selectedOptions"] if o["name"] == option_name_2), None)
        if option_name_2
        else None
    )
    if not stake_opt1_live:
        sys.exit(f"STOP: could not read option1 value for SKU {STAKE_SKU}")
    if option_name_2 and not stake_opt2_live:
        sys.exit(f"STOP: could not read option2 value for SKU {STAKE_SKU}")

    if option_name_2:
        stake_alt = f"SRW Landscape Staples #{stake_opt1_live}#{stake_opt2_live}"
    else:
        stake_alt = f"SRW Landscape Staples #{stake_opt1_live}"
    bag_alt = "SRW Landscape Staples"

    print("\nAlt strategy (Option A: 2-hashtag targeting):")
    print(f"  STAKE image ({Path(STAKE_IMAGE_PATH).name}): alt='{stake_alt}'  -> variant SKU {STAKE_SKU}")
    print(f"  BAG image   ({Path(BAG_IMAGE_PATH).name}): alt='{bag_alt}'  -> variant SKUs {BAG_SKUS}")
    print("  (Bag alt has no '#', so theme filter JS skips it — bag stays visible on every variant.)")
    print("  (Stake alt has 2 hashtags matching option1+option2 — filter JS only shows it on SKU 26697.)")

    print("\nPlan:")
    print("  1. Stage + upload STAKE image, productCreateMedia, poll READY")
    print("  2. Stage + upload BAG image,   productCreateMedia, poll READY")
    print(f"  3. productVariantAppendMedia STAKE -> [{STAKE_SKU}]")
    print(f"  4. productVariantAppendMedia BAG   -> {BAG_SKUS}")
    print("  5. metafieldsSet custom.color_swatch_image per variant with CDN URL")
    print("  6. Re-query product, verify, simulate filter, curl live page")

    if args.dry_run:
        print("\n[DRY RUN] Stopping before any mutations.")
        return 0

    # ---------------------------------------------------------------------
    # Execute: upload STAKE image
    # ---------------------------------------------------------------------
    print("\n--- STAKE image upload ---")
    target, bytes_, filename = stage_upload(api_url, headers, STAKE_IMAGE_PATH)
    print(f"  staged target: {target['url'][:80]}...  ({len(bytes_)} bytes)")
    upload_bytes_to_target(target, bytes_, filename)
    print("  bytes uploaded to staged target")
    stake_media = create_media_on_product(api_url, headers, product_id, target["resourceUrl"], stake_alt)
    stake_media_id = stake_media["id"]
    print(f"  MediaImage created: {stake_media_id} status={stake_media.get('status')} alt='{stake_media.get('alt')}'")
    stake_ready = poll_media_ready(api_url, headers, product_id, stake_media_id)
    stake_cdn_url = (stake_ready.get("image") or {}).get("url")
    print(f"  READY. CDN URL: {stake_cdn_url}")

    # ---------------------------------------------------------------------
    # Execute: upload BAG image
    # ---------------------------------------------------------------------
    print("\n--- BAG image upload ---")
    target, bytes_, filename = stage_upload(api_url, headers, BAG_IMAGE_PATH)
    print(f"  staged target: {target['url'][:80]}...  ({len(bytes_)} bytes)")
    upload_bytes_to_target(target, bytes_, filename)
    print("  bytes uploaded to staged target")
    bag_media = create_media_on_product(api_url, headers, product_id, target["resourceUrl"], bag_alt)
    bag_media_id = bag_media["id"]
    print(f"  MediaImage created: {bag_media_id} status={bag_media.get('status')} alt='{bag_media.get('alt')}'")
    bag_ready = poll_media_ready(api_url, headers, product_id, bag_media_id)
    bag_cdn_url = (bag_ready.get("image") or {}).get("url")
    print(f"  READY. CDN URL: {bag_cdn_url}")

    # ---------------------------------------------------------------------
    # Execute: productVariantAppendMedia
    # ---------------------------------------------------------------------
    print("\n--- productVariantAppendMedia STAKE ---")
    stake_variant_ids = [variants_map[STAKE_SKU]["id"]]
    resp = append_media_to_variants(api_url, headers, product_id, stake_variant_ids, stake_media_id)
    if resp.get("userErrors"):
        raise RuntimeError(f"append STAKE userErrors: {resp['userErrors']}")
    print(f"  linked {len(stake_variant_ids)} variant(s) to stake MediaImage")

    print("\n--- productVariantAppendMedia BAG ---")
    bag_variant_ids = [variants_map[s]["id"] for s in BAG_SKUS]
    resp = append_media_to_variants(api_url, headers, product_id, bag_variant_ids, bag_media_id)
    if resp.get("userErrors"):
        raise RuntimeError(f"append BAG userErrors: {resp['userErrors']}")
    print(f"  linked {len(bag_variant_ids)} variant(s) to bag MediaImage")

    # ---------------------------------------------------------------------
    # Execute: metafieldsSet
    # ---------------------------------------------------------------------
    print("\n--- metafieldsSet custom.color_swatch_image ---")
    variant_url_pairs = []
    variant_url_pairs.append((variants_map[STAKE_SKU]["id"], stake_cdn_url))
    for s in BAG_SKUS:
        variant_url_pairs.append((variants_map[s]["id"], bag_cdn_url))
    mf_resp = set_swatch_metafields(api_url, headers, variant_url_pairs)
    if mf_resp.get("userErrors"):
        raise RuntimeError(f"metafieldsSet userErrors: {mf_resp['userErrors']}")
    mf_created = mf_resp.get("metafields") or []
    print(f"  metafieldsSet created/updated: {len(mf_created)}")
    for mf in mf_created:
        owner_sku = (mf.get("owner") or {}).get("sku")
        print(f"    - SKU {owner_sku}: {mf.get('value')}")

    # ---------------------------------------------------------------------
    # Verify
    # ---------------------------------------------------------------------
    print("\n--- Verification: re-query product ---")
    # Small delay to let Shopify settle variant image association
    time.sleep(2)
    product_v = fetch_product(api_url, headers)
    media_v = [e["node"] for e in product_v["media"]["edges"] if e.get("node") and e["node"].get("id")]
    print(f"  media count: {len(media_v)}")
    for m in media_v:
        print(f"    - {m.get('id')} alt='{m.get('alt')}' status={m.get('status')} cdn={(m.get('image') or {}).get('url')}")

    variants_v = [e["node"] for e in product_v["variants"]["edges"]]
    variants_v_by_sku = {v["sku"]: v for v in variants_v if v.get("sku")}

    print("\n  Per-variant image + metafield check:")
    all_ok = True
    for sku in EXPECTED:
        v = variants_v_by_sku.get(sku)
        if not v:
            print(f"    [FAIL] SKU {sku}: not found on re-query")
            all_ok = False
            continue
        img_url = (v.get("image") or {}).get("url")
        mf = v.get("metafield") or {}
        mf_val = mf.get("value")
        expected_url = stake_cdn_url if sku == STAKE_SKU else bag_cdn_url
        img_ok = (img_url == expected_url)
        mf_ok = (mf_val == expected_url)
        flag = "OK" if (img_ok and mf_ok) else "DIFF"
        print(f"    [{flag}] SKU {sku}: image_url_match={img_ok} metafield_match={mf_ok}")
        if not img_ok:
            print(f"        expected image: {expected_url}")
            print(f"        got      image: {img_url}")
        if not mf_ok:
            print(f"        expected mf   : {expected_url}")
            print(f"        got      mf   : {mf_val}")
        if not (img_ok and mf_ok):
            all_ok = False

    # ---------------------------------------------------------------------
    # Theme filter simulation
    # ---------------------------------------------------------------------
    print("\n--- Theme filter simulation (product-gallery.liquid:311-336) ---")
    sim = simulate_filter(variants_v, media_v)
    print(f"  {'SKU':<8} {'option1':<15} {'visible_count':<14} visible_alts")
    for row in sim:
        alts = ", ".join(f"'{m['alt']}'" for m in row["visible_media"])
        print(f"  {row['sku']:<8} {row['selectedOptions'][0] if row['selectedOptions'] else '':<15} {len(row['visible_media']):<14} {alts}")

    # Sanity: stake variant should see 2, all others should see 1 (the bag)
    sim_by_sku = {r["sku"]: r for r in sim}
    expected_counts = {s: (2 if s == STAKE_SKU else 1) for s in EXPECTED}
    sim_ok = True
    for sku, want in expected_counts.items():
        got = len(sim_by_sku.get(sku, {}).get("visible_media", []))
        if got != want:
            print(f"  [FAIL] SKU {sku} sim: expected {want} visible, got {got}")
            sim_ok = False
    if sim_ok:
        print("  Filter simulation: expected visibility pattern confirmed.")

    # ---------------------------------------------------------------------
    # Live curl
    # ---------------------------------------------------------------------
    print("\n--- Live page curl with cache-buster ---")
    live = curl_live_page([stake_cdn_url, bag_cdn_url])
    print(f"  URL: {live.get('url')}")
    if live.get("error"):
        print(f"  ERROR: {live['error']}")
    else:
        print(f"  http_ok={live.get('http_ok')} html_len={live.get('html_length')}")
        for url, found in (live.get("cdn_url_found") or {}).items():
            flag = "FOUND" if found else "MISSING"
            print(f"  [{flag}] {url}")

    print("\n=== SUMMARY ===")
    print(f"  stake MediaImage: {stake_media_id}  alt='{stake_alt}'")
    print(f"  bag   MediaImage: {bag_media_id}  alt='{bag_alt}'")
    print(f"  stake CDN URL   : {stake_cdn_url}")
    print(f"  bag   CDN URL   : {bag_cdn_url}")
    print(f"  variants linked : 5/5")
    print(f"  metafields set  : {len(mf_created)}/5")
    print(f"  verification    : {'OK' if (all_ok and sim_ok) else 'CHECK LOG'}")
    return 0 if (all_ok and sim_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
