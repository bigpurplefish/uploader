#!/usr/bin/env python3
"""Move all product-level media from a source Shopify product to a destination
product.

Workflow:
  1. Query current media on both products (including variant media associations
     on the source so we can warn about severed links).
  2. If source has zero media, stop and report.
  3. Re-create each source media on the destination via productCreateMedia
     (batched), preserving alt text and mediaContentType.
  4. Poll destination media until status READY (or FAILED). Abort if any FAILED.
  5. Once destination copies are READY, productDeleteMedia on the source.
  6. Re-query both products and report before/after counts.

Usage:
    python scripts/move_media_between_products.py \
        --source gid://shopify/Product/10431960809764 \
        --destination gid://shopify/Product/10429334028580

Credentials come from uploader/config.json.
Shopify Admin API 2025-10 via GraphQL.
"""

import argparse
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader_modules.config import load_config

API_VERSION = "2025-10"

POLL_INTERVAL_SECONDS = 1.5
POLL_TIMEOUT_SECONDS = 30  # per batch poll cycle; up to 3 cycles


# ---------------------------------------------------------------------------
# GraphQL helpers
# ---------------------------------------------------------------------------


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


PRODUCT_MEDIA_QUERY = """
query ProductMedia($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    mediaCount { count }
    media(first: 250) {
      edges {
        node {
          id
          alt
          mediaContentType
          status
          preview { image { url } }
          ... on MediaImage {
            image { id url altText width height }
          }
          ... on Video {
            sources { url mimeType format height width }
            originalSource { url mimeType format height width }
          }
          ... on Model3d {
            sources { url mimeType format filesize }
            originalSource { url mimeType format filesize }
          }
          ... on ExternalVideo {
            embedUrl
            host
          }
        }
      }
    }
    variants(first: 250) {
      edges {
        node {
          id
          title
          sku
          selectedOptions { name value }
          media(first: 50) {
            edges {
              node {
                id
                mediaContentType
                alt
              }
            }
          }
        }
      }
    }
  }
}
"""


PRODUCT_CREATE_MEDIA_MUTATION = """
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media {
      id
      alt
      mediaContentType
      status
      ... on MediaImage {
        image { id url altText }
      }
      ... on Video {
        sources { url }
      }
      ... on Model3d {
        sources { url }
      }
    }
    mediaUserErrors {
      field
      message
      code
    }
    userErrors {
      field
      message
    }
  }
}
"""


MEDIA_STATUS_QUERY = """
query MediaStatus($id: ID!) {
  node(id: $id) {
    id
    ... on MediaImage {
      mediaContentType
      status
      alt
      image { url }
    }
    ... on Video {
      mediaContentType
      status
      alt
    }
    ... on Model3d {
      mediaContentType
      status
      alt
    }
  }
}
"""


PRODUCT_DELETE_MEDIA_MUTATION = """
mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedMediaIds
    deletedProductImageIds
    mediaUserErrors {
      field
      message
      code
    }
    product { id }
    userErrors { field message }
  }
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_product(url, headers, product_gid):
    data = gql(url, headers, PRODUCT_MEDIA_QUERY, {"id": product_gid})
    product = data.get("product")
    if product is None:
        raise RuntimeError(f"Product not found: {product_gid}")
    return product


def summarize_product(label, product):
    media_edges = product["media"]["edges"]
    print(f"\n=== {label}: {product['title']} ({product['id']}) ===")
    print(f"  handle: {product['handle']}")
    print(f"  mediaCount: {product['mediaCount']['count']}")
    print(f"  media edges returned: {len(media_edges)}")
    for i, edge in enumerate(media_edges, start=1):
        node = edge["node"]
        url = None
        if node.get("image"):
            url = node["image"].get("url")
        elif node.get("originalSource"):
            url = node["originalSource"].get("url")
        elif node.get("preview", {}).get("image"):
            url = node["preview"]["image"].get("url")
        print(
            f"    [{i}] {node['id']} type={node['mediaContentType']} "
            f"status={node.get('status')} alt={node.get('alt')!r} "
            f"url={url}"
        )


def extract_source_media_payloads(source_product):
    """Extract CreateMediaInput-ready dicts from source media edges.

    Returns a list of {"originalSource": url, "alt": alt, "mediaContentType": type}
    plus a parallel list of source media GIDs.
    """
    payloads = []
    source_ids = []
    skipped = []

    for edge in source_product["media"]["edges"]:
        node = edge["node"]
        source_ids.append(node["id"])
        media_type = node["mediaContentType"]
        alt = node.get("alt") or ""

        # Find a usable original URL. Different media types return it in
        # different places.
        url = None
        if media_type == "IMAGE":
            if node.get("image"):
                url = node["image"].get("url")
        elif media_type in ("VIDEO", "MODEL_3D"):
            if node.get("originalSource"):
                url = node["originalSource"].get("url")
            if not url and node.get("sources"):
                for src in node["sources"]:
                    if src.get("url"):
                        url = src["url"]
                        break
        elif media_type == "EXTERNAL_VIDEO":
            url = node.get("embedUrl")

        if not url:
            # Last resort: preview image URL (only valid for IMAGE really).
            preview = (node.get("preview") or {}).get("image") or {}
            url = preview.get("url")

        if not url:
            skipped.append({"id": node["id"], "type": media_type, "reason": "no URL available"})
            continue

        payloads.append({
            "_source_id": node["id"],
            "originalSource": url,
            "alt": alt,
            "mediaContentType": media_type,
        })

    return payloads, source_ids, skipped


def collect_variant_media_associations(source_product):
    """Return a list of variant media associations on the source product.

    Each entry: {variant_id, variant_title, sku, options, media_ids}
    """
    associations = []
    for vedge in source_product["variants"]["edges"]:
        v = vedge["node"]
        media_edges = v.get("media", {}).get("edges", [])
        if not media_edges:
            continue
        associations.append({
            "variant_id": v["id"],
            "variant_title": v.get("title"),
            "sku": v.get("sku"),
            "options": v.get("selectedOptions"),
            "media": [
                {"id": m["node"]["id"], "type": m["node"]["mediaContentType"], "alt": m["node"].get("alt")}
                for m in media_edges
            ],
        })
    return associations


def create_media_on_destination(url, headers, destination_gid, payloads):
    """Call productCreateMedia with the full batch. Returns the created media
    records (list of dicts with id, status, mediaContentType, alt)."""
    media_input = [
        {"originalSource": p["originalSource"], "alt": p["alt"], "mediaContentType": p["mediaContentType"]}
        for p in payloads
    ]
    data = gql(
        url,
        headers,
        PRODUCT_CREATE_MEDIA_MUTATION,
        {"productId": destination_gid, "media": media_input},
    )
    result = data["productCreateMedia"]

    media_user_errors = result.get("mediaUserErrors") or []
    user_errors = result.get("userErrors") or []
    if media_user_errors or user_errors:
        # Still return the media that did succeed so caller can evaluate.
        print("  productCreateMedia reported errors:")
        for e in media_user_errors:
            print(f"    mediaUserError: field={e.get('field')} code={e.get('code')} message={e.get('message')}")
        for e in user_errors:
            print(f"    userError: field={e.get('field')} message={e.get('message')}")

    return result.get("media") or [], media_user_errors, user_errors


def poll_media_until_ready(url, headers, media_ids, timeout=POLL_TIMEOUT_SECONDS, interval=POLL_INTERVAL_SECONDS):
    """Poll each media id until status is READY or FAILED. Returns dict of id -> final status."""
    pending = set(media_ids)
    statuses = {}
    deadline = time.time() + timeout
    while pending and time.time() < deadline:
        for mid in list(pending):
            try:
                data = gql(url, headers, MEDIA_STATUS_QUERY, {"id": mid})
            except Exception as e:
                print(f"    poll error for {mid}: {e}")
                continue
            node = data.get("node")
            if not node:
                # Node may not be queryable yet; skip this round.
                continue
            status = node.get("status")
            if status in ("READY", "FAILED"):
                statuses[mid] = status
                pending.discard(mid)
                print(f"    {mid} -> {status}")
        if pending:
            time.sleep(interval)
    for mid in pending:
        statuses[mid] = "TIMEOUT"
    return statuses


def delete_source_media(url, headers, source_gid, media_ids):
    data = gql(
        url,
        headers,
        PRODUCT_DELETE_MEDIA_MUTATION,
        {"productId": source_gid, "mediaIds": media_ids},
    )
    result = data["productDeleteMedia"]
    deleted = result.get("deletedMediaIds") or []
    media_user_errors = result.get("mediaUserErrors") or []
    user_errors = result.get("userErrors") or []
    return deleted, media_user_errors, user_errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Move product-level media between two Shopify products.")
    parser.add_argument("--source", required=True, help="Source product GID (remove media FROM here)")
    parser.add_argument("--destination", required=True, help="Destination product GID (add media TO here)")
    parser.add_argument("--dry-run", action="store_true", help="Query both products and report, but do not mutate")
    args = parser.parse_args()

    cfg = load_config()
    store_url = cfg.get("SHOPIFY_STORE_URL", "").replace("https://", "").replace("http://", "").strip("/")
    token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()
    if not store_url or not token:
        print("ERROR: Shopify credentials missing from config.json", file=sys.stderr)
        sys.exit(2)

    api_url = f"https://{store_url}/admin/api/{API_VERSION}/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}

    print(f"Store: {store_url}")
    print(f"Source:      {args.source}")
    print(f"Destination: {args.destination}")
    if args.dry_run:
        print("(dry-run mode — no mutations will be performed)")

    # -----------------------------------------------------------------------
    # Step 1: Query current state
    # -----------------------------------------------------------------------
    print("\n[Step 1] Querying current media on both products...")
    source = fetch_product(api_url, headers, args.source)
    destination = fetch_product(api_url, headers, args.destination)

    summarize_product("SOURCE (before)", source)
    summarize_product("DESTINATION (before)", destination)

    source_before_count = source["mediaCount"]["count"]
    dest_before_count = destination["mediaCount"]["count"]

    # -----------------------------------------------------------------------
    # Step 2: Short-circuit if source has no media
    # -----------------------------------------------------------------------
    if source_before_count == 0 or not source["media"]["edges"]:
        print("\n[Step 2] Source product has 0 media. Nothing to move — stopping.")
        print("         Please double-check which product has the images.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 3: Extract payloads + variant associations
    # -----------------------------------------------------------------------
    payloads, source_ids, skipped = extract_source_media_payloads(source)
    variant_assocs = collect_variant_media_associations(source)

    print(f"\n[Step 3] Prepared {len(payloads)} media payload(s) to copy; {len(skipped)} skipped.")
    for s in skipped:
        print(f"  SKIPPED: {s['id']} type={s['type']} reason={s['reason']}")
    if variant_assocs:
        print(f"\n  Variant media associations on source (will be severed on delete):")
        for a in variant_assocs:
            opt_str = ", ".join(f"{o['name']}={o['value']}" for o in (a["options"] or []))
            print(f"    variant {a['variant_id']} sku={a['sku']} ({opt_str}) -> {len(a['media'])} media link(s)")
            for m in a["media"]:
                print(f"      - {m['id']} type={m['type']} alt={m['alt']!r}")
    else:
        print("\n  No variant-specific media associations on source.")

    if args.dry_run:
        print("\nDry-run complete. Exiting without mutations.")
        return

    if not payloads:
        print("\nNo transferable media payloads (all skipped). Exiting without deleting source media.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 4: Create media on destination
    # -----------------------------------------------------------------------
    print(f"\n[Step 4] Creating {len(payloads)} media item(s) on destination via productCreateMedia...")
    created, media_user_errors, user_errors = create_media_on_destination(api_url, headers, args.destination, payloads)

    if not created:
        print("ERROR: productCreateMedia returned no media records. Aborting before source deletion.")
        sys.exit(3)

    created_ids = [m["id"] for m in created]
    print(f"  Created {len(created_ids)} media record(s):")
    for m in created:
        print(f"    {m['id']} type={m.get('mediaContentType')} status={m.get('status')} alt={m.get('alt')!r}")

    if media_user_errors or user_errors:
        print("ERROR: productCreateMedia reported errors; aborting before source deletion.")
        sys.exit(3)

    if len(created_ids) != len(payloads):
        print(f"ERROR: Created {len(created_ids)} but expected {len(payloads)}. Aborting before source deletion.")
        sys.exit(3)

    # -----------------------------------------------------------------------
    # Step 5: Poll until READY
    # -----------------------------------------------------------------------
    total_poll_timeout = POLL_TIMEOUT_SECONDS * max(1, len(created_ids))
    print(f"\n[Step 5] Polling destination media until READY (timeout {total_poll_timeout}s)...")
    statuses = poll_media_until_ready(api_url, headers, created_ids, timeout=total_poll_timeout)

    not_ready = {mid: st for mid, st in statuses.items() if st != "READY"}
    if not_ready:
        print("ERROR: Not all destination media reached READY. Aborting before source deletion.")
        for mid, st in not_ready.items():
            print(f"  {mid} -> {st}")
        print("  Destination was modified; review manually before retrying.")
        sys.exit(4)
    print("  All destination media READY.")

    # -----------------------------------------------------------------------
    # Step 6: Delete source media
    # -----------------------------------------------------------------------
    print(f"\n[Step 6] Deleting {len(source_ids)} media item(s) from source via productDeleteMedia...")
    deleted_ids, media_user_errors, user_errors = delete_source_media(api_url, headers, args.source, source_ids)
    print(f"  Deleted {len(deleted_ids)} media id(s).")
    if media_user_errors or user_errors:
        for e in media_user_errors:
            print(f"  mediaUserError: field={e.get('field')} code={e.get('code')} message={e.get('message')}")
        for e in user_errors:
            print(f"  userError: field={e.get('field')} message={e.get('message')}")

    # -----------------------------------------------------------------------
    # Step 7: Re-verify
    # -----------------------------------------------------------------------
    print("\n[Step 7] Re-querying both products to verify...")
    source_after = fetch_product(api_url, headers, args.source)
    destination_after = fetch_product(api_url, headers, args.destination)
    summarize_product("SOURCE (after)", source_after)
    summarize_product("DESTINATION (after)", destination_after)

    source_after_count = source_after["mediaCount"]["count"]
    dest_after_count = destination_after["mediaCount"]["count"]

    print("\n=== SUMMARY ===")
    print(f"  Source     media: {source_before_count} -> {source_after_count}")
    print(f"  Destination media: {dest_before_count} -> {dest_after_count}")
    print(f"  Moved: {len(created_ids)} (mapped from {len(source_ids)} source media ids)")
    if skipped:
        print(f"  Skipped during extraction: {len(skipped)}")
    if variant_assocs:
        print(f"  Severed variant media associations: {sum(len(a['media']) for a in variant_assocs)} "
              f"across {len(variant_assocs)} variant(s)")

    expected_source_after = 0
    expected_dest_after = dest_before_count + len(created_ids)
    ok = source_after_count == expected_source_after and dest_after_count == expected_dest_after
    if ok:
        print("\nVERIFIED: counts match expectations.")
    else:
        print(f"\nWARNING: counts do not match expectations. "
              f"Expected source={expected_source_after}, dest={expected_dest_after}.")
        sys.exit(5)


if __name__ == "__main__":
    main()
