"""
Product and collection processing logic for Shopify Product Uploader.

This module contains the main business logic for processing products and collections.
"""

import json
import os
import time
import logging
import requests
from datetime import datetime

from .config import log_and_status, setup_logging, SCRIPT_VERSION
from .state import (
    load_collections, save_collections, load_products, save_products,
    load_taxonomy_cache, update_product_in_restore
)
from .shopify_api import (
    get_sales_channel_ids, get_default_location_id, search_collection,
    create_collection, publish_collection_to_channels, publish_product_to_channels,
    delete_shopify_product, create_metafield_definition,
    upload_model_to_shopify, get_taxonomy_id, ensure_menu_items_for_product
)
from .utils import (
    extract_category_subcategory, extract_unique_option_values,
    key_to_label, validate_image_urls, validate_image_alt_tags_for_filtering,
    generate_image_filter_hashtags
)


def process_collections(products, cfg, status_fn):
    """
    Process and create collections for products based on taxonomy.
    Creates department, category, and subcategory collections.

    Args:
        products: List of product dictionaries
        cfg: Configuration dictionary
        status_fn: Status update function

    Returns:
        Tuple of (success, created_count, existing_count, failed_count)
    """
    try:
        # Load collections tracking data
        collections_data = load_collections()
        
        # Extract all unique departments, categories, and subcategories
        collections_to_create = {
            "department": {},  # Based on product_type
            "category": {},    # Based on tags
            "subcategory": {}  # Based on compound tag rules
        }
        
        for product in products:
            # Department: based on product_type
            product_type = product.get('product_type', '').strip()
            if product_type:
                dept_key = product_type.lower()
                if dept_key not in collections_to_create["department"]:
                    collections_to_create["department"][dept_key] = {
                        "name": product_type,
                        "rules": [
                            {
                                "column": "TYPE",
                                "relation": "EQUALS",
                                "condition": product_type
                            }
                        ]
                    }
            
            # Category and Subcategory: based on tags or metafields
            category, subcategory = extract_category_subcategory(product)
            
            if category:
                cat_key = category.lower()
                if cat_key not in collections_to_create["category"]:
                    collections_to_create["category"][cat_key] = {
                        "name": category,
                        "parent_department": product_type,  # Track parent department
                        "rules": [
                            {
                                "column": "TAG",
                                "relation": "EQUALS",
                                "condition": category
                            }
                        ]
                    }

            if subcategory and category:
                subcat_key = f"{category.lower()}_{subcategory.lower()}"
                if subcat_key not in collections_to_create["subcategory"]:
                    collections_to_create["subcategory"][subcat_key] = {
                        "name": subcategory,
                        "parent_category": category,  # Track parent category
                        "grandparent_department": product_type,  # Track grandparent department
                        "rules": [
                            {
                                "column": "TAG",
                                "relation": "EQUALS",
                                "condition": category
                            },
                            {
                                "column": "TAG",
                                "relation": "EQUALS",
                                "condition": subcategory
                            }
                        ]
                    }
        
        log_and_status(status_fn, "\n" + "=" * 80)
        log_and_status(status_fn, "CREATING COLLECTIONS")
        log_and_status(status_fn, "=" * 80)

        collections_created = 0
        collections_existing = 0
        collections_failed = 0

        # Track handles for hierarchy metafields
        # Maps collection name (lowercase) to handle
        department_handles = {}
        category_handles = {}

        # Process each level in order
        for level in ['department', 'category', 'subcategory']:
            if level not in collections_to_create:
                continue
            
            for collection_key, collection_info in collections_to_create[level].items():
                collection_name = collection_info["name"]
                rules = collection_info["rules"]
                
                log_and_status(
                    status_fn,
                    f"  Processing {level} collection: {collection_name}",
                    ui_msg=f"  Processing collection: {collection_name}"
                )
                
                # Check if already exists in tracking
                existing = next(
                    (c for c in collections_data["collections"] 
                     if c.get("name", "").lower() == collection_name.lower()),
                    None
                )
                
                if existing:
                    log_and_status(status_fn, f"    ✓ Collection already tracked: {existing.get('id')}")

                    # Store handle for hierarchy lookups
                    handle = existing.get('handle', '')
                    if level == 'department' and handle:
                        department_handles[collection_name.lower()] = handle
                    elif level == 'category' and handle:
                        category_handles[collection_name.lower()] = handle

                    # Publish already-tracked collection to sales channels (in case it wasn't published)
                    log_and_status(status_fn, f"    Publishing to sales channels...")
                    sales_channel_ids = get_sales_channel_ids(cfg)
                    if sales_channel_ids:
                        if publish_collection_to_channels(existing.get('id'), sales_channel_ids, cfg):
                            log_and_status(
                                status_fn,
                                f"    ✅ Published to Online Store and Point of Sale",
                                ui_msg="    ✅ Published to channels"
                            )
                        else:
                            log_and_status(
                                status_fn,
                                f"    ⚠️  Failed to publish collection to sales channels",
                                "warning"
                            )

                    collections_existing += 1
                    time.sleep(0.5)
                    continue
                
                # Search in Shopify
                log_and_status(status_fn, f"    Searching in Shopify...")
                found_collection = search_collection(collection_name, cfg)
                
                if found_collection:
                    log_and_status(
                        status_fn,
                        f"    ✓ Collection already exists in Shopify: {found_collection['id']}",
                        ui_msg="    ✓ Collection exists"
                    )

                    # Store handle for hierarchy lookups
                    handle = found_collection.get('handle', '')
                    if level == 'department' and handle:
                        department_handles[collection_name.lower()] = handle
                    elif level == 'category' and handle:
                        category_handles[collection_name.lower()] = handle

                    # Publish existing collection to sales channels (in case it wasn't published)
                    log_and_status(status_fn, f"    Publishing to sales channels...")
                    sales_channel_ids = get_sales_channel_ids(cfg)
                    if sales_channel_ids:
                        if publish_collection_to_channels(found_collection['id'], sales_channel_ids, cfg):
                            log_and_status(
                                status_fn,
                                f"    ✅ Published to Online Store and Point of Sale",
                                ui_msg="    ✅ Published to channels"
                            )
                        else:
                            log_and_status(
                                status_fn,
                                f"    ⚠️  Failed to publish collection to sales channels",
                                "warning"
                            )

                    # Add to tracking
                    collections_data["collections"].append({
                        "name": collection_name,
                        "level": level,
                        "id": found_collection["id"],
                        "handle": found_collection["handle"],
                        "status": "existing",
                        "created_at": datetime.now().isoformat()
                    })
                    save_collections(collections_data)

                    collections_existing += 1
                    time.sleep(0.5)
                    continue

                # Create new collection (without AI-generated description)
                log_and_status(status_fn, f"    Creating new collection...")

                # Build hierarchy metafields based on level
                hierarchy_metafields = [
                    {
                        "namespace": "hierarchy",
                        "key": "level",
                        "value": level,
                        "type": "single_line_text_field"
                    }
                ]

                if level == 'category':
                    # Category has a parent department
                    parent_dept = collection_info.get("parent_department", "")
                    if parent_dept:
                        parent_handle = department_handles.get(parent_dept.lower(), "")
                        if parent_handle:
                            hierarchy_metafields.append({
                                "namespace": "hierarchy",
                                "key": "parent_handle",
                                "value": parent_handle,
                                "type": "single_line_text_field"
                            })
                            log_and_status(status_fn, f"    Adding hierarchy: parent_handle={parent_handle}")

                elif level == 'subcategory':
                    # Subcategory has parent category and grandparent department
                    parent_cat = collection_info.get("parent_category", "")
                    grandparent_dept = collection_info.get("grandparent_department", "")

                    if parent_cat:
                        parent_handle = category_handles.get(parent_cat.lower(), "")
                        if parent_handle:
                            hierarchy_metafields.append({
                                "namespace": "hierarchy",
                                "key": "parent_handle",
                                "value": parent_handle,
                                "type": "single_line_text_field"
                            })
                            log_and_status(status_fn, f"    Adding hierarchy: parent_handle={parent_handle}")

                    if grandparent_dept:
                        grandparent_handle = department_handles.get(grandparent_dept.lower(), "")
                        if grandparent_handle:
                            hierarchy_metafields.append({
                                "namespace": "hierarchy",
                                "key": "grandparent_handle",
                                "value": grandparent_handle,
                                "type": "single_line_text_field"
                            })
                            log_and_status(status_fn, f"    Adding hierarchy: grandparent_handle={grandparent_handle}")

                created_collection = create_collection(
                    collection_name, rules, cfg,
                    description=None,
                    metafields=hierarchy_metafields
                )

                if not created_collection:
                    error_msg = f"Failed to create collection: {collection_name}"
                    log_and_status(status_fn, f"    ❌ {error_msg}", "error")
                    collections_failed += 1
                    
                    # STOP IMMEDIATELY ON FAILURE
                    log_and_status(status_fn, "\n" + "=" * 80)
                    log_and_status(status_fn, "❌ COLLECTION CREATION FAILED - STOPPING", "error")
                    log_and_status(status_fn, "=" * 80)
                    log_and_status(status_fn, f"Failed collection: {collection_name}")
                    log_and_status(status_fn, "Fix the issue and rerun the script to continue.")
                    log_and_status(status_fn, "=" * 80 + "\n")
                    return False, collections_created, collections_existing, collections_failed
                
                log_and_status(
                    status_fn,
                    f"    ✅ Created collection: {created_collection['id']}",
                    ui_msg="    ✅ Collection created"
                )

                # Store handle for hierarchy lookups by child collections
                handle = created_collection.get('handle', '')
                if level == 'department' and handle:
                    department_handles[collection_name.lower()] = handle
                elif level == 'category' and handle:
                    category_handles[collection_name.lower()] = handle

                # Publish collection to sales channels
                log_and_status(status_fn, f"    Publishing to sales channels...")
                # Get sales channel IDs (already retrieved during processing)
                sales_channel_ids = get_sales_channel_ids(cfg)
                if sales_channel_ids:
                    if publish_collection_to_channels(created_collection['id'], sales_channel_ids, cfg):
                        log_and_status(
                            status_fn,
                            f"    ✅ Published to Online Store and Point of Sale",
                            ui_msg="    ✅ Published to channels"
                        )
                    else:
                        log_and_status(
                            status_fn,
                            f"    ⚠️  Failed to publish collection to sales channels",
                            "warning"
                        )

                # Add to tracking
                collections_data["collections"].append({
                    "name": collection_name,
                    "level": level,
                    "id": created_collection["id"],
                    "handle": created_collection["handle"],
                    "status": "created",
                    "created_at": datetime.now().isoformat()
                })
                save_collections(collections_data)

                collections_created += 1
                time.sleep(0.5)
        
        log_and_status(status_fn, "\n" + "=" * 80)
        log_and_status(status_fn, "COLLECTIONS SUMMARY")
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, f"✅ Created: {collections_created}")
        log_and_status(status_fn, f"✓ Already existed: {collections_existing}")
        if collections_failed > 0:
            log_and_status(status_fn, f"❌ Failed: {collections_failed}", "error")
        log_and_status(status_fn, f"Total processed: {collections_created + collections_existing + collections_failed}")
        log_and_status(status_fn, "=" * 80 + "\n")
        
        return True, collections_created, collections_existing, collections_failed
        
    except Exception as e:
        log_and_status(status_fn, f"❌ Error in collection creation: {e}", "error")
        logging.exception("Full traceback:")
        return False, 0, 0, 1




def ensure_metafield_definitions(products, cfg, status_fn):
    """
    Scan all products and variants for metafields and ensure their definitions exist in Shopify.
    Creates missing metafield definitions automatically.

    Args:
        products: List of product dictionaries
        cfg: Configuration dictionary
        status_fn: Status update function

    Returns:
        True on success, False on error
    """
    try:
        log_and_status(status_fn, "\n" + "=" * 80)
        log_and_status(status_fn, "CHECKING METAFIELD DEFINITIONS")
        log_and_status(status_fn, "=" * 80)

        # Key mappings (same as used during product creation)
        PRODUCT_METAFIELD_KEY_MAPPING = {
            'laying_patterns': 'layout_possibilities',
            'applications': 'applications',
            'documentation': 'documentation',
            'benefits': 'benefits',
            'features': 'features',
            'directions': 'directions',
            'nutritional_information': 'nutritional_information',
            'ingredients': 'ingredients',
            'specifications': 'specifications',
            'additional_documentation': 'additional_documentation',
            'whats_included': 'whats_included',
        }

        VARIANT_METAFIELD_KEY_MAPPING = {
            'model_number': 'model_number',
            'size_info': 'size_info',
            'color_swatch_image': 'color_swatch_image',
            'texture_swatch_image': 'texture_swatch_image',
            'finish_swatch_image': 'finish_swatch_image',
        }

        # Collect all unique metafield definitions needed
        product_metafields = {}  # {mapped_key: type}
        variant_metafields = {}  # {mapped_key: type}

        for product in products:
            # Product metafields
            for mf in product.get('metafields', []):
                input_key = mf.get('key')
                mf_type = mf.get('type')
                namespace = mf.get('namespace', 'custom')
                if namespace == 'custom' and input_key and mf_type:
                    # Apply key mapping
                    shopify_key = PRODUCT_METAFIELD_KEY_MAPPING.get(input_key, input_key)
                    product_metafields[shopify_key] = mf_type

            # Variant metafields
            for variant in product.get('variants', []):
                for mf in variant.get('metafields', []):
                    input_key = mf.get('key')
                    mf_type = mf.get('type')
                    namespace = mf.get('namespace', 'custom')
                    if namespace == 'custom' and input_key and mf_type:
                        # Apply key mapping
                        shopify_key = VARIANT_METAFIELD_KEY_MAPPING.get(input_key, input_key)
                        variant_metafields[shopify_key] = mf_type

        total_definitions = len(product_metafields) + len(variant_metafields)
        log_and_status(
            status_fn,
            f"Found {len(product_metafields)} product metafield types, {len(variant_metafields)} variant metafield types",
            ui_msg=f"Found {total_definitions} metafield types to check"
        )
        log_and_status(
            status_fn,
            f"Total: {total_definitions} metafield definitions to verify/create\n",
            ui_msg="Verifying metafield definitions..."
        )

        if total_definitions == 0:
            log_and_status(
                status_fn,
                "No metafields found - skipping definition check",
                ui_msg="No metafields to check"
            )
            log_and_status(status_fn, "=" * 80 + "\n")
            return True

        # Create product metafield definitions
        if product_metafields:
            log_and_status(
                status_fn,
                f"Checking {len(product_metafields)} product metafield definitions:",
                ui_msg=f"Checking {len(product_metafields)} product metafields..."
            )
            for key, mf_type in product_metafields.items():
                label = key_to_label(key)
                log_and_status(
                    status_fn,
                    f"  • {key} ({label}) - type: {mf_type}",
                    ui_msg=f"  Checking: {label}"
                )
                create_metafield_definition('custom', key, mf_type, 'PRODUCT', cfg, pin=True, status_fn=status_fn)
                time.sleep(0.3)  # Small delay to avoid rate limits

        # Create variant metafield definitions
        if variant_metafields:
            log_and_status(
                status_fn,
                f"\nChecking {len(variant_metafields)} variant metafield definitions:",
                ui_msg=f"Checking {len(variant_metafields)} variant metafields..."
            )
            for key, mf_type in variant_metafields.items():
                label = key_to_label(key)
                log_and_status(
                    status_fn,
                    f"  • {key} ({label}) - type: {mf_type}",
                    ui_msg=f"  Checking: {label}"
                )
                create_metafield_definition('custom', key, mf_type, 'PRODUCTVARIANT', cfg, pin=True, status_fn=status_fn)
                time.sleep(0.3)  # Small delay to avoid rate limits

        log_and_status(
            status_fn,
            "\n✅ Metafield definition check complete",
            ui_msg="✅ All metafield definitions verified"
        )
        log_and_status(status_fn, "=" * 80 + "\n")

        return True

    except Exception as e:
        log_and_status(status_fn, f"❌ Error checking metafield definitions: {e}", "error")
        logging.exception("Full traceback:")
        return False




def process_products(cfg, status_fn, execution_mode="resume", start_record=None, end_record=None):
    """
    Process products from input file with granular restore points.
    Stops immediately on any failure (product, variant, or collection).

    Args:
        cfg: Configuration dictionary
        status_fn: Status update function
        execution_mode: "resume" to continue from last run, "overwrite" to delete and recreate existing products
        start_record: 1-based index of first record to process (None = start from beginning)
        end_record: 1-based index of last record to process (None = process to end)
    """
    try:
        input_file = cfg.get("INPUT_FILE", "").strip()
        product_output_file = cfg.get("PRODUCT_OUTPUT_FILE", "").strip()
        collections_output_file = cfg.get("COLLECTIONS_OUTPUT_FILE", "").strip()
        
        setup_logging(cfg.get("LOG_FILE", ""))
        
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, f"Shopify Product Uploader - {SCRIPT_VERSION}")
        log_and_status(status_fn, f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_and_status(status_fn, "=" * 80)
        
        # Load input file
        log_and_status(status_fn, f"Loading input file: {input_file}")
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            log_and_status(status_fn, f"❌ Input file not found: {input_file}", "error")
            return
        except json.JSONDecodeError as e:
            log_and_status(status_fn, f"❌ Invalid JSON in input file: {e}", "error")
            return
        except Exception as e:
            log_and_status(status_fn, f"❌ Error loading input file: {e}", "error")
            return
        
        # Handle both formats: {"products": [...]} or just [...]
        if isinstance(data, list):
            products = data
        else:
            products = data.get('products', [])

        if not products:
            log_and_status(status_fn, "❌ No products found in input file.", "error")
            return

        total_in_file = len(products)
        log_and_status(status_fn, f"✅ Loaded {total_in_file} products from file")

        # Apply start/end record filtering if specified
        start_idx = 0
        end_idx = None

        if start_record is not None and start_record > 0:
            start_idx = start_record - 1  # Convert 1-based to 0-based index

        if end_record is not None and end_record > 0:
            end_idx = end_record  # Keep as-is for slicing (end is exclusive in Python)

        # Slice the products list
        products = products[start_idx:end_idx]

        if not products:
            log_and_status(status_fn, f"❌ No products in specified range (records {start_record or 1} to {end_record or total_in_file})", "error")
            return

        # Log filtering info
        if start_record or end_record:
            actual_start = (start_record or 1)
            actual_end = min(end_record, total_in_file) if end_record else total_in_file
            log_and_status(
                status_fn,
                f"📋 Processing records {actual_start} to {actual_end} ({len(products)} products)",
                ui_msg=f"Processing records {actual_start}-{actual_end}"
            )

        log_and_status(status_fn, "")

        # ========== PRE-UPLOAD VALIDATION ==========
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, "PRE-UPLOAD VALIDATION")
        log_and_status(status_fn, "=" * 80)
        log_and_status(
            status_fn,
            "Validating image URLs...",
            ui_msg="Checking for non-Shopify CDN URLs..."
        )

        is_valid, invalid_urls = validate_image_urls(products)

        if not is_valid:
            log_and_status(
                status_fn,
                f"\n⚠️  WARNING: Found {len(invalid_urls)} non-Shopify CDN URL(s)",
                "warning"
            )
            log_and_status(status_fn, "\nBest practice: Use Shopify CDN URLs for images and metafields.")
            log_and_status(status_fn, "External URLs may work but could have limitations or performance issues.")
            log_and_status(status_fn, "\nNon-Shopify CDN URLs found:")
            log_and_status(status_fn, "-" * 80)

            # Group by product for better readability
            current_product = None
            shown_count = 0
            max_to_show = 10
            for item in invalid_urls:
                if shown_count >= max_to_show:
                    break
                if item['product_title'] != current_product:
                    current_product = item['product_title']
                    log_and_status(status_fn, f"\nProduct: {current_product}")
                log_and_status(status_fn, f"  • {item['location']}")
                log_and_status(status_fn, f"    URL: {item['url'][:80]}...")
                shown_count += 1

            if len(invalid_urls) > max_to_show:
                log_and_status(status_fn, f"\n... and {len(invalid_urls) - max_to_show} more")

            log_and_status(status_fn, "\n" + "=" * 80)
            log_and_status(status_fn, "RECOMMENDATION (optional):", "warning")
            log_and_status(status_fn, "=" * 80)
            log_and_status(status_fn, "For best performance and reliability:")
            log_and_status(status_fn, "1. Upload images to Shopify first (Admin → Content → Files)")
            log_and_status(status_fn, "2. Update your input JSON with the Shopify CDN URLs")
            log_and_status(status_fn, "3. Shopify CDN URLs should look like:")
            log_and_status(status_fn, "   https://cdn.shopify.com/s/files/1/xxxx/xxxx/xxxx/filename.jpg")
            log_and_status(status_fn, "   OR")
            log_and_status(status_fn, "   https://cdn.shopify.com/shopifycloud/...")
            log_and_status(status_fn, "\n⚠️  This is a WARNING - upload will continue.")
            log_and_status(status_fn, "Shopify may automatically fetch and cache external images.")
            log_and_status(status_fn, "=" * 80 + "\n")
        else:
            log_and_status(
                status_fn,
                f"✅ All image URLs validated successfully",
                ui_msg="✅ All URLs are valid Shopify CDN URLs"
            )
            log_and_status(status_fn, "=" * 80 + "\n")

        # ========== IMAGE ALT TAG VALIDATION (Warning Only) ==========
        log_and_status(
            status_fn,
            "Checking image alt tags for variant filtering support...",
            ui_msg="Checking image alt tags..."
        )

        has_warnings, alt_tag_warnings = validate_image_alt_tags_for_filtering(products)

        if has_warnings:
            log_and_status(
                status_fn,
                f"\n⚠️  WARNING: Found {len(alt_tag_warnings)} image(s) without filter hashtags",
                "warning"
            )
            log_and_status(status_fn, "\nMany Shopify themes filter product images by variant options using")
            log_and_status(status_fn, "hashtags in image alt text (e.g., #COLOR#FINISH#SIZE).")
            log_and_status(status_fn, "\nImages without filter hashtags:")
            log_and_status(status_fn, "-" * 80)

            # Show first 10 warnings
            for warning in alt_tag_warnings[:10]:
                log_and_status(status_fn, f"\nProduct: {warning['product_title']}")
                log_and_status(status_fn, f"  Image #{warning['image_index']}")
                log_and_status(status_fn, f"  Current alt: \"{warning['current_alt']}\"")
                log_and_status(status_fn, f"  {warning['suggestion']}")

            if len(alt_tag_warnings) > 10:
                log_and_status(status_fn, f"\n... and {len(alt_tag_warnings) - 10} more images")

            log_and_status(status_fn, "\n" + "=" * 80)
            log_and_status(status_fn, "HOW TO FIX (if your theme uses alt tag filtering):", "warning")
            log_and_status(status_fn, "=" * 80)
            log_and_status(status_fn, "1. For each image, determine which variant options it represents")
            log_and_status(status_fn, "2. Append filter hashtags to the alt text:")
            log_and_status(status_fn, "   Example: \"Product description #OPTION1_VALUE#OPTION2_VALUE#OPTION3_VALUE\"")
            log_and_status(status_fn, "3. Format rules:")
            log_and_status(status_fn, "   - Use UPPERCASE for values")
            log_and_status(status_fn, "   - Replace spaces and special characters with underscores")
            log_and_status(status_fn, "   - Example: \"20 X 10 & 20 X 20\" becomes \"#20_X_10___20_X_20\"")
            log_and_status(status_fn, "\nExample full alt tag:")
            log_and_status(status_fn, "  \"Aberdeen Slabs in outdoor setting #ROCK_GARDEN_BROWN#KLEAN_BLOC_SLATE#20_X_10___20_X_20\"")
            log_and_status(status_fn, "\n⚠️  This is a WARNING - upload will continue.")
            log_and_status(status_fn, "If your theme doesn't use alt tag filtering, you can ignore this.")
            log_and_status(status_fn, "=" * 80 + "\n")
        else:
            log_and_status(
                status_fn,
                "✅ All images have filter hashtags in alt tags (or theme doesn't use filtering)",
                ui_msg="✅ Image alt tags validated"
            )

        # Get sales channel IDs (cached after first retrieval)
        log_and_status(status_fn, "Retrieving sales channel IDs...")
        sales_channel_ids = get_sales_channel_ids(cfg)
        
        if not sales_channel_ids:
            log_and_status(status_fn, "❌ Failed to retrieve sales channel IDs.", "error")
            return
        
        log_and_status(status_fn, f"✅ Sales channel IDs retrieved")
        log_and_status(status_fn, f"  - Online Store: {sales_channel_ids.get('online_store', 'Not found')}")
        log_and_status(status_fn, f"  - Point of Sale: {sales_channel_ids.get('point_of_sale', 'Not found')}\n")

        # Get inventory quantity setting and location ID if needed
        inventory_quantity = None
        location_id = None
        try:
            inv_qty_str = cfg.get("INVENTORY_QUANTITY", "").strip()
            if inv_qty_str:
                inventory_quantity = int(inv_qty_str)
                if inventory_quantity > 0:
                    log_and_status(status_fn, f"Inventory quantity configured: {inventory_quantity}")
                    log_and_status(status_fn, "Retrieving default location ID...")
                    location_id = get_default_location_id(cfg, status_fn)
                    if location_id:
                        log_and_status(status_fn, f"✅ Location ID: {location_id}\n")
                    else:
                        log_and_status(status_fn, "⚠️  Could not retrieve location ID. Inventory quantities will not be set.", "warning")
                        inventory_quantity = None
                else:
                    inventory_quantity = None
        except (ValueError, TypeError):
            inventory_quantity = None

        # Process collections first
        success, created, existing, failed = process_collections(products, cfg, status_fn)
        if not success:
            return  # Stop if collection creation failed

        # Update navigation menu to include menu items for product taxonomy paths
        log_and_status(status_fn, "\n" + "=" * 80)
        log_and_status(status_fn, "UPDATING NAVIGATION MENU")
        log_and_status(status_fn, "=" * 80 + "\n")

        collections_data = load_collections()
        menu_updates_success = 0
        menu_updates_failed = 0

        for product in products:
            product_title = product.get('title', 'Unknown Product').strip()
            try:
                menu_success = ensure_menu_items_for_product(product, collections_data, cfg, status_fn)
                if menu_success:
                    menu_updates_success += 1
                else:
                    menu_updates_failed += 1
                    log_and_status(status_fn, f"⚠️  Menu update incomplete for: {product_title}", "warning")
            except Exception as e:
                menu_updates_failed += 1
                log_and_status(status_fn, f"⚠️  Menu update error for {product_title}: {str(e)}", "warning")

        if menu_updates_failed == 0:
            log_and_status(status_fn, f"✅ Navigation menu updated for all {menu_updates_success} products\n")
        else:
            log_and_status(status_fn, f"⚠️  Menu updates: {menu_updates_success} successful, {menu_updates_failed} with issues\n", "warning")

        # Ensure metafield definitions exist (auto-create if missing)
        success = ensure_metafield_definitions(products, cfg, status_fn)
        if not success:
            log_and_status(status_fn, "⚠️  Warning: Some metafield definitions may not exist", "warning")
            log_and_status(status_fn, "Continuing with product upload...\n")

        # Get API credentials
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()
        
        if not store_url or not access_token:
            log_and_status(status_fn, "❌ Shopify credentials not configured.", "error")
            return
        
        store_url = store_url.replace("https://", "").replace("http://", "")
        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }
        
        # Load taxonomy cache
        log_and_status(status_fn, "Loading taxonomy cache...")
        taxonomy_cache = load_taxonomy_cache()
        log_and_status(status_fn, f"✅ Loaded {len(taxonomy_cache)} cached taxonomy mappings\n")
        
        # Load restore points
        products_restore = load_products()
        
        # Initialize results for current run
        results = []
        processed_titles = set()
        
        def add_result(result_dict):
            """Add result avoiding duplicates."""
            title = result_dict.get("title", "").strip().lower()
            if title and title not in processed_titles:
                results.append(result_dict)
                processed_titles.add(title)
        
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, "PROCESSING PRODUCTS")
        log_and_status(status_fn, "=" * 80)
        log_and_status(
            status_fn,
            f"Execution Mode: {execution_mode.upper()}",
            ui_msg=f"Mode: {'Resume from last run' if execution_mode == 'resume' else 'Overwrite & Continue'}"
        )
        log_and_status(status_fn, "=" * 80)

        total_products = len(products)
        successful = 0
        failed = 0
        skipped = 0
        
        for idx, product in enumerate(products):
            try:
                product_title = product.get('title', 'Unknown Product').strip()
                product_num = idx + 1
                
                log_and_status(
                    status_fn,
                    f"\n[{product_num}/{total_products}] Processing: {product_title}",
                    ui_msg=f"[{product_num}/{total_products}] {product_title[:50]}..."
                )
                
                # Check restore point
                restore_key = product_title.lower()
                existing_restore = products_restore.get("products_dict", {}).get(restore_key)
                
                if existing_restore:
                    shopify_id = existing_restore.get("shopify_id")
                    product_created = existing_restore.get("product_created", False)
                    variants_created = existing_restore.get("variants_created", False)

                    if product_created and variants_created:
                        if existing_restore.get("status") == "completed":
                            # In resume mode, skip completed products
                            # In overwrite mode, delete and recreate them
                            if execution_mode == "resume":
                                log_and_status(
                                    status_fn,
                                    f"  ✓ Product already completed successfully. Skipping.",
                                    ui_msg="  ✓ Already completed - skipping"
                                )
                                skipped += 1

                                add_result({
                                    "title": product_title,
                                    "shopify_id": shopify_id,
                                    "status": "skipped",
                                    "reason": "already_completed"
                                })

                                continue
                            else:  # overwrite mode
                                log_and_status(
                                    status_fn,
                                    f"  ⚠️  Product already completed. Overwrite mode: deleting and recreating.",
                                    ui_msg="  ⚠️  Overwriting existing product"
                                )
                                log_and_status(
                                    status_fn,
                                    f"  Deleting product: {shopify_id}",
                                    ui_msg="  Deleting existing product..."
                                )

                                if not delete_shopify_product(shopify_id, cfg):
                                    error_msg = "Failed to delete existing product"
                                    log_and_status(status_fn, f"  ❌ {error_msg}", "error")

                                    # Save restore point with error
                                    result_dict = {
                                        "title": product_title,
                                        "status": "failed",
                                        "error": error_msg,
                                        "failed_stage": "product_deletion"
                                    }
                                    add_result(result_dict)
                                    products_restore = update_product_in_restore(products_restore, result_dict)
                                    save_products(products_restore)

                                    # STOP IMMEDIATELY
                                    log_and_status(status_fn, "\n" + "=" * 80)
                                    log_and_status(status_fn, "❌ PRODUCT DELETION FAILED - STOPPING", "error")
                                    log_and_status(status_fn, "=" * 80)
                                    return

                                log_and_status(status_fn, "  ✅ Deleted existing product")
                                time.sleep(0.5)
                        else:
                            log_and_status(
                                status_fn,
                                f"  Found incomplete restore point for: {product_title}",
                                ui_msg="  Restarting from failure point"
                            )
                            log_and_status(status_fn, f"  Previous status: {existing_restore.get('status')}")
                            log_and_status(
                                status_fn,
                                f"  Will delete and recreate product: {shopify_id}",
                                ui_msg="  Deleting for recreation..."
                            )

                            if not delete_shopify_product(shopify_id, cfg):
                                error_msg = "Failed to delete existing product for recreation"
                                log_and_status(status_fn, f"  ❌ {error_msg}", "error")

                                # Save restore point with error
                                result_dict = {
                                    "title": product_title,
                                    "status": "failed",
                                    "error": error_msg,
                                    "failed_stage": "product_deletion"
                                }
                                add_result(result_dict)
                                products_restore = update_product_in_restore(products_restore, result_dict)
                                save_products(products_restore)

                                # STOP IMMEDIATELY
                                log_and_status(status_fn, "\n" + "=" * 80)
                                log_and_status(status_fn, "❌ PRODUCT DELETION FAILED - STOPPING", "error")
                                log_and_status(status_fn, "=" * 80)
                                return

                            log_and_status(status_fn, "  ✅ Deleted existing product")
                            time.sleep(0.5)

                    elif product_created and not variants_created:
                        # Product was created but variants failed - delete and recreate
                        log_and_status(
                            status_fn,
                            f"  ⚠️  Product created but variants failed. Deleting to retry.",
                            ui_msg="  ⚠️  Retrying failed variant creation"
                        )
                        log_and_status(status_fn, f"  Previous error: {existing_restore.get('error', 'Unknown')}")
                        log_and_status(
                            status_fn,
                            f"  Deleting product: {shopify_id}",
                            ui_msg="  Deleting for recreation..."
                        )

                        if not delete_shopify_product(shopify_id, cfg):
                            error_msg = "Failed to delete product with failed variants"
                            log_and_status(status_fn, f"  ❌ {error_msg}", "error")

                            # Save restore point with error
                            result_dict = {
                                "title": product_title,
                                "status": "failed",
                                "error": error_msg,
                                "failed_stage": "product_deletion"
                            }
                            add_result(result_dict)
                            products_restore = update_product_in_restore(products_restore, result_dict)
                            save_products(products_restore)

                            # STOP IMMEDIATELY
                            log_and_status(status_fn, "\n" + "=" * 80)
                            log_and_status(status_fn, "❌ PRODUCT DELETION FAILED - STOPPING", "error")
                            log_and_status(status_fn, "=" * 80)
                            return

                        log_and_status(status_fn, "  ✅ Deleted existing product")
                        time.sleep(0.5)

                # Create or recreate product
                log_and_status(status_fn, "  Creating product in Shopify...")
                
                # Prepare metafields
                product_metafields = list(product.get('metafields', []))
                
                # Extract category/subcategory for collections (from tags)
                category, subcategory = extract_category_subcategory(product)

                # Get Shopify product category
                # Look up from shopify_category_id field (if provided by categorizer)
                # Otherwise, try product_category field for lookup
                taxonomy_id = product.get('shopify_category_id')
                product_category_field = product.get('product_category', '').strip()

                if taxonomy_id:
                    log_and_status(status_fn, f"  Using provided Shopify category ID: {taxonomy_id}")
                elif product_category_field:
                    # Fallback: Try product_category field for taxonomy lookup
                    log_and_status(status_fn, f"  Looking up Shopify taxonomy for: {product_category_field}")
                    taxonomy_id, taxonomy_cache = get_taxonomy_id(product_category_field, taxonomy_cache, api_url, headers, status_fn)

                    if taxonomy_id:
                        log_and_status(status_fn, f"  ✅ Found taxonomy ID: {taxonomy_id}")
                    else:
                        log_and_status(status_fn, f"  ⚠️  No taxonomy match found for: {product_category_field}", "warning")
                else:
                    log_and_status(status_fn, "  No Shopify category available", "warning")
                
                # Prepare product input (API 2025-10 format)
                # Support both 'descriptionHtml' (new) and 'body_html' (legacy) field names
                description = product.get('descriptionHtml') or product.get('body_html', '')

                product_input = {
                    "title": product.get('title'),
                    "descriptionHtml": description,
                    "vendor": product.get('vendor', ''),
                    "productType": product.get('product_type', ''),
                    "status": "ACTIVE"
                }
                
                # Add category to product input (if taxonomy ID found)
                if taxonomy_id:
                    product_input["category"] = taxonomy_id
                
                # Add tags (split comma-separated string into array)
                tags = product.get('tags', [])
                if isinstance(tags, str):
                    # Split by comma and strip whitespace from each tag
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                elif isinstance(tags, list):
                    # Clean up list tags
                    tags = [str(t).strip() for t in tags if t and str(t).strip()]
                else:
                    tags = []

                if tags:
                    product_input["tags"] = tags
                
                # ✅ CRITICAL FIX: Add productOptions to define option structure
                # Extract unique option values from variants
                option_values_map = extract_unique_option_values(product)
                
                if option_values_map:
                    product_options = []
                    for option_name, value_set in option_values_map.items():
                        product_options.append({
                            "name": option_name,
                            "values": [{"name": value} for value in sorted(value_set)]
                        })
                    
                    product_input["productOptions"] = product_options
                    log_and_status(status_fn, f"  Adding productOptions: {json.dumps(product_options, indent=2)}")
                
                # Add metafields with key mapping
                # Map input file keys to Shopify metafield definition keys
                METAFIELD_KEY_MAPPING = {
                    # Input key -> Shopify key
                    'laying_patterns': 'layout_possibilities',
                    'applications': 'applications',
                    'documentation': 'documentation',
                    'benefits': 'benefits',
                    'features': 'features',
                    'directions': 'directions',
                    'nutritional_information': 'nutritional_information',
                    'ingredients': 'ingredients',
                    'specifications': 'specifications',
                    'additional_documentation': 'additional_documentation',
                    'whats_included': 'whats_included',
                }

                metafields_input = []

                # Add existing product metafields with key mapping
                if product_metafields:
                    for mf in product_metafields:
                        input_key = mf.get('key')
                        # Map the key if a mapping exists, otherwise use original
                        shopify_key = METAFIELD_KEY_MAPPING.get(input_key, input_key)

                        metafields_input.append({
                            "namespace": mf.get('namespace'),
                            "key": shopify_key,
                            "value": mf.get('value'),
                            "type": mf.get('type')
                        })

                        # Log if key was mapped
                        if input_key != shopify_key:
                            logging.debug(f"  Mapped metafield key: '{input_key}' -> '{shopify_key}'")
                
                # Attach metafields to product input
                if metafields_input:
                    product_input["metafields"] = metafields_input
                
                # Prepare media input
                media_input = []

                # Process 3D models from media array
                uploaded_models = []
                for media_item in product.get('media', []):
                    if media_item.get('media_content_type') == 'MODEL_3D':
                        log_and_status(status_fn, f"  Uploading 3D model sources for product...")

                        # Upload ALL sources (GLB for Android/web, USDZ for iOS AR)
                        sources = media_item.get('sources', [])
                        alt_text = media_item.get('alt', '')
                        position = media_item.get('position', 999)

                        # Prepare filename components
                        vendor = product.get('vendor', 'Unknown').strip().replace(' ', '_')
                        product_name = product_title.replace(' ', '_')

                        # Generate unique ID for this model (8-character hex)
                        import uuid
                        unique_id = uuid.uuid4().hex[:8]

                        for source in sources:
                            source_format = source.get('format', '').lower()
                            model_url = source.get('url')

                            if not model_url:
                                continue

                            # Create filename: vendor_product_name_unique_id.extension
                            filename = f"{vendor}_{product_name}_{unique_id}.{source_format}"

                            # Upload this source file (GLB or USDZ)
                            log_and_status(status_fn, f"    Uploading {source_format.upper()} file as: {filename}")
                            resource_url, _ = upload_model_to_shopify(model_url, filename, cfg, status_fn)

                            if resource_url:
                                # Model uploaded successfully - store resourceUrl from staged upload
                                uploaded_models.append({
                                    'cdn_url': resource_url,  # This is the resourceUrl for productCreateMedia
                                    'alt': alt_text,
                                    'position': position,
                                    'format': source_format
                                })
                                log_and_status(status_fn, f"    ✅ {source_format.upper()} file uploaded")
                            else:
                                log_and_status(status_fn, f"    ⚠️ Failed to upload {source_format.upper()} (no resourceUrl returned)", "warning")

                # Add images to media input
                images = product.get('images', [])

                if images:
                    log_and_status(
                        status_fn,
                        f"  📊 Images: {len(images)}",
                        ui_msg=f"  📊 {len(images)} images"
                    )

                    # Sort images by position to ensure correct ordering
                    sorted_images = sorted(images, key=lambda x: x.get('position', 999))

                    # For Aggregates and Pavers and Hardscaping products,
                    # use first lifestyle image as featured image (collection thumbnail)
                    product_tags = product.get('tags', [])
                    uses_lifestyle_featured = any(
                        tag in product_tags for tag in ['Aggregates', 'Pavers and Hardscaping']
                    )

                    if uses_lifestyle_featured:
                        # Find all lifestyle/hero image indices
                        lifestyle_indices = []
                        for idx, img in enumerate(sorted_images):
                            alt_text = img.get('alt', '').lower()
                            if 'lifestyle' in alt_text or 'hero' in alt_text:
                                lifestyle_indices.append(idx)
                                if len(lifestyle_indices) >= 2:
                                    break  # Only need first two

                        if lifestyle_indices:
                            # Extract lifestyle/hero images (in reverse order to preserve indices)
                            lifestyle_images = []
                            for idx in sorted(lifestyle_indices, reverse=True):
                                lifestyle_images.insert(0, sorted_images.pop(idx))

                            # Insert at beginning: first lifestyle as featured, second as hover
                            for i, img in enumerate(reversed(lifestyle_images)):
                                sorted_images.insert(0, img)

                            if len(lifestyle_images) >= 2:
                                log_and_status(
                                    status_fn,
                                    f"  📷 Using lifestyle/hero images for featured and hover"
                                )
                            else:
                                log_and_status(
                                    status_fn,
                                    f"  📷 Using lifestyle/hero image as featured (collection thumbnail)"
                                )
                            logging.debug(f"  Moved {len(lifestyle_images)} lifestyle/hero image(s) to front")

                    # Log sorted image order for debugging
                    logging.debug(f"  Sorted images for '{product_title}':")
                    for i, img in enumerate(sorted_images):
                        img_src = img.get('src', '')
                        img_alt = img.get('alt', '')
                        img_pos = img.get('position', 'N/A')
                        # Extract filename from URL for clearer logging
                        filename = img_src.split('/')[-1].split('?')[0] if img_src else 'N/A'
                        logging.debug(f"    [{i+1}] pos={img_pos}, file={filename}, alt={img_alt[:50]}...")
                else:
                    sorted_images = []

                for img in sorted_images:
                    media_input.append({
                        "originalSource": img.get('src'),
                        "alt": img.get('alt', ''),
                        "mediaContentType": "IMAGE"
                    })

                # Note: 3D models will be attached to the product after creation
                # using productCreateMedia mutation (they can't be added during productCreate)
                
                # Create product mutation (API 2025-10)
                # Returns media details to verify correct image association
                create_product_mutation = """
                mutation productCreate($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
                  productCreate(product: $product, media: $media) {
                    product {
                      id
                      title
                      handle
                      media(first: 250) {
                        edges {
                          node {
                            ... on MediaImage {
                              id
                              alt
                              image {
                                url
                                originalSrc
                              }
                            }
                          }
                        }
                      }
                    }
                    userErrors {
                      field
                      message
                    }
                  }
                }
                """
                
                variables = {
                    "product": product_input,
                    "media": media_input if media_input else None
                }

                log_and_status(status_fn, f"  Creating product with title: {product_input['title']}")
                logging.debug(f"Product input: {json.dumps(product_input, indent=2)}")

                # Log media input for debugging image association issues
                if media_input:
                    logging.debug(f"Media input ({len(media_input)} items):")
                    for i, m in enumerate(media_input):
                        src = m.get('originalSource', '')
                        alt = m.get('alt', '')
                        filename = src.split('/')[-1].split('?')[0] if src else 'N/A'
                        logging.debug(f"  [{i+1}] file={filename}, alt={alt[:60] if alt else 'N/A'}...")

                # Make API request
                try:
                    response = requests.post(
                        api_url,
                        json={"query": create_product_mutation, "variables": variables},
                        headers=headers,
                        timeout=60
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Check for GraphQL errors
                    if "errors" in result:
                        error_msg = f"GraphQL errors: {result['errors']}"
                        logging.error(error_msg)
                        log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                        
                        # Save restore point with error
                        result_dict = {
                            "title": product_title,
                            "status": "failed",
                            "error": error_msg,
                            "failed_stage": "product_creation",
                            "product_created": False
                        }
                        add_result(result_dict)
                        products_restore = update_product_in_restore(products_restore, result_dict)
                        save_products(products_restore)
                        
                        # STOP IMMEDIATELY
                        log_and_status(status_fn, "\n" + "=" * 80)
                        log_and_status(status_fn, "❌ PRODUCT CREATION FAILED - STOPPING", "error")
                        log_and_status(status_fn, "=" * 80)
                        return
                    
                    # Check for user errors
                    user_errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
                    if user_errors:
                        error_msg = "; ".join([f"{err.get('field')}: {err.get('message')}" for err in user_errors])
                        logging.error(f"Product creation user errors: {error_msg}")
                        log_and_status(status_fn, f"  ❌ Product creation errors: {error_msg}", "error")
                        
                        # Save restore point with error
                        result_dict = {
                            "title": product_title,
                            "status": "failed",
                            "error": error_msg,
                            "failed_stage": "product_creation",
                            "product_created": False
                        }
                        add_result(result_dict)
                        products_restore = update_product_in_restore(products_restore, result_dict)
                        save_products(products_restore)
                        
                        # STOP IMMEDIATELY
                        log_and_status(status_fn, "\n" + "=" * 80)
                        log_and_status(status_fn, "❌ PRODUCT CREATION FAILED - STOPPING", "error")
                        log_and_status(status_fn, "=" * 80)
                        return
                    
                    # Extract product data
                    created_product = result.get("data", {}).get("productCreate", {}).get("product", {})
                    shopify_product_id = created_product.get("id")
                    product_handle = created_product.get("handle")
                    
                    if not shopify_product_id:
                        error_msg = "No product ID returned from API"
                        logging.error(error_msg)
                        log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                        
                        # Save restore point with error
                        result_dict = {
                            "title": product_title,
                            "status": "failed",
                            "error": error_msg,
                            "failed_stage": "product_creation",
                            "product_created": False
                        }
                        add_result(result_dict)
                        products_restore = update_product_in_restore(products_restore, result_dict)
                        save_products(products_restore)
                        
                        # STOP IMMEDIATELY
                        log_and_status(status_fn, "\n" + "=" * 80)
                        log_and_status(status_fn, "❌ PRODUCT CREATION FAILED - STOPPING", "error")
                        log_and_status(status_fn, "=" * 80)
                        return
                    
                    log_and_status(
                        status_fn,
                        f"  ✅ Product created successfully: {shopify_product_id}",
                        ui_msg="  ✅ Product created"
                    )

                    # Verify media was created correctly
                    created_media = created_product.get("media", {}).get("edges", [])
                    if created_media and media_input:
                        logging.debug(f"  Media verification for '{product_title}':")
                        logging.debug(f"    Sent {len(media_input)} images, received {len(created_media)} media items")

                        # Compare sent URLs with received URLs
                        sent_urls = [m.get('originalSource', '') for m in media_input]
                        received_media_info = []

                        for i, edge in enumerate(created_media):
                            node = edge.get("node") or {}
                            image_data = node.get("image") or {}
                            media_id = node.get("id", "N/A")
                            media_alt = node.get("alt") or ""
                            original_src = image_data.get("originalSrc") or ""

                            # Extract filename for comparison
                            received_filename = original_src.split('/')[-1].split('?')[0] if original_src else 'N/A'
                            received_media_info.append({
                                'position': i + 1,
                                'id': media_id,
                                'filename': received_filename,
                                'alt': media_alt
                            })
                            logging.debug(f"    Received [{i+1}]: id={media_id}, file={received_filename}, alt={media_alt[:50] if media_alt else 'N/A'}...")

                        # Check for URL mismatches (warning only, don't fail)
                        if len(media_input) != len(created_media):
                            log_and_status(
                                status_fn,
                                f"  ⚠️ Media count mismatch: sent {len(media_input)}, received {len(created_media)}",
                                "warning"
                            )

                    # Attach 3D models to product if any were uploaded
                    if uploaded_models:
                        log_and_status(status_fn, f"  Attaching {len(uploaded_models)} 3D model(s) to product...")

                        # Build media array with resourceUrls from staged uploads
                        media_inputs = []
                        for model in uploaded_models:
                            media_inputs.append({
                                "originalSource": model['cdn_url'],  # This is the resourceUrl from staged upload
                                "alt": model['alt'],
                                "mediaContentType": "MODEL_3D"
                            })

                        # Use productCreateMedia to attach 3D models
                        attach_model_mutation = """
                        mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
                          productCreateMedia(media: $media, productId: $productId) {
                            media {
                              ... on Model3d {
                                id
                                alt
                              }
                            }
                            mediaUserErrors {
                              field
                              message
                            }
                            userErrors {
                              field
                              message
                            }
                          }
                        }
                        """

                        attach_variables = {
                            "productId": shopify_product_id,
                            "media": media_inputs
                        }

                        try:
                            attach_response = requests.post(
                                api_url,
                                json={"query": attach_model_mutation, "variables": attach_variables},
                                headers=headers,
                                timeout=60
                            )
                            attach_response.raise_for_status()
                            attach_result = attach_response.json()

                            logging.debug(f"productCreateMedia response: {json.dumps(attach_result, indent=2)}")

                            # Check for errors
                            mutation_data = attach_result.get("data", {}).get("productCreateMedia", {})
                            user_errors = mutation_data.get("userErrors", [])
                            media_user_errors = mutation_data.get("mediaUserErrors", [])

                            if "errors" in attach_result or user_errors or media_user_errors:
                                all_errors = attach_result.get("errors", []) + user_errors + media_user_errors
                                log_and_status(status_fn, f"  ⚠️ Failed to attach models: {all_errors}", "warning")
                            else:
                                log_and_status(status_fn, f"  ✅ Attached {len(uploaded_models)} 3D model(s) to product")
                        except Exception as e:
                            log_and_status(status_fn, f"  ⚠️ Error attaching models: {e}", "warning")
                            logging.exception("Full traceback:")

                    # Save restore point after product creation
                    restore_data = {
                        "title": product_title,
                        "status": "in_progress",
                        "shopify_id": shopify_product_id,
                        "handle": product_handle,
                        "product_created": True,
                        "variants_created": False,
                        "published": False,
                        "category": category,
                        "subcategory": subcategory,
                        "product_category": product_category_field,
                        "taxonomy_id": taxonomy_id
                    }
                    products_restore = update_product_in_restore(products_restore, restore_data)
                    save_products(products_restore)
                    
                    # Publish product to sales channels if available
                    if sales_channel_ids:
                        log_and_status(status_fn, "  Publishing to sales channels...")
                        
                        if publish_product_to_channels(shopify_product_id, sales_channel_ids, cfg):
                            log_and_status(
                                status_fn,
                                "  ✅ Published to Online Store and Point of Sale",
                                ui_msg="  ✅ Published to sales channels"
                            )
                            
                            # Update restore point with publishing status
                            restore_data["published"] = True
                            products_restore = update_product_in_restore(products_restore, restore_data)
                            save_products(products_restore)
                        else:
                            log_and_status(
                                status_fn,
                                "  ⚠️  Failed to publish to sales channels",
                                "warning"
                            )
                            # Continue processing - publishing failure is not fatal
                    
                except requests.exceptions.Timeout:
                    error_msg = "Request timeout creating product"
                    logging.error(error_msg)
                    log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                    
                    # Save restore point with error
                    result_dict = {
                        "title": product_title,
                        "status": "failed",
                        "error": error_msg,
                        "failed_stage": "product_creation",
                        "product_created": False
                    }
                    add_result(result_dict)
                    products_restore = update_product_in_restore(products_restore, result_dict)
                    save_products(products_restore)
                    
                    # STOP IMMEDIATELY
                    log_and_status(status_fn, "\n" + "=" * 80)
                    log_and_status(status_fn, "❌ PRODUCT CREATION FAILED - STOPPING", "error")
                    log_and_status(status_fn, "=" * 80)
                    return
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"Request failed creating product: {e}"
                    logging.error(error_msg)
                    log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                    
                    # Save restore point with error
                    result_dict = {
                        "title": product_title,
                        "status": "failed",
                        "error": str(e),
                        "failed_stage": "product_creation",
                        "product_created": False
                    }
                    add_result(result_dict)
                    products_restore = update_product_in_restore(products_restore, result_dict)
                    save_products(products_restore)
                    
                    # STOP IMMEDIATELY
                    log_and_status(status_fn, "\n" + "=" * 80)
                    log_and_status(status_fn, "❌ PRODUCT CREATION FAILED - STOPPING", "error")
                    log_and_status(status_fn, "=" * 80)
                    return
                
                # Create variants
                variants = product.get('variants', [])
                variant_results = []

                if not variants:
                    log_and_status(
                        status_fn,
                        "  ⚠️  No variants found in product data",
                        "warning"
                    )
                    # Mark product as failed if no variants
                    result_dict = {
                        "title": product_title,
                        "shopify_id": shopify_product_id,
                        "status": "failed",
                        "error": "No variants in product data",
                        "failed_stage": "variant_validation",
                        "product_created": True,
                        "variants_created": False
                    }
                    add_result(result_dict)
                    products_restore = update_product_in_restore(products_restore, result_dict)
                    save_products(products_restore)

                    log_and_status(status_fn, "\n" + "=" * 80)
                    log_and_status(status_fn, "❌ NO VARIANTS - STOPPING", "error")
                    log_and_status(status_fn, "=" * 80)
                    return

                if variants:
                    log_and_status(
                        status_fn,
                        f"  Creating {len(variants)} variants...",
                        ui_msg=f"  Creating variants..."
                    )
                    
                    variant_inputs = []
                    option_names = [opt.get('name') for opt in product.get('options', []) if isinstance(opt, dict)]
                    
                    for var_idx, variant in enumerate(variants):
                        try:
                            variant_input = {
                                "price": str(variant.get('price', '0')),
                                "barcode": variant.get('barcode', ''),
                                "inventoryPolicy": "DENY",
                                "taxable": variant.get('taxable', True),
                            }
                            
                            # Set SKU, inventory tracking, requiresShipping, and weight via inventoryItem (API 2025-10 structure)
                            sku_value = variant.get('sku', '')
                            inventory_item = {
                                "tracked": True,
                                "requiresShipping": True  # ✅ All products require shipping
                            }

                            if sku_value:
                                inventory_item["sku"] = sku_value

                            # Handle weight via inventoryItem.measurement.weight (API 2025-10 structure)
                            if 'weight' in variant and variant['weight']:
                                try:
                                    weight_value = float(variant['weight'])
                                    # Map weight_unit to Shopify WeightUnit enum (POUNDS, OUNCES, KILOGRAMS, GRAMS)
                                    weight_unit_map = {
                                        'lb': 'POUNDS',
                                        'lbs': 'POUNDS',
                                        'LB': 'POUNDS',
                                        'pound': 'POUNDS',
                                        'pounds': 'POUNDS',
                                        'oz': 'OUNCES',
                                        'ounce': 'OUNCES',
                                        'ounces': 'OUNCES',
                                        'kg': 'KILOGRAMS',
                                        'kilogram': 'KILOGRAMS',
                                        'kilograms': 'KILOGRAMS',
                                        'g': 'GRAMS',
                                        'gram': 'GRAMS',
                                        'grams': 'GRAMS',
                                    }
                                    input_unit = variant.get('weight_unit', 'lb')
                                    weight_unit = weight_unit_map.get(input_unit, 'POUNDS')

                                    inventory_item["measurement"] = {
                                        "weight": {
                                            "value": weight_value,
                                            "unit": weight_unit
                                        }
                                    }
                                except (ValueError, TypeError):
                                    pass

                            variant_input["inventoryItem"] = inventory_item

                            if 'compare_at_price' in variant and variant['compare_at_price']:
                                variant_input["compareAtPrice"] = str(variant['compare_at_price'])
                            
                            # Build optionValues (API 2025-10 format)
                            option_values = []
                            
                            for i in range(len(option_names)):
                                option_name = option_names[i]
                                option_key = f'option{i+1}'
                                option_value = variant.get(option_key)
                                
                                if option_value:
                                    option_values.append({
                                        "optionName": option_name,
                                        "name": str(option_value)
                                    })
                            
                            if option_values:
                                variant_input['optionValues'] = option_values

                            # Note: Inventory quantities are now set via inventorySetQuantities mutation
                            # after variant creation for better reliability (see code below)

                            # Add variant metafields with key mapping
                            # Map input file keys to Shopify metafield definition keys
                            # Note: weight and dimensions are handled as standard Shopify fields, not metafields
                            VARIANT_METAFIELD_KEY_MAPPING = {
                                # Input key -> Shopify key
                                'model_number': 'model_number',
                                'size_info': 'size_info',
                                'color_swatch_image': 'color_swatch_image',
                                'texture_swatch_image': 'texture_swatch_image',
                                'finish_swatch_image': 'finish_swatch_image',
                            }

                            var_metafields = []
                            for mf in variant.get('metafields', []):
                                input_key = mf.get('key')
                                # Map the key if a mapping exists, otherwise use original
                                shopify_key = VARIANT_METAFIELD_KEY_MAPPING.get(input_key, input_key)

                                var_metafields.append({
                                    "namespace": mf.get('namespace'),
                                    "key": shopify_key,
                                    "value": mf.get('value'),
                                    "type": mf.get('type')
                                })

                                # Log if key was mapped
                                if input_key != shopify_key:
                                    logging.debug(f"    Mapped variant metafield key: '{input_key}' -> '{shopify_key}'")
                            
                            if var_metafields:
                                variant_input['metafields'] = var_metafields
                            
                            variant_inputs.append(variant_input)
                            
                        except Exception as e:
                            error_msg = f"Error preparing variant {var_idx+1}: {e}"
                            logging.error(error_msg)
                            log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                            
                            # Save restore point with error
                            result_dict = {
                                "title": product_title,
                                "shopify_id": shopify_product_id,
                                "status": "failed",
                                "error": error_msg,
                                "failed_stage": "variant_preparation",
                                "product_created": True,
                                "variants_created": False
                            }
                            add_result(result_dict)
                            products_restore = update_product_in_restore(products_restore, result_dict)
                            save_products(products_restore)
                            
                            # STOP IMMEDIATELY
                            log_and_status(status_fn, "\n" + "=" * 80)
                            log_and_status(status_fn, "❌ VARIANT PREPARATION FAILED - STOPPING", "error")
                            log_and_status(status_fn, "=" * 80)
                            return
                    
                    # Create variants in bulk (API 2025-10)
                    # ✅ CRITICAL FIX: Use REMOVE_STANDALONE_VARIANT strategy to avoid duplicates
                    # When productOptions are provided, Shopify auto-creates a default variant
                    # This strategy removes it before creating our variants
                    if variant_inputs:
                        create_variants_mutation = """
                        mutation productVariantsBulkCreate($productId: ID!, $strategy: ProductVariantsBulkCreateStrategy, $variants: [ProductVariantsBulkInput!]!) {
                          productVariantsBulkCreate(productId: $productId, strategy: $strategy, variants: $variants) {
                            productVariants {
                              id
                              sku
                              inventoryItem {
                                id
                              }
                            }
                            userErrors {
                              field
                              message
                            }
                          }
                        }
                        """
                        
                        variant_variables = {
                            "productId": shopify_product_id,
                            "strategy": "REMOVE_STANDALONE_VARIANT",  # ✅ Remove auto-created default variant
                            "variants": variant_inputs
                        }

                        log_and_status(status_fn, f"  Creating {len(variant_inputs)} variants in bulk with REMOVE_STANDALONE_VARIANT strategy")
                        logging.debug(f"Variant inputs: {json.dumps(variant_inputs, indent=2)}")
                        
                        try:
                            response = requests.post(
                                api_url,
                                json={"query": create_variants_mutation, "variables": variant_variables},
                                headers=headers,
                                timeout=60
                            )
                            response.raise_for_status()
                            result = response.json()
                            
                            # Check for GraphQL errors
                            if "errors" in result:
                                error_msg = f"GraphQL errors: {result['errors']}"
                                logging.error(error_msg)
                                log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                                
                                # Save restore point with error
                                result_dict = {
                                    "title": product_title,
                                    "shopify_id": shopify_product_id,
                                    "status": "failed",
                                    "error": error_msg,
                                    "failed_stage": "variant_creation",
                                    "product_created": True,
                                    "variants_created": False
                                }
                                add_result(result_dict)
                                products_restore = update_product_in_restore(products_restore, result_dict)
                                save_products(products_restore)
                                
                                # STOP IMMEDIATELY
                                log_and_status(status_fn, "\n" + "=" * 80)
                                log_and_status(status_fn, "❌ VARIANT CREATION FAILED - STOPPING", "error")
                                log_and_status(status_fn, "=" * 80)
                                return
                            
                            # Check for user errors
                            user_errors = result.get("data", {}).get("productVariantsBulkCreate", {}).get("userErrors", [])
                            if user_errors:
                                error_msg = "; ".join([f"{err.get('field')}: {err.get('message')}" for err in user_errors])
                                logging.error(f"Variant creation user errors: {error_msg}")
                                log_and_status(status_fn, f"  ❌ Variant creation errors: {error_msg}", "error")
                                
                                # Save restore point with error
                                result_dict = {
                                    "title": product_title,
                                    "shopify_id": shopify_product_id,
                                    "status": "failed",
                                    "error": error_msg,
                                    "failed_stage": "variant_creation",
                                    "product_created": True,
                                    "variants_created": False
                                }
                                add_result(result_dict)
                                products_restore = update_product_in_restore(products_restore, result_dict)
                                save_products(products_restore)
                                
                                # STOP IMMEDIATELY
                                log_and_status(status_fn, "\n" + "=" * 80)
                                log_and_status(status_fn, "❌ VARIANT CREATION FAILED - STOPPING", "error")
                                log_and_status(status_fn, "=" * 80)
                                return
                            
                            # Extract created variants
                            created_variants = result.get("data", {}).get("productVariantsBulkCreate", {}).get("productVariants", [])
                            
                            if not created_variants:
                                error_msg = "No variants returned from API"
                                logging.error(error_msg)
                                log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                                
                                # Save restore point with error
                                result_dict = {
                                    "title": product_title,
                                    "shopify_id": shopify_product_id,
                                    "status": "failed",
                                    "error": error_msg,
                                    "failed_stage": "variant_creation",
                                    "product_created": True,
                                    "variants_created": False
                                }
                                add_result(result_dict)
                                products_restore = update_product_in_restore(products_restore, result_dict)
                                save_products(products_restore)
                                
                                # STOP IMMEDIATELY
                                log_and_status(status_fn, "\n" + "=" * 80)
                                log_and_status(status_fn, "❌ VARIANT CREATION FAILED - STOPPING", "error")
                                log_and_status(status_fn, "=" * 80)
                                return
                            
                            log_and_status(
                                status_fn,
                                f"  ✅ Created {len(created_variants)} variants",
                                ui_msg="  ✅ Variants created"
                            )

                            # Extract variant IDs for output
                            created_variant_ids = [
                                {"id": v.get("id"), "sku": v.get("sku")}
                                for v in created_variants
                                if v.get("id")
                            ]

                            # Update restore point with successful variant creation
                            restore_data["variants_created"] = True
                            restore_data["variant_count"] = len(created_variants)
                            restore_data["variant_ids"] = created_variant_ids
                            products_restore = update_product_in_restore(products_restore, restore_data)
                            save_products(products_restore)

                            # Set inventory quantities using inventorySetQuantities mutation
                            # This is more reliable than inventoryQuantities in productVariantsBulkCreate
                            if inventory_quantity and location_id:
                                log_and_status(status_fn, f"  Setting inventory quantities...")

                                # Build quantities input for all variants
                                inventory_quantities_input = []
                                for variant in created_variants:
                                    inventory_item = variant.get("inventoryItem", {})
                                    inventory_item_id = inventory_item.get("id") if inventory_item else None

                                    if inventory_item_id:
                                        inventory_quantities_input.append({
                                            "inventoryItemId": inventory_item_id,
                                            "locationId": location_id,
                                            "quantity": inventory_quantity
                                        })

                                if inventory_quantities_input:
                                    set_inventory_mutation = """
                                    mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
                                      inventorySetQuantities(input: $input) {
                                        inventoryAdjustmentGroup {
                                          id
                                        }
                                        userErrors {
                                          field
                                          message
                                        }
                                      }
                                    }
                                    """

                                    inventory_variables = {
                                        "input": {
                                            "name": "available",
                                            "reason": "correction",
                                            "ignoreCompareQuantity": True,
                                            "quantities": inventory_quantities_input
                                        }
                                    }

                                    try:
                                        inv_response = requests.post(
                                            api_url,
                                            json={"query": set_inventory_mutation, "variables": inventory_variables},
                                            headers=headers,
                                            timeout=60
                                        )
                                        inv_response.raise_for_status()
                                        inv_result = inv_response.json()

                                        # Check for errors
                                        if "errors" in inv_result:
                                            logging.warning(f"GraphQL errors setting inventory: {inv_result['errors']}")
                                            log_and_status(status_fn, f"  ⚠️  Warning: Could not set inventory quantities", "warning")
                                        else:
                                            inv_user_errors = inv_result.get("data", {}).get("inventorySetQuantities", {}).get("userErrors", [])
                                            if inv_user_errors:
                                                error_msgs = "; ".join([f"{e.get('field')}: {e.get('message')}" for e in inv_user_errors])
                                                logging.warning(f"Inventory user errors: {error_msgs}")
                                                log_and_status(status_fn, f"  ⚠️  Warning: {error_msgs}", "warning")
                                            else:
                                                log_and_status(status_fn, f"  ✅ Set inventory quantity to {inventory_quantity} for {len(inventory_quantities_input)} variants")

                                    except Exception as inv_e:
                                        logging.warning(f"Error setting inventory quantities: {inv_e}")
                                        log_and_status(status_fn, f"  ⚠️  Warning: Could not set inventory quantities: {inv_e}", "warning")

                        except requests.exceptions.Timeout:
                            error_msg = "Request timeout creating variants"
                            logging.error(error_msg)
                            log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                            
                            # Save restore point with error
                            result_dict = {
                                "title": product_title,
                                "shopify_id": shopify_product_id,
                                "status": "failed",
                                "error": error_msg,
                                "failed_stage": "variant_creation",
                                "product_created": True,
                                "variants_created": False
                            }
                            add_result(result_dict)
                            products_restore = update_product_in_restore(products_restore, result_dict)
                            save_products(products_restore)
                            
                            # STOP IMMEDIATELY
                            log_and_status(status_fn, "\n" + "=" * 80)
                            log_and_status(status_fn, "❌ VARIANT CREATION FAILED - STOPPING", "error")
                            log_and_status(status_fn, "=" * 80)
                            return
                        
                        except requests.exceptions.RequestException as e:
                            error_msg = f"Request failed creating variants: {e}"
                            logging.error(error_msg)
                            log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                            
                            # Save restore point with error
                            result_dict = {
                                "title": product_title,
                                "shopify_id": shopify_product_id,
                                "status": "failed",
                                "error": str(e),
                                "failed_stage": "variant_creation",
                                "product_created": True,
                                "variants_created": False
                            }
                            add_result(result_dict)
                            products_restore = update_product_in_restore(products_restore, result_dict)
                            save_products(products_restore)
                            
                            # STOP IMMEDIATELY
                            log_and_status(status_fn, "\n" + "=" * 80)
                            log_and_status(status_fn, "❌ VARIANT CREATION FAILED - STOPPING", "error")
                            log_and_status(status_fn, "=" * 80)
                            return
                
                # Mark as completed
                restore_data["status"] = "completed"
                restore_data["completed_at"] = datetime.now().isoformat()
                products_restore = update_product_in_restore(products_restore, restore_data)
                save_products(products_restore)
                
                log_and_status(status_fn, f"  ✅ Product processing complete")
                
                successful += 1
                
                result_dict = {
                    "title": product_title,
                    "shopify_id": shopify_product_id,
                    "handle": product_handle,
                    "status": "completed",
                    "variant_count": len(variants) if variants else 0,
                    "variant_ids": restore_data.get("variant_ids", [])
                }
                add_result(result_dict)
                
            except Exception as e:
                error_msg = f"Unexpected error processing product: {e}"
                logging.exception(error_msg)
                log_and_status(status_fn, f"  ❌ {error_msg}", "error")
                
                # Save restore point with error
                result_dict = {
                    "title": product.get('title', 'Unknown'),
                    "status": "failed",
                    "error": str(e),
                    "failed_stage": "unexpected_error"
                }
                add_result(result_dict)
                products_restore = update_product_in_restore(products_restore, result_dict)
                save_products(products_restore)
                
                # STOP IMMEDIATELY
                log_and_status(status_fn, "\n" + "=" * 80)
                log_and_status(status_fn, "❌ UNEXPECTED ERROR - STOPPING", "error")
                log_and_status(status_fn, "=" * 80)
                return
        
        # Save final output
        log_and_status(status_fn, "\n" + "=" * 80)
        log_and_status(status_fn, "PROCESSING COMPLETE")
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, f"✅ Successful: {successful}")
        log_and_status(status_fn, f"✓ Skipped: {skipped}")
        log_and_status(status_fn, f"❌ Failed: {failed}")
        log_and_status(status_fn, f"Total: {total_products}")
        log_and_status(status_fn, "=" * 80)
        
        # Save product output (merge with existing if present)
        if product_output_file:
            log_and_status(status_fn, f"\nSaving product output to: {product_output_file}")
            try:
                # Load existing output file if present
                existing_output = {}
                if os.path.exists(product_output_file):
                    try:
                        with open(product_output_file, 'r', encoding='utf-8') as f:
                            existing_output = json.load(f)
                        log_and_status(status_fn, f"  Loaded existing output with {len(existing_output.get('products', []))} products")
                    except (json.JSONDecodeError, IOError):
                        pass  # Start fresh if file is corrupt

                # Build dict of existing products keyed by lowercase title
                existing_products = {}
                for p in existing_output.get("products", []):
                    title_key = p.get("title", "").strip().lower()
                    if title_key:
                        existing_products[title_key] = p

                # Merge new results (overwrites existing entries for same product)
                for r in results:
                    title_key = r.get("title", "").strip().lower()
                    if title_key:
                        existing_products[title_key] = r

                merged_results = list(existing_products.values())

                # Recalculate counts from merged results
                merged_successful = sum(1 for p in merged_results if p.get("status") == "completed")
                merged_skipped = sum(1 for p in merged_results if p.get("status") == "skipped")
                merged_failed = sum(1 for p in merged_results if p.get("status") == "failed")

                with open(product_output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "completed_at": datetime.now().isoformat(),
                        "total_products": len(merged_results),
                        "successful": merged_successful,
                        "skipped": merged_skipped,
                        "failed": merged_failed,
                        "products": merged_results
                    }, f, indent=4)
                log_and_status(status_fn, f"✅ Product output saved ({len(merged_results)} total products)")
            except Exception as e:
                log_and_status(status_fn, f"❌ Failed to save product output: {e}", "error")
        
        # Save collections output
        if collections_output_file:
            log_and_status(status_fn, f"Saving collections output to: {collections_output_file}")
            try:
                collections_data = load_collections()
                with open(collections_output_file, 'w', encoding='utf-8') as f:
                    json.dump(collections_data, f, indent=4)
                log_and_status(status_fn, f"✅ Collections output saved")
            except Exception as e:
                log_and_status(status_fn, f"❌ Failed to save collections output: {e}", "error")
        
        log_and_status(status_fn, f"\n✅ All processing complete!")
        log_and_status(status_fn, f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_and_status(status_fn, "=" * 80 + "\n")
        
    except Exception as e:
        log_and_status(status_fn, f"❌ Fatal error in process_products: {e}", "error")
        logging.exception("Full traceback:")
        raise



