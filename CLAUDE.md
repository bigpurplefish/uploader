# CLAUDE.md — uploader

Python tool that uploads pre-categorized products to Shopify via GraphQL Admin API 2025-10. Handles products, variants, images, 3D models, videos, metafields, and collection creation. **See root `garoppos/CLAUDE.md` for pipeline-wide Shopify rules (descriptionHtml, status=ACTIVE, `media_content_type`, option/variant/image caps, publishing channels, color swatches).**

**Version:** 2.6.0 | **API:** 2025-10 | **Repo:** https://github.com/bigpurplefish/uploader | **Store:** c2280b-es.myshopify.com

Input arrives fully processed from upscaler → `product_type`, `tags`, `body_html`, `weight`, and image CDN URLs already set. The uploader does not enhance or categorize content.

## Entry Points & Commands

| Command | Purpose |
|---------|---------|
| `python3 gui.py` | GUI (ttkbootstrap `darkly` theme) |
| `python3 main.py --input products.json --output results.json` | CLI — resume mode (default) |
| `python3 main.py --input ... --output ... --mode overwrite --verbose` | Overwrite existing products |
| `pytest tests/ -v` | Tests |
| `pip install -r requirements.txt` | Install (`ttkbootstrap>=1.10.0`, `requests>=2.28.0`) |

## Module Layout

Source in `uploader_modules/`:

| File | Purpose |
|------|---------|
| `shopify_api.py` | GraphQL client, mutations, staged uploads |
| `product_processing.py` | Per-product orchestration, media attach, variant-image linking |
| `config.py` | `config.json` load/save |
| `state.py` | `upload_state.json` resume checkpointing |
| `taxonomy_data.py` | Shopify taxonomy search + cache |

### Key functions (with line refs)

| Function | File:Line | Role |
|----------|-----------|------|
| `process_products()` | `product_processing.py:1346` | Per-product orchestration |
| `process_collections()` | `product_processing.py:815` | 3-level collection creation |
| `is_shopify_cdn_url()` | `product_processing.py:1010` | URL validation |
| `search_shopify_taxonomy()` | `product_processing.py:1186` | Taxonomy match |
| `get_taxonomy_id()` | `product_processing.py:1272` | Taxonomy ID lookup |
| Media type read | `product_processing.py:1766,1811` | Reads `media_content_type` for MODEL_3D / VIDEO |

## Product Creation — Use `productSet`, Never `productCreate`

```graphql
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!)
```

- `synchronous: true` mode with `ProductSetInput`
- Creates product + options + variants in a single call. No separate `productVariantsBulkCreate` for new products
- `productOptions` entries MUST include `position` field
- Variant `optionValues` use `{optionName, name}` shape
- `productVariantsBulkCreate` is only used on the existing-product overwrite path

## Media Attach — Single `productCreateMedia` Call

After product creation, attach ALL media in ONE `productCreateMedia` call. Order: images → 3D models → videos. Timeout 120s. Mutation uses inline fragments for `MediaImage`, `Model3d`, `Video`.

**Do NOT split into per-type calls.** Separate calls race; 3D models finish first and get lower position numbers, appearing before images in the Shopify gallery.

Images must already be on Shopify CDN (`cdn.shopify.com`). 3D model URLs in `media[].sources[].url` may be external — script stages+uploads them (`stagedUploadsCreate` → upload → `fileCreate`). Reads `media_content_type` from the JSON (NOT `media_type`).

## Variant ↔ Image Linking

Images are linked to variants by parsing `#OPTION1#OPTION2#OPTION3` hashtags from image alt text and matching against variant `selectedOptions` values. The uploader does NOT read an `image_id` field on variants.

## Collections — 3-Level Taxonomy

| Level | Rule | Source |
|-------|------|--------|
| Department | `PRODUCT_TYPE EQUALS <x>` | `product_type` |
| Category | `TAG EQUALS <x>` | tags[0] |
| Subcategory | `TAG EQUALS <cat>` AND `TAG EQUALS <sub>` | tags[0] + tags[1] |

Search by exact title before create to avoid duplicates. IDs persisted to `collections.json`.

## State Files

| File | Purpose | Lifecycle |
|------|---------|-----------|
| `upload_state.json` | `last_processed_index` + results for resume | Created on start, deleted on success |
| `collections.json` | Created collection IDs/handles | Persistent |
| `products.json` | Full product restore backup | Created before modifications |
| `product_taxonomy.json` | Shopify taxonomy ID cache | Persistent |
| `config.json` | Credentials + paths (gitignored) | Auto-saved on field change via `trace_add` |

Resume pattern: `start_index = state.get("last_processed_index", -1) + 1`; save state after each product.

## Product Creation Flow (`process_products`)

1. Scan for non-CDN URLs — abort if any image isn't on `cdn.shopify.com`
2. Load `upload_state.json`, resume from `last_processed_index + 1`
3. For each product: extract taxonomy → `search_shopify_taxonomy` → stage-upload 3D models → build `ProductSetInput` (includes variants) → `productSet` call → single `productCreateMedia` (images, then models, then videos) → publish to channels → save state
4. Write output JSON

## GraphQL Mutations Used

```graphql
mutation productSet($synchronous: Boolean!, $input: ProductSetInput!)
mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!)  # overwrite path only
mutation collectionCreate($input: CollectionInput!)
mutation stagedUploadsCreate($input: [StagedUploadInput!]!)
mutation fileCreate($files: [FileCreateInput!]!)
mutation productCreateMedia(...)
```

Base URL: `https://{SHOPIFY_STORE_URL}/admin/api/2025-10/graphql.json`
Headers: `Content-Type: application/json`, `X-Shopify-Access-Token: <token>`
All mutations return `userErrors` — check before treating as success.

## GUI Architecture

- Main thread: tkinter event loop. Worker thread (daemon): processing. Cross-thread updates via `app.after()` / queue
- Layout: col0 label+tooltip, col1 input, col2 browse, col3 delete. Tooltips on all inputs.

## Git Workflow

Proactive commit strategy: after a significant change, ASK "commit and push?" and wait for explicit approval. Don't commit WIP/experimental changes or typos (unless requested). Group related changes. Commit message includes `Co-Authored-By` footer. Remote: `git@github.com:bigpurplefish/uploader.git`.

## Constraints

- 0.5s delay between products; GraphQL cost-based rate limiting applies
- Whole input JSON loaded in memory — fine for <10,000 products
- Uploader does NOT upload images; they must be pre-uploaded to Shopify CDN by the upscaler
- API 2025-10 supported until Oct 2026. On bump: change URL, review changelog, test all mutations, update `requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md`

## Reference Docs

| Area | Document |
|------|----------|
| Input schema | `requirements/INPUT_FORMAT_REQUIREMENTS.md` |
| Shopify API compat | `requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md` |
| OpenAI API | `requirements/OPENAI_API_REQUIREMENTS.md` |
| Org Python standards | `/Users/moosemarketer/Code/shared-docs/python/` (COMPLIANCE_CHECKLIST, LOGGING_REQUIREMENTS, GRAPHQL_OUTPUT_REQUIREMENTS, GUI_DESIGN_REQUIREMENTS, GIT_WORKFLOW) |
| Theme (sibling repo) | `/Users/moosemarketer/Code/garoppos/shopify/` |

Use Context7 MCP (`resolve-library-id`, `get-library-docs`) for current Shopify/requests/ttkbootstrap docs rather than guessing signatures.

## Agent Delegation

Auto-delegate without asking. Agents live in `.claude/agents/`:

| Agent | For |
|-------|-----|
| `requirements-analyst` | Read/interpret requirements before implementation |
| `shopify-api-specialist` | All Shopify GraphQL work |
| `gui-specialist` | tkinter/ttkbootstrap/threading |
| `ai-integration-specialist` | OpenAI/Claude API |
| `test-writer` | pytest, fixtures, coverage |
| `code-reviewer` | Pre-commit review |
| `product-taxonomy-specialist` | Categorization, collection rules |

(`shopify-theme-specialist` lives in the sibling `../shopify/` repo.)

Feature pattern: `requirements-analyst` → domain specialist(s) → `test-writer` → `code-reviewer`. Never implement Shopify features without first consulting the requirements docs.

Slash commands in `.claude/commands/`: `/implement-feature`, `/review`, `/test`, `/document`, `/fix-api-error`, `/add-shopify-mutation`, `/debug-gui`.
