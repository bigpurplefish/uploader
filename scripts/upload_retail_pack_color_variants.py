#!/usr/bin/env python3
"""
Upload 3 new retail-pack color variant images for the "Retail Pack Standing
Irregulars" product, link each to its matching color variants, set the
`custom.color_swatch_image` metafield on every variant, and clean up the
obsolete Lilac-only MediaImage that was uploaded earlier.

Per-color pipeline:
  1. stagedUploadsCreate (resource=IMAGE)
  2. POST bytes to staged target
  3. productCreateMedia (mediaContentType=IMAGE) with alt=
     "#<Color> Retail Pack Standing Irregulars"
  4. Poll product.media until the new MediaImage reaches status=READY
  5. productVariantAppendMedia for both variants of that color
  6. metafieldsSet custom.color_swatch_image (single_line_text_field) for both
     variants of that color with the MediaImage.image.url CDN URL

Cleanup (runs FIRST, before any uploads):
  - productDeleteMedia removes gid://shopify/MediaImage/45468754641188

Verification (runs LAST):
  - Re-query product media; confirm 3 ready MediaImages, old one absent
  - Confirm each variant.image.id matches its color's MediaImage ProductImage id
  - Confirm each variant.metafield(custom.color_swatch_image).value equals that
    color's CDN URL
  - curl the live page and confirm the 3 CDN URLs appear and no
    "background-color: <color>" swatch fallback is rendered

Usage:
    python upload_retail_pack_color_variants.py --dry-run
    python upload_retail_pack_color_variants.py

Hard constraints:
  - Shopify GraphQL API 2025-10
  - Fresh variant gids from productByHandle — no hardcoded variant IDs mutated
    (the ones in PLAN are cross-checked against the fresh API response)
  - If any step fails mid-pipeline, the script reports exactly which color is
    in what state (uploaded/linked/metafield-set) before exiting non-zero.
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

PRODUCT_HANDLE = "retail-pack-standing-irregulars"
PRODUCT_GID_EXPECTED = "gid://shopify/Product/10429372891428"

OLD_MEDIA_IMAGE_GID = "gid://shopify/MediaImage/45468754641188"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"

READY_POLL_TIMEOUT = 60  # seconds
READY_POLL_INTERVAL = 2  # seconds

# Per-color plan: color display name -> (image path, expected variant gids)
# Variant gids listed here are used ONLY as a cross-check; the actual variant
# gids used for mutations come from the fresh productByHandle lookup.
COLOR_PLAN = [
    {
        "color": "Chocolate Grey",
        "image_path": "/tmp/garoppos_product_images/retail_pack_chocolate_grey.png",
        "expected_variant_gids": [
            "gid://shopify/ProductVariant/53328468836644",
            "gid://shopify/ProductVariant/53328468869412",
        ],
    },
    {
        "color": "Lilac",
        "image_path": "/tmp/garoppos_product_images/retail_pack_lilac.png",
        "expected_variant_gids": [
            "gid://shopify/ProductVariant/53328468902180",
            "gid://shopify/ProductVariant/53328468934948",
        ],
    },
    {
        "color": "PA Flagstone Full Color",
        "image_path": "/tmp/garoppos_product_images/retail_pack_pa_full_color.png",
        "expected_variant_gids": [
            "gid://shopify/ProductVariant/53328468967716",
            "gid://shopify/ProductVariant/53328469000484",
        ],
    },
]


def alt_for_color(color):
    # Prefix-matchable by the theme's gallery JS: "#<Color> ..."
    return f"#{color} Retail Pack Standing Irregulars"


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
    variants(first: 250) {
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
    media(first: 100) {
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


def find_color_option_name(product):
    for opt in product.get("options", []):
        if "color" in opt["name"].lower():
            return opt["name"]
    return None


def variants_for_color(product, color_option_name, target_color):
    matches = []
    for edge in product["variants"]["edges"]:
        v = edge["node"]
        for sel in v["selectedOptions"]:
            if sel["name"] == color_option_name and sel["value"].strip().lower() == target_color.strip().lower():
                matches.append(v)
                break
    return matches


# ---------------------------------------------------------------------------
# Cleanup: productDeleteMedia
# ---------------------------------------------------------------------------

PRODUCT_DELETE_MEDIA_MUTATION = """
mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedMediaIds
    mediaUserErrors { field message }
    userErrors { field message }
  }
}
"""


def delete_media(api_url, headers, product_id, media_ids):
    data = gql(
        api_url,
        headers,
        PRODUCT_DELETE_MEDIA_MUTATION,
        {"productId": product_id, "mediaIds": media_ids},
        timeout=60,
    )
    return data["productDeleteMedia"]


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


def set_swatch_metafields(api_url, headers, variant_ids, value):
    inputs = [
        {
            "ownerId": vid,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "type": METAFIELD_TYPE,
            "value": value,
        }
        for vid in variant_ids
    ]
    data = gql(api_url, headers, METAFIELDS_SET_MUTATION, {"metafields": inputs}, timeout=60)
    return data["metafieldsSet"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print plan without mutating")
    args = parser.parse_args()

    # Pre-flight: verify all inputs exist
    for entry in COLOR_PLAN:
        p = Path(entry["image_path"])
        if not p.exists():
            sys.exit(f"ERROR: Image not found: {p}")
        entry["file_size"] = p.stat().st_size

    store, token = load_config()
    api_url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }

    print(f"Store: {store}")
    print(f"API version: {API_VERSION}")
    print(f"Product handle: {PRODUCT_HANDLE}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Fetch product (fresh)
    product = fetch_product(api_url, headers)
    product_id = product["id"]
    if product_id != PRODUCT_GID_EXPECTED:
        sys.exit(
            f"ERROR: Fetched product gid {product_id} does not match expected {PRODUCT_GID_EXPECTED}. STOP."
        )
    print(f"Product: {product['title']}")
    print(f"Product gid: {product_id}")

    color_opt = find_color_option_name(product)
    if not color_opt:
        sys.exit("ERROR: Could not identify a Color option. STOP.")
    print(f"Color option: {color_opt}")

    # Resolve variants per color (fresh) and cross-check against expected gids
    for entry in COLOR_PLAN:
        variants = variants_for_color(product, color_opt, entry["color"])
        if not variants:
            sys.exit(f"ERROR: No variants with {color_opt} == '{entry['color']}'. STOP.")
        got_gids = sorted(v["id"] for v in variants)
        want_gids = sorted(entry["expected_variant_gids"])
        if got_gids != want_gids:
            sys.exit(
                f"ERROR: variant gid mismatch for {entry['color']}.\n"
                f"  Fresh API returned: {got_gids}\n"
                f"  Task plan expected: {want_gids}"
            )
        entry["variants"] = variants
        entry["variant_ids"] = [v["id"] for v in variants]
        entry["alt"] = alt_for_color(entry["color"])

    # Existing product media snapshot
    product_media = [e["node"] for e in product["media"]["edges"] if e.get("node")]
    print(f"\nExisting product media ({len(product_media)}):")
    for m in product_media:
        if m.get("id"):
            print(f"  {m['id']}  status={m.get('status')}  alt={m.get('alt')!r}  img={m.get('image', {}).get('id')}")

    old_media_present = any(m.get("id") == OLD_MEDIA_IMAGE_GID for m in product_media)
    print(f"\nOld MediaImage present? {old_media_present}  ({OLD_MEDIA_IMAGE_GID})")

    print("\nPlan:")
    print(f"  1. Cleanup: productDeleteMedia [{OLD_MEDIA_IMAGE_GID}] "
          f"({'would delete' if old_media_present else 'already absent — skip'})")
    for i, entry in enumerate(COLOR_PLAN, start=2):
        print(f"  {i}. {entry['color']}")
        print(f"       image: {entry['image_path']} ({entry['file_size']:,} bytes)")
        print(f"       alt:   {entry['alt']!r}")
        print(f"       variants ({len(entry['variant_ids'])}):")
        for v in entry["variants"]:
            opts = ", ".join(f"{s['name']}={s['value']}" for s in v["selectedOptions"])
            cur_img = (v.get("image") or {}).get("id") or "(none)"
            cur_mf = (v.get("metafield") or {}).get("value") or "(none)"
            print(f"         SKU={v.get('sku'):<8} id={v['id']}  image={cur_img}")
            print(f"           options: {opts}")
            print(f"           current {METAFIELD_NAMESPACE}.{METAFIELD_KEY} = {cur_mf}")
        print(f"       -> stagedUploadsCreate IMAGE, POST bytes")
        print(f"       -> productCreateMedia (IMAGE)")
        print(f"       -> poll READY")
        print(f"       -> productVariantAppendMedia to {len(entry['variant_ids'])} variants")
        print(f"       -> metafieldsSet {METAFIELD_NAMESPACE}.{METAFIELD_KEY}={METAFIELD_TYPE} on {len(entry['variant_ids'])} variants with CDN URL")
    print(f"  {len(COLOR_PLAN) + 2}. Verify: re-query product media + each variant image + metafield")
    print(f"  {len(COLOR_PLAN) + 3}. Sanity: curl live page for CDN URLs and confirm no 'background-color:' swatch fallback")

    if args.dry_run:
        print("\nDry run complete. Rerun without --dry-run to execute.")
        return 0

    # Per-color execution state (so partial failures are reportable)
    state = {entry["color"]: {"staged": False, "media_id": None, "image_id": None,
                              "image_url": None, "linked": False, "metafield_set": False,
                              "errors": []} for entry in COLOR_PLAN}

    # 1. Cleanup — delete the old MediaImage
    cleanup_result = {"attempted": False, "deleted": None, "errors": []}
    if old_media_present:
        cleanup_result["attempted"] = True
        print(f"\n[Cleanup] productDeleteMedia [{OLD_MEDIA_IMAGE_GID}]…")
        try:
            del_payload = delete_media(api_url, headers, product_id, [OLD_MEDIA_IMAGE_GID])
        except Exception as exc:
            cleanup_result["errors"].append(str(exc))
            _abort_with_state("Cleanup failed before uploads.", cleanup_result, state)
        for err_key in ("userErrors", "mediaUserErrors"):
            if del_payload.get(err_key):
                cleanup_result["errors"].append({err_key: del_payload[err_key]})
        deleted = del_payload.get("deletedMediaIds") or []
        cleanup_result["deleted"] = deleted
        print(f"  deletedMediaIds: {deleted}")
        if cleanup_result["errors"]:
            _abort_with_state("Cleanup userErrors.", cleanup_result, state)
    else:
        print(f"\n[Cleanup] Old MediaImage already absent — skipping.")

    # 2-4. Per-color: stage, upload bytes, create media, poll, link variants, set metafield
    for entry in COLOR_PLAN:
        color = entry["color"]
        st = state[color]
        print(f"\n[{color}] --------------------------------------------")
        try:
            print(f"  Staging upload: {Path(entry['image_path']).name} ({entry['file_size']:,} bytes)…")
            target, file_bytes, filename = stage_upload(api_url, headers, entry["image_path"])
            print(f"    resourceUrl: {target['resourceUrl']}")
            print(f"  Uploading bytes…")
            upload_bytes_to_target(target, file_bytes, filename)
            st["staged"] = True
            print(f"    upload complete.")

            print(f"  productCreateMedia (alt={entry['alt']!r})…")
            media = create_media_on_product(api_url, headers, product_id, target["resourceUrl"], entry["alt"])
            media_id = media["id"]
            st["media_id"] = media_id
            print(f"    MediaImage id: {media_id}  initial status: {media.get('status')}")

            print(f"  Polling for READY…")
            ready = poll_media_ready(api_url, headers, product_id, media_id)
            image = ready.get("image") or {}
            st["image_id"] = image.get("id")
            st["image_url"] = image.get("url")
            print(f"    status: {ready['status']}  image.id: {st['image_id']}")
            print(f"    image.url: {st['image_url']}")

            print(f"  productVariantAppendMedia to {len(entry['variant_ids'])} variants…")
            append_payload = append_media_to_variants(api_url, headers, product_id, entry["variant_ids"], media_id)
            if append_payload.get("userErrors"):
                raise RuntimeError(f"productVariantAppendMedia userErrors: {append_payload['userErrors']}")
            st["linked"] = True
            for pv in append_payload.get("productVariants", []):
                img = pv.get("image") or {}
                print(f"    {pv['id']}  variant.image.id={img.get('id')}  url={img.get('url')}")

            print(f"  metafieldsSet {METAFIELD_NAMESPACE}.{METAFIELD_KEY} on {len(entry['variant_ids'])} variants…")
            mf_payload = set_swatch_metafields(api_url, headers, entry["variant_ids"], st["image_url"])
            if mf_payload.get("userErrors"):
                raise RuntimeError(f"metafieldsSet userErrors: {mf_payload['userErrors']}")
            st["metafield_set"] = True
            for mf in mf_payload.get("metafields", []) or []:
                owner = mf.get("owner") or {}
                print(f"    mf_id={mf['id']}  owner={owner.get('id')} sku={owner.get('sku')}  value={mf['value']}")

        except Exception as exc:
            st["errors"].append(str(exc))
            _abort_with_state(f"Failure during {color} pipeline.", cleanup_result, state)

    # 5. Verification
    print("\n[Verify] Re-querying product…")
    refreshed = fetch_product(api_url, headers)
    refreshed_media = [e["node"] for e in refreshed["media"]["edges"] if e.get("node") and e["node"].get("id")]
    print(f"  Media count: {len(refreshed_media)}")
    for m in refreshed_media:
        print(f"    {m['id']}  status={m.get('status')}  alt={m.get('alt')!r}  img={m.get('image', {}).get('id')}")

    # Build color -> CDN URL map from state. We match variant images by CDN URL
    # rather than gid, because MediaImage.image.id returns an ImageSource gid
    # while ProductVariant.image.id returns a ProductImage gid (same image,
    # different gid namespaces).
    color_to_image_url = {c: state[c]["image_url"] for c in state}

    refreshed_variant_by_id = {e["node"]["id"]: e["node"] for e in refreshed["variants"]["edges"]}

    all_ok = True
    print("\n=== Verification Table ===")
    header = f"{'SKU':<8} {'Color':<26} {'variant.image.id':<60} {'metafield CDN URL'}"
    print(header)
    print("-" * len(header))
    for entry in COLOR_PLAN:
        expected_url = color_to_image_url[entry["color"]]
        for vid in entry["variant_ids"]:
            v = refreshed_variant_by_id.get(vid) or {}
            actual_img = (v.get("image") or {}).get("id")
            actual_img_url = (v.get("image") or {}).get("url")
            mf = v.get("metafield") or {}
            actual_mf = mf.get("value")
            ok_img = actual_img_url == expected_url
            ok_mf = actual_mf == expected_url
            status = " " if (ok_img and ok_mf) else "X"
            all_ok = all_ok and ok_img and ok_mf
            print(f"[{status}] {v.get('sku', ''):<6} {entry['color']:<26} {actual_img!s:<60} {actual_mf}")
            if not ok_img:
                print(f"      expected variant image url={expected_url}")
                print(f"      got      variant image url={actual_img_url}")
            if not ok_mf:
                print(f"      expected metafield={expected_url}")

    # Confirm old MediaImage is gone
    old_still_present = any(m.get("id") == OLD_MEDIA_IMAGE_GID for m in refreshed_media)
    print(f"\nOld MediaImage {OLD_MEDIA_IMAGE_GID} present post-run? {old_still_present}")
    if old_still_present:
        all_ok = False

    # 6. Live page sanity check
    print("\n[Sanity] Curling live product page…")
    cb = int(time.time())
    url = f"https://garoppos.com/products/{PRODUCT_HANDLE}?cb={cb}"
    try:
        html = subprocess.check_output(
            ["curl", "-sL", url], timeout=60, text=True, errors="replace"
        )
    except Exception as exc:
        html = ""
        print(f"  curl failed: {exc}")
    url_hits = {}
    for entry in COLOR_PLAN:
        u = state[entry["color"]]["image_url"]
        # Strip the query string for a lax match
        u_base = (u or "").split("?", 1)[0]
        url_hits[entry["color"]] = (u_base in html) if u_base else False
    # The theme fix should mean no background-color: <color> swatch fallback is rendered
    bg_hits = [line.strip() for line in html.splitlines() if "background-color" in line.lower() and "swatch" in line.lower()]
    print(f"  CDN URL hits in HTML:")
    for c, hit in url_hits.items():
        print(f"    {c}: {'FOUND' if hit else 'MISSING'}")
    if bg_hits:
        print(f"  WARNING: 'background-color' + 'swatch' lines found ({len(bg_hits)}):")
        for b in bg_hits[:5]:
            print(f"    {b[:200]}")
    else:
        print(f"  No 'background-color' swatch fallback lines found — OK.")

    # Summary
    print("\n=== Summary ===")
    print(f"  cleanup: {'deleted' if cleanup_result['deleted'] else ('already absent' if not old_media_present else 'NOT deleted')}"
          + (f"  errors={cleanup_result['errors']}" if cleanup_result["errors"] else ""))
    for c, st in state.items():
        print(f"  {c}: media={st['media_id']}  image_id={st['image_id']}  "
              f"linked={st['linked']}  metafield_set={st['metafield_set']}"
              + (f"  errors={st['errors']}" if st["errors"] else ""))
    print(f"  verification all_ok: {all_ok}")
    print(f"  old_media_still_present: {old_still_present}")

    return 0 if all_ok else 2


def _abort_with_state(message, cleanup_result, state):
    print(f"\nABORT: {message}")
    print(f"  cleanup: {cleanup_result}")
    for c, st in state.items():
        print(f"  {c}: {st}")
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main() or 0)
