#!/usr/bin/env python3
"""Fix alt text on 3 MediaImages for 'Retail Pack Standing Irregulars' product.

Problem:
  The theme's gallery filter JS splits alt on '#' and checks every hashtag
  segment against the variant's option1/2/3 (lowercased). Current alt
  "#Chocolate Grey Retail Pack Standing Irregulars" yields hashtag value
  "chocolate grey retail pack standing irregulars" which does not equal
  option1 value "chocolate grey". Result: all 3 images filtered out.

Fix:
  Update alt text on the 3 MediaImages via productUpdateMedia so the
  hashtag contains ONLY the color value. Descriptive text goes BEFORE the
  hashtag (ignored by the filter — parts[0]) but is useful for screen readers.

Usage:
  python3 fix_retail_pack_alt_tags.py --dry-run
  python3 fix_retail_pack_alt_tags.py --execute
"""

import argparse
import json
import logging
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_VERSION = "2025-10"

PRODUCT_ID = "gid://shopify/Product/10429372891428"
PRODUCT_HANDLE = "retail-pack-standing-irregulars"
LIVE_URL = f"https://garoppos.com/products/{PRODUCT_HANDLE}"

# (MediaImage gid, new alt text)
UPDATES = [
    ("gid://shopify/MediaImage/45468925198628", "Retail Pack Standing Irregulars #Chocolate Grey"),
    ("gid://shopify/MediaImage/45468925690148", "Retail Pack Standing Irregulars #Lilac"),
    ("gid://shopify/MediaImage/45468925755684", "Retail Pack Standing Irregulars #PA Flagstone Full Color"),
]


def gql(store_url: str, token: str, query: str, variables: dict) -> dict:
    # Normalize — config may contain "https://store.myshopify.com" or just "store.myshopify.com"
    host = store_url.replace("https://", "").replace("http://", "").rstrip("/")
    url = f"https://{host}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }
    resp = requests.post(url, json={"query": query, "variables": variables}, headers=headers, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


def fetch_product_media(store_url: str, token: str, product_id: str) -> list:
    """Fetch the product's media, returning list of {id, alt} for MediaImages."""
    query = """
    query($id: ID!) {
      product(id: $id) {
        id
        title
        media(first: 50) {
          nodes {
            ... on MediaImage {
              id
              alt
              image { url }
            }
          }
        }
      }
    }
    """
    data = gql(store_url, token, query, {"id": product_id})
    product = data.get("product") or {}
    nodes = (product.get("media") or {}).get("nodes") or []
    return [n for n in nodes if n.get("id", "").startswith("gid://shopify/MediaImage/")]


def fetch_product_variants(store_url: str, token: str, product_id: str) -> list:
    """Fetch the product's variants and their selectedOptions."""
    query = """
    query($id: ID!) {
      product(id: $id) {
        variants(first: 100) {
          nodes {
            id
            title
            selectedOptions { name value }
          }
        }
      }
    }
    """
    data = gql(store_url, token, query, {"id": product_id})
    product = data.get("product") or {}
    return (product.get("variants") or {}).get("nodes") or []


def update_media_alt(store_url: str, token: str, product_id: str, updates: list) -> dict:
    """Run productUpdateMedia to update alt text on all media entries in one call."""
    query = """
    mutation($productId: ID!, $media: [UpdateMediaInput!]!) {
      productUpdateMedia(productId: $productId, media: $media) {
        media {
          ... on MediaImage { id alt }
        }
        mediaUserErrors { field message code }
      }
    }
    """
    media_input = [{"id": gid, "alt": alt} for gid, alt in updates]
    data = gql(store_url, token, query, {"productId": product_id, "media": media_input})
    return data.get("productUpdateMedia") or {}


def simulate_filter(variants: list, media_alts: list) -> list:
    """Simulate theme's filter JS. Returns list of (variant_title, selectedOptions, matching_media_ids).

    JS logic (product-gallery.liquid lines 311-336):
      selectedOptions = [option1, option2, option3].lowercased (those present)
      hashtagValues = [p.strip().lower() for p in alt.split('#')[1:] if p.strip()]
      allMatch = True
      for k in range(min(len(hashtagValues), len(selectedOptions))):
        if hashtagValues[k] != selectedOptions[k] and
           not selectedOptions[k].startswith(hashtagValues[k] + ' - '):
          allMatch = False
    """
    results = []
    for v in variants:
        sel = [o["value"].lower() for o in v.get("selectedOptions", [])]
        matches = []
        for m in media_alts:
            alt = m.get("alt") or ""
            if "#" not in alt:
                continue
            parts = alt.split("#")
            hashtag_values = [p.strip().lower() for p in parts[1:] if p.strip()]
            if not hashtag_values:
                continue
            all_match = True
            k_max = min(len(hashtag_values), len(sel))
            for k in range(k_max):
                if hashtag_values[k] != sel[k] and not sel[k].startswith(hashtag_values[k] + " - "):
                    all_match = False
                    break
            if all_match:
                matches.append(m["id"])
        results.append({
            "variant_title": v.get("title"),
            "selectedOptions": sel,
            "matching_media": matches,
        })
    return results


def curl_live_page() -> dict:
    """Fetch live page with cache-buster and return verification info."""
    import subprocess

    url = f"{LIVE_URL}?cb={int(time.time())}"
    try:
        result = subprocess.run(
            ["curl", "-sL", url],
            capture_output=True, text=True, timeout=30,
        )
        html = result.stdout
        expected_alts = [alt for _, alt in UPDATES]
        found_alts = [a for a in expected_alts if f'data-media-alt="{a}"' in html]
        # Count carousel items and those marked filtered
        carousel_count = html.count("product-gallery__carousel-item")
        is_filtered_count = html.count("is-filtered")
        return {
            "url": url,
            "http_ok": result.returncode == 0,
            "found_alts": found_alts,
            "expected_alts": expected_alts,
            "carousel_item_mentions": carousel_count,
            "is_filtered_mentions": is_filtered_count,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Fix alt text on Retail Pack Standing Irregulars MediaImages")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only, don't execute mutation")
    parser.add_argument("--execute", action="store_true", help="Execute the mutation")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Must pass --dry-run or --execute")

    config = load_config()
    store_url = config.get("SHOPIFY_STORE_URL")
    token = config.get("SHOPIFY_ACCESS_TOKEN")
    if not store_url or not token:
        log.error("Missing SHOPIFY_STORE_URL or SHOPIFY_ACCESS_TOKEN in config.json")
        return 1

    log.info("=" * 70)
    log.info("Fetching current product media...")
    current_media = fetch_product_media(store_url, token, PRODUCT_ID)
    current_by_id = {m["id"]: m for m in current_media}

    log.info("Fetching product variants...")
    variants = fetch_product_variants(store_url, token, PRODUCT_ID)

    log.info("")
    log.info("PLAN: update alt text on %d MediaImages", len(UPDATES))
    log.info("-" * 70)
    for gid, new_alt in UPDATES:
        old_alt = (current_by_id.get(gid) or {}).get("alt") or "(not found)"
        log.info("  %s", gid)
        log.info("    BEFORE: %r", old_alt)
        log.info("    AFTER:  %r", new_alt)

    log.info("")
    log.info("Simulation BEFORE mutation (what filter does right now):")
    log.info("-" * 70)
    before_sim = simulate_filter(variants, current_media)
    for row in before_sim:
        log.info("  %-55s -> matches=%d %s",
                 row["variant_title"], len(row["matching_media"]), row["matching_media"])

    log.info("")
    log.info("Simulation AFTER mutation (with proposed alt text):")
    log.info("-" * 70)
    proposed_media = []
    for m in current_media:
        # Substitute proposed alt for the 3 targeted images
        override = next((alt for gid, alt in UPDATES if gid == m["id"]), None)
        proposed_media.append({"id": m["id"], "alt": override if override is not None else m.get("alt")})
    after_sim = simulate_filter(variants, proposed_media)
    for row in after_sim:
        log.info("  %-55s -> matches=%d %s",
                 row["variant_title"], len(row["matching_media"]), row["matching_media"])

    if args.dry_run:
        log.info("")
        log.info("DRY-RUN: not executing mutation. Re-run with --execute to apply.")
        return 0

    log.info("")
    log.info("=" * 70)
    log.info("EXECUTING productUpdateMedia mutation...")
    result = update_media_alt(store_url, token, PRODUCT_ID, UPDATES)
    errors = result.get("mediaUserErrors") or []
    updated = result.get("media") or []
    if errors:
        log.error("mediaUserErrors: %s", json.dumps(errors, indent=2))
        return 2
    log.info("Mutation succeeded. Updated %d media entries:", len(updated))
    for m in updated:
        if m:
            log.info("  %s  alt=%r", m.get("id"), m.get("alt"))

    # Re-query to confirm
    log.info("")
    log.info("Re-querying product to confirm alt text persisted...")
    time.sleep(1.5)
    refetched = fetch_product_media(store_url, token, PRODUCT_ID)
    refetched_by_id = {m["id"]: m for m in refetched}
    for gid, expected in UPDATES:
        got = (refetched_by_id.get(gid) or {}).get("alt")
        match = "OK" if got == expected else "MISMATCH"
        log.info("  [%s] %s -> %r", match, gid, got)

    # Live page verification
    log.info("")
    log.info("Fetching live page to verify theme rendering...")
    live = curl_live_page()
    log.info("  URL: %s", live.get("url"))
    if "error" in live:
        log.warning("  curl error: %s", live["error"])
    else:
        log.info("  HTTP OK: %s", live.get("http_ok"))
        log.info("  Alts found in HTML: %d/%d", len(live.get("found_alts", [])),
                 len(live.get("expected_alts", [])))
        for a in live.get("expected_alts", []):
            mark = "OK" if a in live.get("found_alts", []) else "MISSING"
            log.info("    [%s] %s", mark, a)
        log.info("  carousel_item mentions: %d, is-filtered mentions: %d",
                 live.get("carousel_item_mentions", 0),
                 live.get("is_filtered_mentions", 0))

    # Final simulation on refetched live data
    log.info("")
    log.info("Final simulation using REFETCHED live data:")
    log.info("-" * 70)
    final_sim = simulate_filter(variants, refetched)
    for row in final_sim:
        log.info("  %-55s -> matches=%d %s",
                 row["variant_title"], len(row["matching_media"]), row["matching_media"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
