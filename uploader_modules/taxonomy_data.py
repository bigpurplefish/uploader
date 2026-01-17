"""
Taxonomy data structure for Shopify Product Uploader.

This module defines the complete product taxonomy with the correct ordering
for menu items. The order defined here determines the order of menu items
in the Shopify navigation.
"""

# Complete taxonomy structure
# Order matters - items will appear in menus in this order
TAXONOMY = {
    "Landscape and Construction": {
        "order": 1,
        "categories": {
            "Aggregates": {
                "order": 1,
                "subcategories": ["Stone", "Soil", "Mulch", "Sand"]
            },
            "Pavers and Hardscaping": {
                "order": 2,
                "subcategories": [
                    "Pavers",
                    "Slabs",
                    "Retaining Walls",
                    "Wall Caps",
                    "Steps & Treads",
                    "Edging & Borders",
                    "Joint Sand & Polymeric Sand",
                    "Sealers & Cleaners",
                    "Base Materials & Geotextiles",
                    "Accessories"
                ]
            },
            "Paving Tools & Equipment": {
                "order": 3,
                "subcategories": ["Hand Tools", "Compactors", "Screeds"]
            },
            "Paving & Construction Supplies": {
                "order": 4,
                "subcategories": ["Edging", "Adhesives", "Spikes", "Sealers"]
            }
        }
    },
    "Lawn and Garden": {
        "order": 2,
        "categories": {
            "Garden Tools": {
                "order": 1,
                "subcategories": ["Shovels", "Wheelbarrows", "Pruners", "Gloves"]
            },
            "Garden Supplies": {
                "order": 2,
                "subcategories": ["Fertilizers", "Soil Conditioners", "Planters", "Watering Systems"]
            },
            "Garden Decor": {
                "order": 3,
                "subcategories": ["Flags", "Stakes", "Chimes", "Statues"]
            }
        }
    },
    "Home and Gift": {
        "order": 3,
        "categories": {
            "Home Decor": {
                "order": 1,
                "subcategories": ["Candles", "Wall Art", "Seasonal Decorations"]
            },
            "Gifts": {
                "order": 2,
                "subcategories": ["Gift Cards", "Novelty Items", "Themed Gifts"]
            }
        }
    },
    "Pet Supplies": {
        "order": 4,
        "categories": {
            "Dogs": {
                "order": 1,
                "subcategories": [
                    "Bedding", "Carriers", "Chews", "Cleaning", "Collars",
                    "Crates", "Food", "Grooming", "Harnesses", "Training Tools",
                    "Toys", "Treats", "Waste", "Accessories"
                ]
            },
            "Cats": {
                "order": 2,
                "subcategories": [
                    "Bedding", "Carriers", "Cleaning", "Collars", "Food",
                    "Grooming", "Harnesses", "Toys", "Treats", "Waste", "Accessories"
                ]
            },
            "Birds": {
                "order": 3,
                "subcategories": ["Cages", "Health", "Seeds", "Toys", "Treats", "Accessories"]
            },
            "Small Pets": {
                "order": 4,
                "subcategories": ["Bedding", "Cages", "Food", "Accessories"]
            }
        }
    },
    "Livestock and Farm": {
        "order": 5,
        "categories": {
            "Horses": {
                "order": 1,
                "subcategories": ["Feed", "Health", "Tack & Equipment", "Accessories"]
            },
            "Chickens": {
                "order": 2,
                "subcategories": ["Feed", "Supplies", "Accessories"]
            },
            "Goats": {
                "order": 3,
                "subcategories": ["Feed", "Health", "Accessories"]
            },
            "Sheep": {
                "order": 4,
                "subcategories": ["Feed", "Health", "Accessories"]
            },
            "General Farm Supplies": {
                "order": 5,
                "subcategories": ["Buckets", "Scoops", "Fencing", "Tools"]
            }
        }
    },
    "Hunting and Fishing": {
        "order": 6,
        "categories": {
            "Deer": {
                "order": 1,
                "subcategories": ["Attractants", "Minerals & Supplements", "Gear", "Food Plots", "Scent Control"]
            }
        }
    }
}


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
