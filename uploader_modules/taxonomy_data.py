"""
Taxonomy data structure for Shopify Product Uploader.

This module loads the product taxonomy from the canonical shared-docs taxonomy document:
  /Users/moosemarketer/Code/garoppos/shared-docs/PRODUCT_TAXONOMY.md

The taxonomy is parsed once at import time and cached in the module-level TAXONOMY dict.
The document is the single source of truth — make taxonomy changes there, not here.
This ensures the uploader stays in sync with the AI categorizer, which also reads
from the same canonical document.

If the document cannot be found or parsed, a ValueError is raised with the expected path.
"""

import re
import os

# Canonical path to the shared taxonomy document
_TAXONOMY_DOC_PATH = "/Users/moosemarketer/Code/garoppos/shared-docs/PRODUCT_TAXONOMY.md"


def _parse_taxonomy(doc_path):
    """
    Parse PRODUCT_TAXONOMY.md and return the nested TAXONOMY dict.

    Expected markdown structure (under '## Complete Product Taxonomy'):
      ### N. DEPARTMENT NAME
      **Product Type:** `Display Name`
      #### Category Name
      - **Subcategories:**
        1. Subcategory One
        2. **Subcategory Two**
      ---

    Returns a dict with structure:
      {
        "Department Display Name": {
          "order": N,
          "categories": {
            "Category Name": {
              "order": M,
              "subcategories": ["Sub1", "Sub2", ...]
            },
            ...
          }
        },
        ...
      }
    """
    if not os.path.exists(doc_path):
        raise ValueError(
            f"Taxonomy document not found at expected path: {doc_path}\n"
            "Ensure shared-docs is checked out at the correct location."
        )

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the "## Complete Product Taxonomy" section
    taxonomy_section_match = re.search(r"## Complete Product Taxonomy\s*\n", content)
    if not taxonomy_section_match:
        raise ValueError(
            f"Could not find '## Complete Product Taxonomy' section in {doc_path}"
        )

    # Grab text from the taxonomy section start until the next ## heading (next major section)
    remaining = content[taxonomy_section_match.end():]
    next_h2 = re.search(r"^## ", remaining, re.MULTILINE)
    taxonomy_text = remaining[:next_h2.start()] if next_h2 else remaining

    taxonomy = {}

    # Split into department blocks on "### N. DEPARTMENT NAME" lines
    dept_pattern = re.compile(r"^### (\d+)\. (.+)$", re.MULTILINE)
    dept_matches = list(dept_pattern.finditer(taxonomy_text))

    if not dept_matches:
        raise ValueError(
            f"No department headers (### N. NAME) found in taxonomy section of {doc_path}"
        )

    for i, dept_match in enumerate(dept_matches):
        dept_order = int(dept_match.group(1))
        # Determine end of this department's block
        block_start = dept_match.end()
        block_end = dept_matches[i + 1].start() if i + 1 < len(dept_matches) else len(taxonomy_text)
        dept_block = taxonomy_text[block_start:block_end]

        # Extract the canonical display name from **Product Type:** `Name`
        product_type_match = re.search(r"\*\*Product Type:\*\*\s*`([^`]+)`", dept_block)
        if not product_type_match:
            raise ValueError(
                f"Department #{dept_order} is missing a '**Product Type:** `Name`' line in {doc_path}"
            )
        dept_display_name = product_type_match.group(1)

        # Parse categories within this department block
        categories = {}
        cat_pattern = re.compile(r"^#### (.+)$", re.MULTILINE)
        cat_matches = list(cat_pattern.finditer(dept_block))

        for j, cat_match in enumerate(cat_matches):
            cat_order = j + 1
            cat_name = cat_match.group(1).strip()
            cat_block_start = cat_match.end()
            cat_block_end = cat_matches[j + 1].start() if j + 1 < len(cat_matches) else len(dept_block)
            cat_block = dept_block[cat_block_start:cat_block_end]

            # Find subcategories section (numbered list items under "**Subcategories:**")
            # Items can be:  "  1. Name" or "  1. **Name**" (bold with possible sub-bullets)
            subcategories = []
            in_subcategories = False
            for line in cat_block.splitlines():
                stripped = line.strip()
                if "**Subcategories:**" in stripped:
                    in_subcategories = True
                    continue
                if in_subcategories:
                    # Stop at a new section marker or empty bold header
                    if stripped.startswith("---") or stripped.startswith("**Tags:**") or stripped.startswith("**Note:**"):
                        continue
                    # Numbered list item: "1. Name" or "1. **Name**"
                    numbered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
                    if numbered_match:
                        raw_name = numbered_match.group(1).strip()
                        # Strip bold markers: **Name** → Name
                        clean_name = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw_name).strip()
                        # Remove trailing parenthetical notes like "(coops | feeders | waterers)"
                        clean_name = re.sub(r"\s*\([^)]*\)\s*$", "", clean_name).strip()
                        if clean_name:
                            subcategories.append(clean_name)
                    elif stripped.startswith("-") and subcategories:
                        # Sub-bullet under a numbered item — skip (extra tag details)
                        continue
                    elif stripped == "" and subcategories:
                        # Blank line might end the list; keep going to catch multi-paragraph lists
                        continue

            categories[cat_name] = {
                "order": cat_order,
                "subcategories": subcategories,
            }

        taxonomy[dept_display_name] = {
            "order": dept_order,
            "categories": categories,
        }

    return taxonomy


def _load_taxonomy():
    """Load and return the parsed taxonomy, raising on failure."""
    try:
        return _parse_taxonomy(_TAXONOMY_DOC_PATH)
    except (ValueError, OSError) as exc:
        raise ValueError(
            f"Failed to load product taxonomy from canonical document.\n"
            f"Expected path: {_TAXONOMY_DOC_PATH}\n"
            f"Error: {exc}"
        ) from exc


# Module-level TAXONOMY — populated once at import time from the canonical doc.
# Do not edit the taxonomy here. Edit shared-docs/PRODUCT_TAXONOMY.md instead.
TAXONOMY = _load_taxonomy()


def get_department_order(department_name):
    """Get the sort order for a department."""
    dept = TAXONOMY.get(department_name, {})
    return dept.get("order", 999)


def get_category_order(department_name, category_name):
    """Get the sort order for a category within a department."""
    dept = TAXONOMY.get(department_name, {})
    categories = dept.get("categories", {})
    cat = categories.get(category_name, {})
    return cat.get("order", 999)


def get_subcategory_order(department_name, category_name, subcategory_name):
    """Get the sort order for a subcategory within a category."""
    dept = TAXONOMY.get(department_name, {})
    categories = dept.get("categories", {})
    cat = categories.get(category_name, {})
    subcategories = cat.get("subcategories", [])

    try:
        return subcategories.index(subcategory_name) + 1
    except ValueError:
        return 999


def get_all_categories_for_department(department_name):
    """Get all categories for a department in order."""
    dept = TAXONOMY.get(department_name, {})
    categories = dept.get("categories", {})

    # Sort by order
    sorted_cats = sorted(categories.items(), key=lambda x: x[1].get("order", 999))
    return [cat_name for cat_name, _ in sorted_cats]


def get_all_subcategories_for_category(department_name, category_name):
    """Get all subcategories for a category in order."""
    dept = TAXONOMY.get(department_name, {})
    categories = dept.get("categories", {})
    cat = categories.get(category_name, {})
    return cat.get("subcategories", [])


def is_valid_taxonomy_path(department, category=None, subcategory=None):
    """Check if a taxonomy path is valid."""
    if department not in TAXONOMY:
        return False

    if category is None:
        return True

    dept = TAXONOMY[department]
    if category not in dept.get("categories", {}):
        return False

    if subcategory is None:
        return True

    cat = dept["categories"][category]
    return subcategory in cat.get("subcategories", [])
