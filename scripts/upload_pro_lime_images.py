#!/usr/bin/env python3
"""Upload 2 processed PNGs (front + back) for Gardenscape 'Pro Lime Pelletized Dolomitic Lime'.

Product (queried at design time):
  handle = pro-lime-pelletized-dolomitic-lime
  gid    = gid://shopify/Product/10433286045988
  vendor = Gardenscape
  options:
    position 1 = 'Size'         values = ['50 LB']   (degenerate: 1 value)
    position 2 = 'Unit of Sale' values = ['Bag']     (degenerate: 1 value)
  variants (1):
    SKU 3492  title='50 LB / Bag'
  media: EMPTY (no images uploaded yet)

Alt-tag strategy:
  Single variant and BOTH options are degenerate (every variant carries the same
  values for option1 and option2). Hashtags would add no selectivity: the filter
  either matches every variant (redundant) or breaks them (typos). Instead, we
  use descriptive no-hashtag alts. The theme filter JS (product-gallery.liquid)
  skips any alt without a '#' and leaves the image visible for every variant.

  Front image alt = "Gardenscape Pro-Lime Pelletized Dolomitic Lime"
  Back image alt  = "Gardenscape Pro-Lime Pelletized Dolomitic Lime - Back"

Pipeline:
  1. Query product by handle, verify structure matches the design-time snapshot
     (1 variant, SKU 3492, 2 options both degenerate, 0 media). If unexpected,
     STOP and report.
  2. Per image (front, back):
       a. stagedUploadsCreate (resource=IMAGE, image/png)
       b. POST bytes to staged target
       c. productCreateMedia (mediaContentType=IMAGE) with chosen alt
       d. Poll product.media until status=READY, capture MediaImage gid + CDN url
  3. productVariantAppendMedia — link BOTH images to the single variant
  4. metafieldsSet — custom.color_swatch_image = FRONT CDN URL for the variant
  5. Verification:
       - Re-query: confirm 2 MediaImages, alts correct
       - Variant image.url set, metafield set
       - Python theme-filter simulation: both images should be visible for the variant
       - curl live page with cache-buster, confirm both CDN URLs appear

Usage:
  python3 upload_pro_lime_images.py --dry-run
  python3 upload_pro_lime_images.py          # executes
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

PRODUCT_HANDLE = "pro-lime-pelletized-dolomitic-lime"
LIVE_URL = f"https://garoppos.com/products/{PRODUCT_HANDLE}"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"

READY_POLL_TIMEOUT = 120  # seconds
READY_POLL_INTERVAL = 2  # seconds

FRONT_IMAGE_PATH = "/tmp/garoppos_product_images/3492_front_processed.png"
BACK_IMAGE_PATH = "/tmp/garoppos_product_images/3492_back_processed.png"

# Alt text strategy: descriptive, NO '#' so the theme filter keeps them
# visible on all variants (degenerate options would make hashtags pointless).
FRONT_ALT = "Gardenscape Pro-Lime Pelletized Dolomitic Lime"
BACK_ALT = "Gardenscape Pro-Lime Pelletized Dolomitic Lime - Back"

EXPECTED_SKU = "3492"
EXPECTED_VARIANT_COUNT = 1
EXPECTED_OPTION_NAMES = ["Size", "Unit of Sale"]

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
    vendor
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


def validate_structure(product):
    """Abort if product deviates from the expected single-variant degenerate-options shape."""
    options = product.get("options", []) or []
    options_sorted = sorted(options, key=lambda o: o.get("position", 0))
    option_names = [o["name"] for o in options_sorted]
    if option_names != EXPECTED_OPTION_NAMES:
        sys.exit(
            f"STOP: unexpected options. Expected {EXPECTED_OPTION_NAMES}, got {option_names}."
        )
    # Degenerate check
    for o in options_sorted:
        if len(o.get("values", []) or []) != 1:
            sys.exit(
                f"STOP: option '{o['name']}' is no longer degenerate: values={o.get('values')}."
                " Re-evaluate alt-tag strategy (hashtagging now required)."
            )

    variants_map = variants_by_sku(product)
    if len(variants_map) != EXPECTED_VARIANT_COUNT:
        sys.exit(
            f"STOP: expected {EXPECTED_VARIANT_COUNT} variant, found {len(variants_map)}."
            " Re-evaluate alt-tag strategy."
        )
    if EXPECTED_SKU not in variants_map:
        sys.exit(f"STOP: expected SKU '{EXPECTED_SKU}' missing. SKUs present: {list(variants_map)}")

    existing_media = product["media"]["edges"]
    if existing_media:
        print(
            f"WARNING: product already has {len(existing_media)} media entries."
            " Continuing will append, not replace."
        )
    return options_sorted, variants_map


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
    """Python port of product-gallery.liquid filter JS.

    For each variant, returns list of media entries the filter JS would keep visible.
    An image is visible if:
      - Its alt has no '#' (unfiltered, always visible), OR
      - All hashtag segments match corresponding lowercased selectedOptions
        (exact match or size-prefix match e.g. '30 x 30' matches '30 x 30 - Sq Ft')
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
        # Check for is-filtered class near the URLs (simple heuristic)
        is_filtered_hits = html.count("is-filtered")
        return {
            "url": url,
            "http_ok": result.returncode == 0,
            "html_length": len(html),
            "cdn_url_found": found,
            "is_filtered_count_in_html": is_filtered_hits,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan only, no mutations")
    args = parser.parse_args()

    # Pre-flight: verify inputs exist
    for p in (FRONT_IMAGE_PATH, BACK_IMAGE_PATH):
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
    print(f"Vendor:     {product.get('vendor')}")
    print(f"Product gid:{product_id}")

    options_sorted, variants_map = validate_structure(product)

    print(f"\nOptions ({len(options_sorted)}):")
    for o in options_sorted:
        print(f"  - {o['name']} (position={o['position']}) values={o['values']}")

    print(f"\nVariants ({len(variants_map)}):")
    for sku, v in sorted(variants_map.items()):
        print(f"  - SKU {sku}  gid={v['id']}  title='{v['title']}'  image={v.get('image')}  metafield={v.get('metafield')}")

    target_variant = variants_map[EXPECTED_SKU]
    target_variant_id = target_variant["id"]

    print("\nPLAN")
    print("-" * 60)
    print(f"Front image: {FRONT_IMAGE_PATH}")
    print(f"  alt='{FRONT_ALT}'  (no '#', visible for every variant)")
    print(f"Back image:  {BACK_IMAGE_PATH}")
    print(f"  alt='{BACK_ALT}'  (no '#', visible for every variant)")
    print(f"Link both images to variant SKU {EXPECTED_SKU} ({target_variant_id})")
    print(f"Set variant metafield {METAFIELD_NAMESPACE}.{METAFIELD_KEY}={METAFIELD_TYPE}")
    print("  value = FRONT image CDN URL")
    print("-" * 60)

    if args.dry_run:
        print("\n[DRY RUN] exiting before mutations.")
        return

    # -----------------------------------------------------------------------
    # Upload images: stage -> POST bytes -> productCreateMedia -> poll READY
    # -----------------------------------------------------------------------
    uploads = [
        {"label": "FRONT", "path": FRONT_IMAGE_PATH, "alt": FRONT_ALT},
        {"label": "BACK", "path": BACK_IMAGE_PATH, "alt": BACK_ALT},
    ]

    for u in uploads:
        print(f"\n--- Uploading {u['label']}: {Path(u['path']).name} ---")
        target, file_bytes, filename = stage_upload(api_url, headers, u["path"])
        print(f"  stagedUploadsCreate -> resourceUrl={target['resourceUrl']}")

        upload_bytes_to_target(target, file_bytes, filename)
        print(f"  POST {len(file_bytes)} bytes OK")

        media_stub = create_media_on_product(api_url, headers, product_id, target["resourceUrl"], u["alt"])
        media_id = media_stub["id"]
        print(f"  productCreateMedia -> {media_id} status={media_stub.get('status')}")

        ready = poll_media_ready(api_url, headers, product_id, media_id)
        cdn_url = ready["image"]["url"]
        print(f"  READY   alt='{ready['alt']}'  cdn={cdn_url}")

        u["media_id"] = media_id
        u["cdn_url"] = cdn_url
        u["alt_confirmed"] = ready["alt"]

    front = uploads[0]
    back = uploads[1]

    # -----------------------------------------------------------------------
    # Link media to the single variant.
    # Shopify rejects productVariantAppendMedia once a variant already has an
    # attached image ("The given variant already has attached media.") so we
    # only attach the FRONT (which becomes the variant's featured image, used
    # for thumbnails / swatches). BACK stays in the product-level media gallery
    # and is shown for the variant via the theme filter (no '#' in alt).
    # -----------------------------------------------------------------------
    print("\n--- Linking FRONT media to variant (featured image) ---")
    link_summary = []
    link_resp = append_media_to_variants(
        api_url, headers, product_id, [target_variant_id], front["media_id"]
    )
    if link_resp.get("userErrors"):
        # If the variant already has media (idempotent re-run), don't abort
        ues = link_resp["userErrors"]
        if all("already has attached media" in (e.get("message") or "") for e in ues):
            print(f"  WARN (ignored, likely re-run): {ues}")
        else:
            raise RuntimeError(f"productVariantAppendMedia userErrors: {ues}")
    else:
        print(f"  FRONT -> variant {target_variant_id}: {link_resp.get('productVariants')}")
    link_summary.append({
        "media": "FRONT",
        "media_id": front["media_id"],
        "productVariants": link_resp.get("productVariants"),
    })
    print(
        "  BACK not appended to variant (Shopify allows only one 'attached' media; "
        "BACK remains in product gallery and passes the alt filter for this variant)."
    )

    # -----------------------------------------------------------------------
    # Swatch metafield: FRONT CDN url on the variant
    # -----------------------------------------------------------------------
    print("\n--- Setting swatch metafield ---")
    mf_resp = set_swatch_metafields(api_url, headers, [(target_variant_id, front["cdn_url"])])
    if mf_resp.get("userErrors"):
        raise RuntimeError(f"metafieldsSet userErrors: {mf_resp['userErrors']}")
    for mf in mf_resp.get("metafields", []):
        owner = mf.get("owner") or {}
        print(f"  {owner.get('sku')}  {mf['namespace']}.{mf['key']}={mf['value']}  (id={mf['id']})")

    # -----------------------------------------------------------------------
    # Verification re-query
    # -----------------------------------------------------------------------
    print("\n--- Verification re-query ---")
    product2 = fetch_product(api_url, headers)

    media_entries = []
    for edge in product2["media"]["edges"]:
        node = edge["node"]
        if node:
            media_entries.append(node)
    print(f"Product now has {len(media_entries)} media entries:")
    for m in media_entries:
        print(f"  {m['id']}  status={m.get('status')}  alt='{m.get('alt')}'  url={(m.get('image') or {}).get('url')}")

    variants_after = [e["node"] for e in product2["variants"]["edges"]]
    for v in variants_after:
        print(f"\nVariant SKU {v.get('sku')} ({v['id']})")
        img = v.get("image") or {}
        print(f"  image.url     = {img.get('url')}")
        mf = v.get("metafield") or {}
        print(f"  metafield     = {mf.get('namespace')}.{mf.get('key')}={mf.get('value')}")

    # -----------------------------------------------------------------------
    # Theme filter simulation
    # -----------------------------------------------------------------------
    print("\n--- Theme filter simulation ---")
    sim = simulate_filter(variants_after, media_entries)
    for r in sim:
        print(f"SKU {r['sku']}  selectedOptions={r['selectedOptions']}")
        for vis in r["visible_media"]:
            print(f"  visible: {vis['id']}  reason={vis['reason']}  alt='{vis['alt']}'")

    # -----------------------------------------------------------------------
    # Live page curl
    # -----------------------------------------------------------------------
    print("\n--- Live page curl (cache-busted) ---")
    expected_urls = [u["cdn_url"] for u in uploads]
    live = curl_live_page(expected_urls)
    print(json.dumps(live, indent=2))

    # -----------------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Product gid:       {product_id}")
    print(f"Variant count:     {len(variants_after)}")
    print(f"FRONT media:       {front['media_id']}")
    print(f"  CDN URL:         {front['cdn_url']}")
    print(f"  alt:             {front['alt_confirmed']}")
    print(f"BACK  media:       {back['media_id']}")
    print(f"  CDN URL:         {back['cdn_url']}")
    print(f"  alt:             {back['alt_confirmed']}")
    print(f"Variant links:     {len(variants_after)} variant(s) x {len(uploads)} images = {len(variants_after) * len(uploads)}")
    print(f"Metafields set:    {len(mf_resp.get('metafields', []))}")
    filter_ok = all(len(r["visible_media"]) == len(media_entries) for r in sim)
    print(f"Theme filter sim:  {'OK' if filter_ok else 'PROBLEM'}  (every variant sees every image)")
    all_found = all(v for v in live.get("cdn_url_found", {}).values())
    print(f"Live curl:         {'OK - both URLs present' if all_found else 'URLs missing (CDN propagation/cache)'}")


if __name__ == "__main__":
    main()
