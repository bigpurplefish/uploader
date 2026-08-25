#!/usr/bin/env python3
"""Merge 4 source products into SRW Landscape Staples as additional variants.

Target: gid://shopify/Product/10409551036708  (SKU 24725, currently 1 variant)
After: 5 variants in order [26697, 41000, 22978, 24724, 24725], all Size=6"x1"x6",
       Unit of Sale = 1 Stake / 10 Per Box / 50 Per Bag / 500 Per Box / 1000 Per Box.

Phases:
  1. Pre-fetch state for target + 4 sources (variants, inventory by loc, media, metafields, publications)
  2. Safety checks: media/metafields on sources, inventory sanity vs. expected
  3. productSet on target with new options, 5 variants, new description, new SEO
  4. Inventory restore via inventorySetQuantities per variant per location
  5. Create URL redirects (source handles -> target handle)
  6. Delete source products
  7. Verify

Dry-run by default; pass --execute to apply.
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
TARGET_PID = "gid://shopify/Product/10409551036708"
TARGET_HANDLE = "srw-landscape-staples-1000-bx"

SIZE_VALUE = '6"x1"x6"'

# Variants in exact display order. Price/cost for 41000 are FILLED IN at runtime
# from the source product's current values (placeholders here).
VARIANT_PLAN = [
    {"sku": "26697", "uos": "1 Stake",      "price": "0.10", "cost": "0.02",
     "source_pid": "gid://shopify/Product/10409556050212",
     "source_title": "Sod Staples Each"},
    {"sku": "41000", "uos": "10 Per Box",   "price": None,  "cost": None,
     "source_pid": "gid://shopify/Product/10409378971940",
     "source_title": "SRW - Landscape Staples Box=10"},
    {"sku": "22978", "uos": "50 Per Bag",   "price": "7.00", "cost": "3.71",
     "source_pid": "gid://shopify/Product/10409379758372",
     "source_title": "Srw Landscape Staples 50/Bag"},
    {"sku": "24724", "uos": "500 Per Box",  "price": "38.00","cost": "24.95",
     "source_pid": "gid://shopify/Product/10409551003940",
     "source_title": "Srw Landscape Staples 500/Bx"},
    {"sku": "24725", "uos": "1000 Per Box", "price": "60.00","cost": "39.95",
     "source_pid": None,  # the target itself, not a source to delete
     "source_title": None},
]

# SKUs for each source product that will be deleted after merge
SOURCE_PRODUCTS = [v for v in VARIANT_PLAN if v["source_pid"]]

DESCRIPTION_HTML = (
    '<p>Lock landscape fabric, weed barrier, sod, and erosion blankets down with '
    'SRW Landscape Staples. Drive these 6"x1"x6" heavy-gauge steel staples with a '
    'hammer and trust them to hold against wind, water, and heavy traffic.</p>'

    '<p>Reach for them on every hardscape and planting job: pin geotextile under '
    'pavers and retaining walls, anchor silt fence and erosion blankets on slopes, '
    'stake fresh sod and drip irrigation, and secure weed barrier around beds. The '
    '1" crown grips fabric without tearing, and the 6" leg bites into compacted '
    'soil and crushed stone.</p>'

    '<p>Pick the pack size that fits the job:</p>'
    '<ul>'
    '<li><strong>Single stake:</strong> Grab one for repairs and touch-ups.</li>'
    '<li><strong>10 per box:</strong> A small planting bed or single fabric run.</li>'
    '<li><strong>50 per bag:</strong> A weekend garden or round of sod staking.</li>'
    '<li><strong>500 per box:</strong> A full landscape fabric install or erosion-blanket slope.</li>'
    '<li><strong>1000 per box:</strong> Keep the crew stocked for paver bases and large sites.</li>'
    '</ul>'

    '<p>Keep a box on the truck and stop chasing loose fabric across the site.</p>'
)

SEO_TITLE = 'SRW Landscape Staples 6" \u2014 Stakes, Bags & Boxes of 10/50/500/1000'
SEO_DESCRIPTION = (
    'SRW 6" heavy-gauge landscape staples for fabric, sod, and erosion control. '
    'Single stakes, 10/50/500/1000 packs \u2014 pick the right size for the job.'
)

# ---------- GraphQL ----------

PRODUCT_DETAIL = """
query($id:ID!){
  product(id:$id){
    id title handle status vendor productType tags
    descriptionHtml
    seo { title description }
    category { id fullName }
    media(first: 50) {
      edges {
        node {
          id alt mediaContentType
          ... on MediaImage { image { url altText } }
        }
      }
    }
    metafields(first: 50) {
      edges { node { id namespace key type value } }
    }
    resourcePublications(first: 20, onlyPublished: true) {
      edges { node { publication { id name } } }
    }
    options { id name position values }
    variants(first: 50) {
      edges { node {
        id sku title price inventoryPolicy
        selectedOptions { name value }
        metafields(first: 30) { edges { node { id namespace key type value } } }
        inventoryItem {
          id
          unitCost { amount }
          measurement { weight { value unit } }
          inventoryLevels(first: 20) {
            edges { node {
              location { id name }
              quantities(names: ["available"]) { name quantity }
            } }
          }
        }
      } }
    }
  }
}
"""

PRODUCT_SET = """
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
  productSet(synchronous: $synchronous, input: $input) {
    product {
      id handle title
      seo { title description }
      options { id name position values }
      variants(first: 20) {
        edges { node {
          id sku title price
          selectedOptions { name value }
          inventoryItem {
            id
            unitCost { amount }
            measurement { weight { value unit } }
          }
        } }
      }
    }
    userErrors { field message }
  }
}
"""

INVENTORY_SET_QUANTITIES = """
mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { id }
    userErrors { field message }
  }
}
"""

URL_REDIRECT_CREATE = """
mutation urlRedirectCreate($input: UrlRedirectInput!) {
  urlRedirectCreate(urlRedirect: $input) {
    urlRedirect { id path target }
    userErrors { field message }
  }
}
"""

PRODUCT_DELETE = """
mutation productDelete($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
    userErrors { field message }
  }
}
"""


def api_url(cfg):
    s = cfg["SHOPIFY_STORE_URL"].replace("https://", "").replace("http://", "").strip("/")
    return f"https://{s}/admin/api/{API_VERSION}/graphql.json"


def headers(cfg):
    return {"Content-Type": "application/json",
            "X-Shopify-Access-Token": cfg["SHOPIFY_ACCESS_TOKEN"]}


def gql(cfg, q, v=None, retries=5):
    last_err = None
    for _ in range(retries):
        r = requests.post(api_url(cfg), json={"query": q, "variables": v or {}},
                          headers=headers(cfg), timeout=120)
        r.raise_for_status()
        d = r.json()
        if "errors" in d:
            if any("THROTTLED" in str(e).upper() for e in d["errors"]):
                time.sleep(2); last_err = d["errors"]; continue
            raise RuntimeError(f"GraphQL errors: {d['errors']}")
        return d["data"]
    raise RuntimeError(f"retries exhausted: {last_err}")


def fetch_product(cfg, pid):
    return gql(cfg, PRODUCT_DETAIL, {"id": pid})["product"]


def collect_inventory(variant):
    item = variant.get("inventoryItem") or {}
    levels = (item.get("inventoryLevels") or {}).get("edges") or []
    rows = []
    for e in levels:
        loc = e["node"]["location"]
        qty = 0
        for q in e["node"].get("quantities") or []:
            if q.get("name") == "available":
                qty = q.get("quantity") or 0
                break
        rows.append({"locationId": loc["id"], "locationName": loc["name"], "quantity": qty})
    return rows


def summarize_product(p, label=""):
    print(f"\n-- {label} --" if label else "")
    print(f"  {p['id']}  handle={p['handle']}  status={p['status']}")
    print(f"  title: {p['title']!r}")
    print(f"  seo.title: {p.get('seo',{}).get('title')!r}  seo.desc: {p.get('seo',{}).get('description')!r}")
    print(f"  description chars: {len(p.get('descriptionHtml') or '')}")
    print(f"  options: {[(o['name'], o['position'], o['values']) for o in p.get('options') or []]}")
    print(f"  media count: {len(p.get('media',{}).get('edges',[]))}  metafields: {len(p.get('metafields',{}).get('edges',[]))}")
    pubs = [e['node']['publication']['name'] for e in p.get('resourcePublications',{}).get('edges',[])]
    print(f"  publications: {pubs}")
    for e in p['variants']['edges']:
        v = e['node']
        item = v.get('inventoryItem') or {}
        cost = (item.get('unitCost') or {}).get('amount')
        wt = (item.get('measurement') or {}).get('weight') or {}
        opts = ", ".join(f"{o['name']}={o['value']}" for o in v['selectedOptions'])
        inv = collect_inventory(v)
        inv_sum = sum(i['quantity'] for i in inv)
        inv_str = "; ".join(f"{i['locationName']}={i['quantity']}" for i in inv)
        vmf_count = len(v.get('metafields',{}).get('edges',[]))
        print(f"    SKU={v['sku']:<8} ${v['price']:<7} cost={cost} wt={wt.get('value')}{wt.get('unit')}  [{opts}]  "
              f"variant_id={v['id']}  inventory_item={item.get('id')}  vmf={vmf_count}  inv_total={inv_sum} [{inv_str}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    mode = "EXECUTE" if args.execute else "DRY RUN"
    log.info(f"Merge SRW staples mode={mode}")

    # ---------- Phase 1: Pre-fetch ----------
    print("\n" + "=" * 72)
    print("PHASE 1 — PRE-FETCH CURRENT STATE")
    print("=" * 72)

    target = fetch_product(cfg, TARGET_PID)
    summarize_product(target, "TARGET (SRW Landscape Staples)")

    sources = {}
    for sp in SOURCE_PRODUCTS:
        pd = fetch_product(cfg, sp["source_pid"])
        sources[sp["sku"]] = pd
        summarize_product(pd, f"SOURCE SKU={sp['sku']} ({sp['source_title']})")

    # Build a per-SKU inventory-by-location map
    per_sku_inventory = {}
    for e in target['variants']['edges']:
        v = e['node']
        per_sku_inventory[v['sku']] = collect_inventory(v)
    for sku, p in sources.items():
        for e in p['variants']['edges']:
            v = e['node']
            if v['sku'] == sku:
                per_sku_inventory[sku] = collect_inventory(v)
                break

    # ---------- Phase 2: Safety checks ----------
    print("\n" + "=" * 72)
    print("PHASE 2 — SAFETY CHECKS")
    print("=" * 72)

    problems = []

    # Media on any source?
    for sku, p in sources.items():
        media = p.get('media',{}).get('edges',[])
        if media:
            problems.append(f"SOURCE {sku} has {len(media)} media entries — would be lost on delete")
            for m in media:
                n = m['node']
                img = n.get('image') or {}
                print(f"    media: {n['id']} type={n.get('mediaContentType')} url={img.get('url')} alt={img.get('altText')}")
        else:
            print(f"  [ok] source {sku}: 0 media")

    # Metafields on source products (product-level)
    for sku, p in sources.items():
        mf = p.get('metafields',{}).get('edges',[])
        if mf:
            print(f"  [flag] source {sku}: {len(mf)} product metafields")
            for m in mf:
                n = m['node']
                print(f"    mf: {n['namespace']}.{n['key']} type={n['type']} val={(n['value'] or '')[:80]!r}")
        else:
            print(f"  [ok] source {sku}: 0 product metafields")

    # Variant-level metafields on sources
    for sku, p in sources.items():
        for e in p['variants']['edges']:
            v = e['node']
            vmf = v.get('metafields',{}).get('edges',[])
            if vmf:
                print(f"  [flag] source {sku} variant {v['sku']}: {len(vmf)} variant metafields")
                for m in vmf:
                    n = m['node']
                    print(f"    vmf: {n['namespace']}.{n['key']} type={n['type']} val={(n['value'] or '')[:80]!r}")
            else:
                print(f"  [ok] source {sku}: 0 variant metafields")

    # Inventory sanity vs. expected from user
    expected = {"26697": 250, "41000": 149, "22978": 50, "24724": 6, "24725": 7}
    print("\n  Inventory sanity check (actual vs expected):")
    for sku, exp in expected.items():
        actual_rows = per_sku_inventory.get(sku, [])
        actual_total = sum(r['quantity'] for r in actual_rows)
        tag = "[ok]" if actual_total == exp else f"[DRIFT actual={actual_total}, expected={exp}]"
        print(f"    SKU {sku}: actual_total={actual_total}  expected={exp}  {tag}  by_loc={actual_rows}")
        if abs(actual_total - exp) > max(5, exp * 0.2):  # tolerate small drift, flag large
            problems.append(f"SKU {sku} inventory drift: actual={actual_total}, expected={exp}")

    # Resolve SKU 41000 price/cost from source
    src_41000 = sources.get("41000")
    price_41000, cost_41000 = None, None
    if src_41000:
        for e in src_41000['variants']['edges']:
            v = e['node']
            if v['sku'] == "41000":
                price_41000 = v['price']
                item = v.get('inventoryItem') or {}
                cost_41000 = (item.get('unitCost') or {}).get('amount')
                break
    print(f"\n  SKU 41000 resolved from source: price={price_41000} cost={cost_41000}")
    # Inject into plan
    for vp in VARIANT_PLAN:
        if vp["sku"] == "41000":
            vp["price"] = price_41000 if price_41000 is not None else "8.00"
            vp["cost"] = cost_41000  # may be None — that's fine
            if cost_41000 is None:
                print("    [note] SKU 41000 cost is null on source; will leave cost unset on new variant")
            break

    if problems:
        print("\n  SAFETY WARNINGS:")
        for p in problems:
            print(f"    !! {p}")

    # ---------- Plan summary ----------
    print("\n" + "=" * 72)
    print("PLAN")
    print("=" * 72)
    print(f"Target: {TARGET_PID}  handle={target['handle']}")
    print(f"Title:  stays 'SRW Landscape Staples'")
    print(f"Options: [Size (pos 1), Unit of Sale (pos 2)]")
    print(f"Variants (new, in order):")
    for vp in VARIANT_PLAN:
        print(f"  #{VARIANT_PLAN.index(vp)+1} SKU={vp['sku']:<6} Size={SIZE_VALUE!r:<12} UoS={vp['uos']!r:<14} ${vp['price']} cost={vp['cost']}")
    print(f"Description new chars: {len(DESCRIPTION_HTML)}")
    print(f"SEO.title new ({len(SEO_TITLE)} chars): {SEO_TITLE!r}")
    print(f"SEO.description new ({len(SEO_DESCRIPTION)} chars): {SEO_DESCRIPTION!r}")
    assert len(SEO_TITLE) <= 70, f"SEO title too long: {len(SEO_TITLE)}"
    assert len(SEO_DESCRIPTION) <= 160, f"SEO desc too long: {len(SEO_DESCRIPTION)}"
    print(f"URL redirects to create (4): source_handle -> /products/{TARGET_HANDLE}")
    for sku, p in sources.items():
        print(f"    /products/{p['handle']}  ->  /products/{TARGET_HANDLE}")
    print(f"Source products to DELETE (4):")
    for sp in SOURCE_PRODUCTS:
        p = sources[sp['sku']]
        print(f"    SKU {sp['sku']}  {sp['source_pid']}  handle={p['handle']}")

    if not args.execute:
        print("\nDRY RUN — rerun with --execute to apply.")
        if problems:
            print(f"(Note: {len(problems)} safety warnings above — review before executing.)")
        return 0

    # Hard-stop gate: media loss is unrecoverable, so block on that.
    # For metafields, only block on UNKNOWN ones. Known-safe: purchase_options
    # (per-product delivery/pickup setting, identical on target so nothing to copy),
    # title_tag/description_tag (SEO fallback overwritten by productSet.seo).
    SAFE_MF_KEYS = {('custom', 'purchase_options'), ('global', 'title_tag'),
                    ('global', 'description_tag')}
    # Build target metafield map to detect source-vs-target differences
    target_mf = {}
    for e in target.get('metafields',{}).get('edges',[]):
        n = e['node']
        target_mf[(n['namespace'], n['key'])] = n['value']

    hard_stop = False
    for sku, p in sources.items():
        if p.get('media',{}).get('edges'):
            log.error(f"HARD STOP: source SKU {sku} has media — extract/transfer first before delete")
            hard_stop = True
        for e in p.get('metafields',{}).get('edges',[]):
            n = e['node']
            key = (n['namespace'], n['key'])
            if key in SAFE_MF_KEYS:
                log.info(f"  safe-drop product mf {sku}: {n['namespace']}.{n['key']} (known safe)")
                continue
            tgt_val = target_mf.get(key)
            if tgt_val == n['value']:
                log.info(f"  safe-drop product mf {sku}: {n['namespace']}.{n['key']} (identical to target)")
                continue
            log.error(f"HARD STOP: source SKU {sku} has unreviewed metafield {n['namespace']}.{n['key']} value={n['value']!r}")
            hard_stop = True
        for e in p['variants']['edges']:
            for me in e['node'].get('metafields',{}).get('edges',[]):
                mn = me['node']
                log.error(f"HARD STOP: source SKU {sku} variant metafield {mn['namespace']}.{mn['key']} — review first")
                hard_stop = True
    if hard_stop:
        log.error("Stopping due to hard-stop conditions. No mutations performed.")
        return 1

    # ---------- Phase 3: productSet ----------
    print("\n" + "=" * 72)
    print("PHASE 3 — productSet")
    print("=" * 72)

    # Preserve weight from existing SKU 24725 variant
    weight_value, weight_unit = None, None
    for e in target['variants']['edges']:
        v = e['node']
        if v['sku'] == "24725":
            wt = ((v.get('inventoryItem') or {}).get('measurement') or {}).get('weight') or {}
            weight_value = wt.get('value')
            weight_unit = wt.get('unit')
            break

    variants_input = []
    for vp in VARIANT_PLAN:
        vi = {
            "optionValues": [
                {"optionName": "Size", "name": SIZE_VALUE},
                {"optionName": "Unit of Sale", "name": vp["uos"]},
            ],
            "price": vp["price"],
            "sku": vp["sku"],
            "inventoryPolicy": "DENY",
            "inventoryItem": {
                "tracked": True,
                "sku": vp["sku"],
            },
        }
        if vp["cost"] is not None:
            vi["inventoryItem"]["cost"] = str(vp["cost"])
        # Keep weight on the 1000-per-box since that's the original measured unit;
        # the smaller pack sizes will be left to the store admin to set.
        if vp["sku"] == "24725" and weight_value and weight_unit:
            vi["inventoryItem"]["measurement"] = {
                "weight": {"value": float(weight_value), "unit": weight_unit}
            }
        variants_input.append(vi)

    product_input = {
        "id": TARGET_PID,
        "title": target['title'],  # preserve "SRW Landscape Staples"
        "descriptionHtml": DESCRIPTION_HTML,
        "seo": {"title": SEO_TITLE, "description": SEO_DESCRIPTION},
        "productOptions": [
            {"name": "Size", "position": 1, "values": [{"name": SIZE_VALUE}]},
            {"name": "Unit of Sale", "position": 2,
             "values": [{"name": v["uos"]} for v in VARIANT_PLAN]},
        ],
        "variants": variants_input,
    }

    log.info("Calling productSet (synchronous=true)...")
    data = gql(cfg, PRODUCT_SET, {"synchronous": True, "input": product_input})
    ue = data["productSet"]["userErrors"]
    if ue:
        log.error(f"productSet userErrors: {ue}")
        log.error("STOPPING — not deleting source products.")
        return 1
    result = data["productSet"]["product"]
    log.info(f"  OK  id={result['id']}  title={result['title']!r}")
    log.info(f"  seo.title: {result['seo']['title']!r}")
    log.info(f"  seo.description: {result['seo']['description']!r}")
    new_variants = [e['node'] for e in result['variants']['edges']]
    # Map SKU -> (variantId, inventoryItemId)
    sku_to_ids = {v['sku']: {"variantId": v['id'],
                             "inventoryItemId": v['inventoryItem']['id']}
                  for v in new_variants}
    log.info(f"  new variants: {len(new_variants)}")
    for v in new_variants:
        opts = ", ".join(f"{o['name']}={o['value']}" for o in v['selectedOptions'])
        cost = (v.get('inventoryItem',{}).get('unitCost') or {}).get('amount')
        log.info(f"    SKU={v['sku']:<8} id={v['id']}  invItem={v['inventoryItem']['id']}  ${v['price']} cost={cost}  [{opts}]")

    # ---------- Phase 4: Inventory restore ----------
    print("\n" + "=" * 72)
    print("PHASE 4 — Inventory restore")
    print("=" * 72)
    # Build quantities list across all 5 SKUs
    quantities_list = []
    for sku, rows in per_sku_inventory.items():
        if sku not in sku_to_ids:
            log.warning(f"SKU {sku} not in new variants — skipping inventory restore for it")
            continue
        inv_item_id = sku_to_ids[sku]['inventoryItemId']
        for r in rows:
            if r['quantity'] is None:
                continue
            quantities_list.append({
                "inventoryItemId": inv_item_id,
                "locationId": r['locationId'],
                "quantity": int(r['quantity']),
            })
            log.info(f"  restore  SKU={sku:<8} loc={r['locationName']}  qty={r['quantity']}")
    if quantities_list:
        ir = gql(cfg, INVENTORY_SET_QUANTITIES, {"input": {
            "name": "available",
            "reason": "correction",
            "ignoreCompareQuantity": True,
            "quantities": quantities_list,
        }})
        ue_inv = ir["inventorySetQuantities"]["userErrors"]
        if ue_inv:
            log.error(f"inventorySetQuantities userErrors: {ue_inv}")
        else:
            log.info(f"  OK restored {len(quantities_list)} quantities")

    # ---------- Phase 5: URL redirects ----------
    print("\n" + "=" * 72)
    print("PHASE 5 — URL redirects")
    print("=" * 72)
    redirects_created = []
    for sku, p in sources.items():
        src_handle = p['handle']
        src_path = f"/products/{src_handle}"
        tgt_path = f"/products/{TARGET_HANDLE}"
        if src_handle == TARGET_HANDLE:
            log.info(f"  skip redirect: source handle matches target handle ({src_handle})")
            continue
        log.info(f"  creating redirect  {src_path}  ->  {tgt_path}")
        rd = gql(cfg, URL_REDIRECT_CREATE, {"input": {"path": src_path, "target": tgt_path}})
        ue_r = rd["urlRedirectCreate"]["userErrors"]
        if ue_r:
            log.error(f"  !! redirect errors for {src_handle}: {ue_r}")
        else:
            redirects_created.append({"sku": sku, "path": src_path, "target": tgt_path,
                                      "id": rd["urlRedirectCreate"]["urlRedirect"]["id"]})
            log.info(f"     OK  id={rd['urlRedirectCreate']['urlRedirect']['id']}")

    # ---------- Phase 6: Delete source products ----------
    print("\n" + "=" * 72)
    print("PHASE 6 — Delete source products")
    print("=" * 72)
    deleted = []
    for sp in SOURCE_PRODUCTS:
        log.info(f"  deleting source SKU {sp['sku']}  {sp['source_pid']}")
        dd = gql(cfg, PRODUCT_DELETE, {"input": {"id": sp["source_pid"]}})
        ue_d = dd["productDelete"]["userErrors"]
        if ue_d:
            log.error(f"    !! delete errors: {ue_d}")
        else:
            deleted_id = dd["productDelete"]["deletedProductId"]
            deleted.append({"sku": sp["sku"], "deletedId": deleted_id})
            log.info(f"    OK deleted {deleted_id}")
        time.sleep(0.5)

    # ---------- Phase 7: Verify ----------
    print("\n" + "=" * 72)
    print("PHASE 7 — Final verification")
    print("=" * 72)
    time.sleep(1)
    final = fetch_product(cfg, TARGET_PID)
    summarize_product(final, "FINAL STATE — SRW Landscape Staples")

    # Redirect HTTP check
    print("\n  Redirect HTTP checks (HEAD, follow=0):")
    store_host = cfg["SHOPIFY_STORE_URL"].replace("https://","").replace("http://","").strip("/")
    for r in redirects_created:
        check_url = f"https://{store_host}{r['path']}"
        try:
            resp = requests.get(check_url, allow_redirects=False, timeout=15)
            log.info(f"    {check_url}  ->  HTTP {resp.status_code}  Location: {resp.headers.get('Location')}")
        except Exception as e:
            log.warning(f"    HTTP check failed for {check_url}: {e}")

    print("\n" + "=" * 72)
    print("COMPLETED")
    print("=" * 72)
    print(f"Storefront: https://{store_host}/products/{final['handle']}")
    print(f"Admin:      https://{store_host}/admin/products/{TARGET_PID.rsplit('/',1)[-1]}")
    print(f"Redirects created: {len(redirects_created)}")
    print(f"Sources deleted:   {len(deleted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
