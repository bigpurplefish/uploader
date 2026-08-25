#!/usr/bin/env python3
"""
Replace the Compost product's only image with a new scene rendering and link it
to the `50 LB Bag` variant only. The `Per Cubic Yard` variant intentionally
ends up with no image in this round (user may add one later).

Pipeline:
  1. Fetch product by handle (`compost`) and confirm structure matches the
     expected GID + option ("Unit of Sale") + variants (Per Cubic Yard / 50 LB
     Bag, SKU 18163-02).
  2. productDeleteMedia removes the old MediaImage.
  3. stagedUploadsCreate (resource=IMAGE) + POST bytes to the staged target.
  4. productCreateMedia (mediaContentType=IMAGE) with alt=
       "Compost #50 LB Bag"
     (Hashtag format the theme's gallery JS splits on for per-option filtering;
      prefix matching in the theme allows `#50 LB Bag` to match option1
      `50 LB Bag` lowercased.)
  5. Poll product.media until the new MediaImage is READY; capture the new
     MediaImage gid + CDN URL.
  6. productVariantAppendMedia for the 50 LB Bag variant only.
  7. metafieldsSet custom.color_swatch_image (single_line_text_field) on the
     50 LB Bag variant with the CDN URL. Per Cubic Yard is skipped.

Verification:
  - Re-query product media: exactly 1 MediaImage, old one absent.
  - 50 LB Bag: variant.image.url == new CDN URL and
    metafield(custom.color_swatch_image).value == new CDN URL.
  - Per Cubic Yard: variant.image is null.
  - Python filter simulation for each variant.
  - curl the live product page with a cache-buster and confirm the new CDN
    URL is in the HTML and the old one is not.

Usage:
    python upload_compost_50lb_image.py --dry-run
    python upload_compost_50lb_image.py

Hard constraints:
  - Shopify GraphQL API 2025-10.
  - Product GID / variant GID cross-checked against the fresh productByHandle
    response. If anything differs, abort.
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

PRODUCT_HANDLE = "compost"
PRODUCT_GID_EXPECTED = "gid://shopify/Product/10368015204644"

OLD_MEDIA_IMAGE_GID = "gid://shopify/MediaImage/45190794117412"
OLD_MEDIA_IMAGE_URL_BASE = (
    "https://cdn.shopify.com/s/files/1/0968/5322/9860/files/"
    "garoppo-s-stone-garden-and-feed-pet-supply_compost_18163_18163_"
    "compost_upscale_29895d43-60d1-4bc3-ae64-044498ec4109.png"
)

IMAGE_PATH = "/tmp/garoppos_product_images/compost_generated_processed.png"
NEW_IMAGE_ALT = "Compost #50 LB Bag"

# Target variant: 50 LB Bag, SKU 18163-02
TARGET_VARIANT_GID_EXPECTED = "gid://shopify/ProductVariant/53342600823076"
TARGET_VARIANT_SKU_EXPECTED = "18163-02"
TARGET_OPTION_NAME = "Unit of Sale"
TARGET_OPTION_VALUE = "50 LB Bag"
OTHER_OPTION_VALUE = "Per Cubic Yard"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "color_swatch_image"
METAFIELD_TYPE = "single_line_text_field"

READY_POLL_TIMEOUT = 60  # seconds
READY_POLL_INTERVAL = 2  # seconds


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
# Theme filter simulation
# ---------------------------------------------------------------------------
#
# Mirror the theme's product-gallery.liquid logic closely enough to answer
# "would this image show for this variant?" in Python. The theme:
#   - Splits alt text on '#' into segments; each non-empty segment is a tag.
#   - For each variant's selectedOptions, lowercases both option values and the
#     alt hashtag segments and checks whether the hashtag STARTS WITH the
#     option value OR the option value starts with the hashtag (prefix match
#     either way). Images with no hashtags are always visible.
#
# This is a conservative Python port: if any hashtag segment exists, that
# hashtag must prefix-match at least one of the variant's selectedOption
# values. If no hashtags, visible.


def parse_alt_hashtags(alt):
    if not alt:
        return []
    # Split on '#', drop empty and pre-hash prefix ("Compost #50 LB Bag" => ["50 LB Bag"])
    parts = [p.strip() for p in alt.split("#")]
    return [p for p in parts if p]


def image_visible_for_variant(alt, variant_option_values):
    """Return True if a variant with the given option values (list of raw
    values, in the variant's option order) should show an image with the given
    alt text, per the theme's prefix-matching rule.
    """
    hashtags = parse_alt_hashtags(alt)
    # Strip the leading non-hash prefix: "Compost #50 LB Bag" has first element
    # "Compost" before the first '#', and that's NOT a hashtag. Re-parse:
    # Actually `alt.split("#")` on "Compost #50 LB Bag" gives:
    #   ["Compost ", "50 LB Bag"]
    # The leading "Compost " is the text before the first hash, not a hashtag.
    # We drop it here.
    if "#" in (alt or ""):
        hashtags = [p.strip() for p in alt.split("#")[1:] if p.strip()]
    else:
        hashtags = []

    if not hashtags:
        return True
    lower_opts = [v.strip().lower() for v in variant_option_values]
    for tag in hashtags:
        t = tag.strip().lower()
        match = False
        for ov in lower_opts:
            if t == ov or t.startswith(ov) or ov.startswith(t):
                match = True
                break
        if not match:
            return False
    return True


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


def variant_by_sku(product, sku):
    for edge in product["variants"]["edges"]:
        v = edge["node"]
        if (v.get("sku") or "").strip() == sku:
            return v
    return None


def variant_by_option_value(product, option_name, value):
    for edge in product["variants"]["edges"]:
        v = edge["node"]
        for sel in v["selectedOptions"]:
            if sel["name"] == option_name and sel["value"].strip() == value:
                return v
    return None


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
        f"Media {media_id} did not reach READY within {READY_POLL_TIMEOUT}s "
        f"(last status: {last_status})"
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


def set_swatch_metafield(api_url, headers, variant_id, value):
    inputs = [
        {
            "ownerId": variant_id,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "type": METAFIELD_TYPE,
            "value": value,
        }
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

    # Pre-flight: image exists
    img = Path(IMAGE_PATH)
    if not img.exists():
        sys.exit(f"ERROR: Image not found: {img}")
    file_size = img.stat().st_size

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

    product = fetch_product(api_url, headers)
    product_id = product["id"]
    if product_id != PRODUCT_GID_EXPECTED:
        sys.exit(
            f"ERROR: Fetched product gid {product_id} does not match expected "
            f"{PRODUCT_GID_EXPECTED}. STOP."
        )
    print(f"Product: {product['title']}")
    print(f"Product gid: {product_id}")
    print(f"Vendor: {product.get('vendor')}")

    # Confirm structure: 1 option named "Unit of Sale" at position 1
    options = product.get("options") or []
    if len(options) != 1:
        sys.exit(f"ERROR: Expected 1 option, got {len(options)}. STOP.")
    opt = options[0]
    if opt["name"] != TARGET_OPTION_NAME:
        sys.exit(
            f"ERROR: Expected option named '{TARGET_OPTION_NAME}', got "
            f"'{opt['name']}'. STOP."
        )
    if opt["position"] != 1:
        sys.exit(f"ERROR: Expected option position 1, got {opt['position']}. STOP.")
    print(f"Option: {opt['name']} (pos {opt['position']}) values={opt['values']}")

    # Resolve variants
    target_variant = variant_by_option_value(product, TARGET_OPTION_NAME, TARGET_OPTION_VALUE)
    other_variant = variant_by_option_value(product, TARGET_OPTION_NAME, OTHER_OPTION_VALUE)
    if not target_variant:
        sys.exit(f"ERROR: No variant with {TARGET_OPTION_NAME}='{TARGET_OPTION_VALUE}'. STOP.")
    if not other_variant:
        sys.exit(f"ERROR: No variant with {TARGET_OPTION_NAME}='{OTHER_OPTION_VALUE}'. STOP.")

    if target_variant["id"] != TARGET_VARIANT_GID_EXPECTED:
        sys.exit(
            f"ERROR: 50 LB Bag variant gid mismatch.\n"
            f"  Fresh API returned: {target_variant['id']}\n"
            f"  Task plan expected: {TARGET_VARIANT_GID_EXPECTED}"
        )
    if (target_variant.get("sku") or "").strip() != TARGET_VARIANT_SKU_EXPECTED:
        sys.exit(
            f"ERROR: 50 LB Bag variant SKU mismatch.\n"
            f"  Fresh API returned: {target_variant.get('sku')!r}\n"
            f"  Task plan expected: {TARGET_VARIANT_SKU_EXPECTED}"
        )
    print(f"\nTarget variant (50 LB Bag):")
    print(f"  gid: {target_variant['id']}")
    print(f"  sku: {target_variant.get('sku')}")
    cur_img = (target_variant.get("image") or {}).get("url") or "(none)"
    cur_mf = (target_variant.get("metafield") or {}).get("value") or "(none)"
    print(f"  current image.url: {cur_img}")
    print(f"  current {METAFIELD_NAMESPACE}.{METAFIELD_KEY}: {cur_mf}")

    print(f"\nOther variant (Per Cubic Yard):")
    print(f"  gid: {other_variant['id']}")
    print(f"  sku: {other_variant.get('sku')}")
    cur_img2 = (other_variant.get("image") or {}).get("url") or "(none)"
    cur_mf2 = (other_variant.get("metafield") or {}).get("value") or "(none)"
    print(f"  current image.url: {cur_img2}")
    print(f"  current {METAFIELD_NAMESPACE}.{METAFIELD_KEY}: {cur_mf2}")

    # Existing product media snapshot
    product_media = [e["node"] for e in product["media"]["edges"] if e.get("node")]
    print(f"\nExisting product media ({len(product_media)}):")
    for m in product_media:
        if m.get("id"):
            print(
                f"  {m['id']}  status={m.get('status')}  alt={m.get('alt')!r}  "
                f"img={m.get('image', {}).get('id')}"
            )
    old_media_present = any(m.get("id") == OLD_MEDIA_IMAGE_GID for m in product_media)
    print(f"\nOld MediaImage present? {old_media_present}  ({OLD_MEDIA_IMAGE_GID})")

    print("\nPlan:")
    print(
        f"  1. Cleanup: productDeleteMedia [{OLD_MEDIA_IMAGE_GID}] "
        f"({'would delete' if old_media_present else 'already absent — skip'})"
    )
    print(f"  2. stagedUploadsCreate IMAGE for {IMAGE_PATH} ({file_size:,} bytes)")
    print(f"  3. productCreateMedia alt={NEW_IMAGE_ALT!r}")
    print(f"  4. poll READY")
    print(
        f"  5. productVariantAppendMedia to 50 LB Bag variant only "
        f"({target_variant['id']})"
    )
    print(
        f"  6. metafieldsSet {METAFIELD_NAMESPACE}.{METAFIELD_KEY}={METAFIELD_TYPE} "
        f"on 50 LB Bag variant with new CDN URL"
    )
    print(
        f"  7. Verify: re-query product media (==1), variant image/metafield, "
        f"Per Cubic Yard image is null, filter simulation, live curl"
    )

    if args.dry_run:
        print("\nDry run complete. Rerun without --dry-run to execute.")
        return 0

    # Execution state
    state = {
        "cleanup": {"attempted": False, "deleted": None, "errors": []},
        "staged": False,
        "media_id": None,
        "image_id": None,
        "image_url": None,
        "linked": False,
        "metafield_set": False,
        "errors": [],
    }

    # 1. Cleanup — delete the old MediaImage
    if old_media_present:
        state["cleanup"]["attempted"] = True
        print(f"\n[Cleanup] productDeleteMedia [{OLD_MEDIA_IMAGE_GID}]…")
        try:
            del_payload = delete_media(api_url, headers, product_id, [OLD_MEDIA_IMAGE_GID])
        except Exception as exc:
            state["cleanup"]["errors"].append(str(exc))
            _abort("Cleanup failed before uploads.", state)
        for err_key in ("userErrors", "mediaUserErrors"):
            if del_payload.get(err_key):
                state["cleanup"]["errors"].append({err_key: del_payload[err_key]})
        deleted = del_payload.get("deletedMediaIds") or []
        state["cleanup"]["deleted"] = deleted
        print(f"  deletedMediaIds: {deleted}")
        if state["cleanup"]["errors"]:
            _abort("Cleanup userErrors.", state)
    else:
        print(f"\n[Cleanup] Old MediaImage already absent — skipping.")

    # 2-3. Stage + POST bytes + productCreateMedia
    try:
        print(f"\n[Upload] Staging: {img.name} ({file_size:,} bytes)…")
        target, file_bytes, filename = stage_upload(api_url, headers, IMAGE_PATH)
        print(f"  resourceUrl: {target['resourceUrl']}")
        print(f"[Upload] POSTing bytes to staged target…")
        upload_bytes_to_target(target, file_bytes, filename)
        state["staged"] = True
        print(f"  upload complete.")

        print(f"\n[Create] productCreateMedia alt={NEW_IMAGE_ALT!r}…")
        media = create_media_on_product(
            api_url, headers, product_id, target["resourceUrl"], NEW_IMAGE_ALT
        )
        media_id = media["id"]
        state["media_id"] = media_id
        print(f"  MediaImage id: {media_id}  initial status: {media.get('status')}")

        # 4. Poll for READY
        print(f"\n[Poll] Waiting for READY…")
        ready = poll_media_ready(api_url, headers, product_id, media_id)
        image = ready.get("image") or {}
        state["image_id"] = image.get("id")
        state["image_url"] = image.get("url")
        print(f"  status: {ready['status']}  image.id: {state['image_id']}")
        print(f"  image.url: {state['image_url']}")

        # 5. productVariantAppendMedia (50 LB Bag only)
        print(
            f"\n[Link] productVariantAppendMedia {target_variant['id']} "
            f"<- {media_id}"
        )
        append_payload = append_media_to_variants(
            api_url, headers, product_id, [target_variant["id"]], media_id
        )
        if append_payload.get("userErrors"):
            raise RuntimeError(
                f"productVariantAppendMedia userErrors: {append_payload['userErrors']}"
            )
        state["linked"] = True
        for pv in append_payload.get("productVariants", []):
            vimg = pv.get("image") or {}
            print(f"  {pv['id']}  variant.image.id={vimg.get('id')}  url={vimg.get('url')}")

        # 6. metafieldsSet on target variant
        print(
            f"\n[Metafield] metafieldsSet {METAFIELD_NAMESPACE}.{METAFIELD_KEY} on "
            f"{target_variant['id']}…"
        )
        mf_payload = set_swatch_metafield(api_url, headers, target_variant["id"], state["image_url"])
        if mf_payload.get("userErrors"):
            raise RuntimeError(f"metafieldsSet userErrors: {mf_payload['userErrors']}")
        state["metafield_set"] = True
        for mf in mf_payload.get("metafields", []) or []:
            owner = mf.get("owner") or {}
            print(
                f"  mf_id={mf['id']}  owner={owner.get('id')} sku={owner.get('sku')}  "
                f"value={mf['value']}"
            )

    except Exception as exc:
        state["errors"].append(str(exc))
        _abort("Failure during upload/link/metafield pipeline.", state)

    # 7. Verification
    print("\n[Verify] Re-querying product…")
    refreshed = fetch_product(api_url, headers)
    refreshed_media = [
        e["node"]
        for e in refreshed["media"]["edges"]
        if e.get("node") and e["node"].get("id")
    ]
    print(f"  Media count: {len(refreshed_media)}")
    for m in refreshed_media:
        print(
            f"    {m['id']}  status={m.get('status')}  alt={m.get('alt')!r}  "
            f"img={m.get('image', {}).get('id')}"
        )

    new_media_ids = [m.get("id") for m in refreshed_media]
    only_new_media = (
        len(refreshed_media) == 1 and state["media_id"] in new_media_ids
    )
    old_still_present = OLD_MEDIA_IMAGE_GID in new_media_ids

    target_v = variant_by_option_value(refreshed, TARGET_OPTION_NAME, TARGET_OPTION_VALUE)
    other_v = variant_by_option_value(refreshed, TARGET_OPTION_NAME, OTHER_OPTION_VALUE)
    target_img_url = (target_v.get("image") or {}).get("url") if target_v else None
    other_img = (other_v.get("image") if other_v else None)
    target_mf = (target_v.get("metafield") or {}) if target_v else {}
    target_mf_val = target_mf.get("value")

    ok_target_img = target_img_url == state["image_url"]
    ok_target_mf = target_mf_val == state["image_url"]
    ok_other_img_none = other_img is None

    print("\n=== Variant verification ===")
    print(f"  50 LB Bag variant.image.url  = {target_img_url}")
    print(f"      expected                 = {state['image_url']}")
    print(f"  50 LB Bag metafield value    = {target_mf_val}")
    print(f"      expected                 = {state['image_url']}")
    print(f"  Per Cubic Yard variant.image = {other_img!r}  (expect None)")

    # 7b. Python filter simulation
    print("\n=== Python filter simulation (theme prefix matching) ===")
    sim_rows = []
    for (label, v) in [("50 LB Bag", target_v), ("Per Cubic Yard", other_v)]:
        if not v:
            sim_rows.append((label, "(variant not found)", "?"))
            continue
        opt_vals = [s["value"] for s in v.get("selectedOptions", [])]
        for m in refreshed_media:
            alt = m.get("alt") or ""
            visible = image_visible_for_variant(alt, opt_vals)
            sim_rows.append((label, alt, "VISIBLE" if visible else "HIDDEN"))
    for row in sim_rows:
        print(f"  variant={row[0]!r:<18} alt={row[1]!r:<40} -> {row[2]}")

    # Expected: 50 LB Bag -> VISIBLE, Per Cubic Yard -> HIDDEN
    sim_50 = any(
        r for r in sim_rows if r[0] == "50 LB Bag" and r[2] == "VISIBLE"
    )
    sim_pcy = any(
        r for r in sim_rows if r[0] == "Per Cubic Yard" and r[2] == "HIDDEN"
    )
    sim_pcy_visible = any(
        r for r in sim_rows if r[0] == "Per Cubic Yard" and r[2] == "VISIBLE"
    )
    ok_sim = sim_50 and sim_pcy and not sim_pcy_visible

    # 7c. Live curl
    print("\n[Sanity] Curling live product page…")
    cb = int(time.time())
    live_url = f"https://garoppos.com/products/{PRODUCT_HANDLE}?cb={cb}"
    try:
        html = subprocess.check_output(
            ["curl", "-sL", live_url], timeout=60, text=True, errors="replace"
        )
    except Exception as exc:
        html = ""
        print(f"  curl failed: {exc}")
    new_url_base = (state["image_url"] or "").split("?", 1)[0]
    new_url_in_html = bool(new_url_base) and (new_url_base in html)
    old_url_in_html = OLD_MEDIA_IMAGE_URL_BASE in html
    print(f"  New CDN URL in HTML? {new_url_in_html}  ({new_url_base})")
    print(f"  Old CDN URL in HTML? {old_url_in_html}  ({OLD_MEDIA_IMAGE_URL_BASE})")

    ok_live = new_url_in_html and not old_url_in_html

    # Summary
    print("\n=== Summary ===")
    print(
        f"  cleanup: "
        f"{'deleted ' + str(state['cleanup']['deleted']) if state['cleanup']['deleted'] else ('already absent' if not old_media_present else 'NOT deleted')}"
        + (f"  errors={state['cleanup']['errors']}" if state['cleanup']['errors'] else "")
    )
    print(f"  new media_id: {state['media_id']}")
    print(f"  new image_id: {state['image_id']}")
    print(f"  new image_url: {state['image_url']}")
    print(f"  alt: {NEW_IMAGE_ALT!r}")
    print(f"  linked to 50 LB Bag: {state['linked']}")
    print(f"  metafield set on 50 LB Bag: {state['metafield_set']}")
    print(f"  media count == 1 (only new): {only_new_media}")
    print(f"  old media absent: {not old_still_present}")
    print(f"  50 LB Bag variant image correct: {ok_target_img}")
    print(f"  50 LB Bag metafield correct: {ok_target_mf}")
    print(f"  Per Cubic Yard image is null: {ok_other_img_none}")
    print(f"  filter sim ok (50 LB Bag visible, Per Cubic Yard hidden): {ok_sim}")
    print(f"  live curl ok (new URL present, old URL absent): {ok_live}")
    if state["errors"]:
        print(f"  errors: {state['errors']}")

    all_ok = (
        only_new_media
        and not old_still_present
        and ok_target_img
        and ok_target_mf
        and ok_other_img_none
        and ok_sim
        and ok_live
        and state["linked"]
        and state["metafield_set"]
    )
    print(f"\n  ALL OK: {all_ok}")
    return 0 if all_ok else 2


def _abort(message, state):
    print(f"\nABORT: {message}")
    print(f"  state: {json.dumps(state, indent=2, default=str)}")
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main() or 0)
