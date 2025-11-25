"""
Shopify API operations for Product Uploader.

This module contains all functions that interact with the Shopify GraphQL Admin API.
"""

import json
import logging
import requests
from .config import log_and_status
from .utils import key_to_label


def get_sales_channel_ids(cfg):
    """
    Retrieve Shopify sales channel IDs for Online Store and Point of Sale.

    Args:
        cfg: Configuration dictionary

    Returns:
        Dictionary with 'online_store' and 'point_of_sale' IDs, or None on error
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            logging.error("Shopify credentials not configured")
            return None

        store_url = store_url.replace("https://", "").replace("http://", "")

        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        query = """
        query {
          publications(first: 10) {
            edges {
              node {
                id
                name
              }
            }
          }
        }
        """

        response = requests.post(
            api_url,
            json={"query": query},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            logging.error(f"GraphQL errors retrieving sales channels: {result['errors']}")
            return None

        publications = result.get("data", {}).get("publications", {}).get("edges", [])

        channel_ids = {}
        for edge in publications:
            node = edge.get("node", {})
            name = node.get("name", "").lower()
            channel_id = node.get("id")

            if "online store" in name:
                channel_ids["online_store"] = channel_id
            elif "point of sale" in name:
                channel_ids["point_of_sale"] = channel_id

        if channel_ids:
            logging.info(f"Retrieved {len(channel_ids)} sales channel IDs")
            return channel_ids
        else:
            logging.warning("No sales channels found")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error retrieving sales channels: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error retrieving sales channels: {e}")
        return None




def publish_collection_to_channels(collection_id, sales_channel_ids, cfg):
    """
    Publish a collection to specified sales channels.

    Args:
        collection_id: Shopify collection ID (e.g., gid://shopify/Collection/123)
        sales_channel_ids: Dictionary with 'online_store' and 'point_of_sale' publication IDs
        cfg: Configuration dictionary

    Returns:
        True if published successfully, False otherwise
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            logging.error("Shopify credentials not configured")
            return False

        store_url = store_url.replace("https://", "").replace("http://", "")
        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        # Mutation to publish collection to publications
        mutation = """
        mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
          publishablePublish(id: $id, input: $input) {
            publishable {
              availablePublicationsCount {
                count
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """

        # Build publications input
        publications = []
        if sales_channel_ids.get('online_store'):
            publications.append({"publicationId": sales_channel_ids['online_store']})
        if sales_channel_ids.get('point_of_sale'):
            publications.append({"publicationId": sales_channel_ids['point_of_sale']})

        if not publications:
            logging.warning("No sales channels configured for collection publishing")
            return False

        variables = {
            "id": collection_id,
            "input": publications
        }

        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            logging.error(f"GraphQL errors publishing collection: {result['errors']}")
            return False

        user_errors = result.get("data", {}).get("publishablePublish", {}).get("userErrors", [])
        if user_errors:
            error_msg = "; ".join([f"{err.get('field')}: {err.get('message')}" for err in user_errors])
            logging.error(f"Collection publishing user errors: {error_msg}")
            return False

        logging.info(f"Successfully published collection {collection_id} to {len(publications)} channels")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error publishing collection: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error publishing collection: {e}")
        return False




def publish_product_to_channels(product_id, sales_channel_ids, cfg):
    """
    Publish a product to Online Store and Point of Sale.

    Args:
        product_id: Shopify product ID (GID format)
        sales_channel_ids: Dictionary with channel IDs
        cfg: Configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            logging.error("Shopify credentials not configured")
            return False

        store_url = store_url.replace("https://", "").replace("http://", "")

        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        # Prepare publication IDs
        publication_ids = []
        if sales_channel_ids.get("online_store"):
            publication_ids.append(sales_channel_ids["online_store"])
        if sales_channel_ids.get("point_of_sale"):
            publication_ids.append(sales_channel_ids["point_of_sale"])

        if not publication_ids:
            logging.warning("No sales channels to publish to")
            return False

        mutation = """
        mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
          publishablePublish(id: $id, input: $input) {
            publishable {
              availablePublicationsCount {
                count
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
            "id": product_id,
            "input": [{"publicationId": pub_id} for pub_id in publication_ids]
        }

        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            logging.error(f"GraphQL errors publishing product: {result['errors']}")
            return False

        user_errors = result.get("data", {}).get("publishablePublish", {}).get("userErrors", [])
        if user_errors:
            error_msg = "; ".join([f"{err.get('field')}: {err.get('message')}" for err in user_errors])
            logging.error(f"Publishing errors: {error_msg}")
            return False

        logging.info(f"Successfully published product {product_id} to {len(publication_ids)} channels")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error publishing product: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error publishing product: {e}")
        return False




def delete_shopify_product(product_id, cfg):
    """
    Delete a product from Shopify.

    Args:
        product_id: Shopify product ID (GID format)
        cfg: Configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            logging.error("Shopify credentials not configured for deletion")
            return False

        store_url = store_url.replace("https://", "").replace("http://", "")

        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        mutation = """
        mutation productDelete($input: ProductDeleteInput!) {
          productDelete(input: $input) {
            deletedProductId
            userErrors {
              field
              message
            }
          }
        }
        """

        variables = {
            "input": {
                "id": product_id
            }
        }

        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            logging.error(f"GraphQL errors deleting product: {result['errors']}")
            return False

        user_errors = result.get("data", {}).get("productDelete", {}).get("userErrors", [])
        if user_errors:
            error_msg = "; ".join([f"{err.get('field')}: {err.get('message')}" for err in user_errors])
            logging.error(f"Product deletion errors: {error_msg}")

            # Check if error is "Product does not exist" - this is OK, product is already gone
            product_not_found = any(
                "does not exist" in err.get('message', '').lower() or
                "not found" in err.get('message', '').lower()
                for err in user_errors
            )

            if product_not_found:
                logging.info(f"Product already deleted (doesn't exist): {product_id}")
                return True  # Treat as success since product is already gone

            return False

        deleted_id = result.get("data", {}).get("productDelete", {}).get("deletedProductId")
        if deleted_id:
            logging.info(f"Successfully deleted product: {deleted_id}")
            return True
        else:
            logging.error("No deleted product ID returned")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error deleting product: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error deleting product: {e}")
        return False




def search_collection(name, cfg):
    """
    Search for a collection by name in Shopify.

    Args:
        name: Collection name to search for
        cfg: Configuration dictionary

    Returns:
        Dictionary with 'id' and 'handle' if found, None otherwise
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            logging.error("Shopify credentials not configured for collection search")
            return None

        store_url = store_url.replace("https://", "").replace("http://", "")

        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        query = """
        query searchCollections($query: String!) {
          collections(first: 5, query: $query) {
            edges {
              node {
                id
                title
                handle
              }
            }
          }
        }
        """

        variables = {
            "query": f"title:{name}"
        }

        response = requests.post(
            api_url,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            logging.error(f"GraphQL errors searching collection: {result['errors']}")
            return None

        edges = result.get("data", {}).get("collections", {}).get("edges", [])

        # Find exact match
        for edge in edges:
            node = edge.get("node", {})
            if node.get("title", "").lower() == name.lower():
                return {
                    "id": node.get("id"),
                    "handle": node.get("handle")
                }

        return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error searching collection: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error searching collection: {e}")
        return None




def create_collection(name, rules, cfg, description=None):
    """
    Create a collection in Shopify.

    Args:
        name: Collection name
        rules: List of rule dictionaries (column, relation, condition)
        cfg: Configuration dictionary
        description: Optional collection description (plain text)

    Returns:
        Dictionary with 'id' and 'handle' if successful, None otherwise
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            logging.error("Shopify credentials not configured for collection creation")
            return None

        store_url = store_url.replace("https://", "").replace("http://", "")

        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        mutation = """
        mutation collectionCreate($input: CollectionInput!) {
          collectionCreate(input: $input) {
            collection {
              id
              title
              handle
            }
            userErrors {
              field
              message
            }
          }
        }
        """

        variables = {
            "input": {
                "title": name,
                "ruleSet": {
                    "appliedDisjunctively": False,
                    "rules": rules
                }
            }
        }

        # Add description if provided
        if description:
            variables["input"]["descriptionHtml"] = f"<p>{description}</p>"

        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            logging.error(f"GraphQL errors creating collection: {result['errors']}")
            return None

        user_errors = result.get("data", {}).get("collectionCreate", {}).get("userErrors", [])
        if user_errors:
            error_msg = "; ".join([f"{err.get('field')}: {err.get('message')}" for err in user_errors])
            logging.error(f"Collection creation user errors: {error_msg}")
            return None

        collection = result.get("data", {}).get("collectionCreate", {}).get("collection", {})

        if collection and collection.get("id"):
            return {
                "id": collection.get("id"),
                "handle": collection.get("handle")
            }
        else:
            logging.error("No collection data returned from API")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error creating collection: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error creating collection: {e}")
        return None




def create_metafield_definition(namespace, key, metafield_type, owner_type, cfg, pin=True, status_fn=None):
    """
    Create a metafield definition in Shopify if it doesn't exist.

    Args:
        namespace: Metafield namespace (e.g., "custom")
        key: Metafield key (e.g., "layout_possibilities")
        metafield_type: Shopify metafield type (e.g., "json", "single_line_text_field")
        owner_type: Owner type (e.g., "PRODUCT", "VARIANT")
        cfg: Configuration dictionary
        pin: Whether to pin the metafield (default True)
        status_fn: Optional status update function

    Returns:
        True if created or already exists, False on error
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            if status_fn:
                log_and_status(status_fn, "Shopify credentials not configured", "error")
            else:
                logging.error("Shopify credentials not configured")
            return False

        store_url = store_url.replace("https://", "").replace("http://", "")
        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        # Generate human-readable label from key
        label = key_to_label(key)

        mutation = """
        mutation CreateMetafieldDefinition($definition: MetafieldDefinitionInput!) {
          metafieldDefinitionCreate(definition: $definition) {
            createdDefinition {
              id
              name
              namespace
              key
            }
            userErrors {
              field
              message
              code
            }
          }
        }
        """

        variables = {
            "definition": {
                "name": label,
                "namespace": namespace,
                "key": key,
                "type": metafield_type,
                "ownerType": owner_type,
                "pin": pin
            }
        }

        if status_fn:
            log_and_status(status_fn, f"Creating metafield definition: {namespace}.{key} ({label}) for {owner_type}")
        else:
            logging.info(f"Creating metafield definition: {namespace}.{key} ({label}) for {owner_type}")

        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            if status_fn:
                log_and_status(status_fn, f"GraphQL errors creating metafield definition: {result['errors']}", "error")
            else:
                logging.error(f"GraphQL errors creating metafield definition: {result['errors']}")
            return False

        user_errors = result.get("data", {}).get("metafieldDefinitionCreate", {}).get("userErrors", [])
        if user_errors:
            # Check if error is "already exists" - that's OK
            for error in user_errors:
                code = error.get('code', '')
                message = error.get('message', '')
                if code == 'TAKEN' or 'already exists' in message.lower():
                    if status_fn:
                        log_and_status(status_fn, f"  Metafield definition already exists: {namespace}.{key}")
                    else:
                        logging.info(f"  Metafield definition already exists: {namespace}.{key}")
                    return True
                else:
                    if status_fn:
                        log_and_status(status_fn, f"  Error creating metafield definition: {message} (code: {code})", "error")
                    else:
                        logging.error(f"  Error creating metafield definition: {message} (code: {code})")
            return False

        created_def = result.get("data", {}).get("metafieldDefinitionCreate", {}).get("createdDefinition", {})
        if created_def and created_def.get("id"):
            if status_fn:
                log_and_status(status_fn, f"  ✅ Created metafield definition: {namespace}.{key} ({label})")
            else:
                logging.info(f"  ✅ Created metafield definition: {namespace}.{key} ({label})")
            return True
        else:
            if status_fn:
                log_and_status(status_fn, "No metafield definition data returned from API", "error")
            else:
                logging.error("No metafield definition data returned from API")
            return False

    except requests.exceptions.RequestException as e:
        if status_fn:
            log_and_status(status_fn, f"Network error creating metafield definition: {e}", "error")
        else:
            logging.error(f"Network error creating metafield definition: {e}")
        return False
    except Exception as e:
        if status_fn:
            log_and_status(status_fn, f"Unexpected error creating metafield definition: {e}", "error")
        else:
            logging.error(f"Unexpected error creating metafield definition: {e}")
        logging.exception("Full traceback:")
        return False




def upload_model_to_shopify(model_url, filename, cfg, status_fn=None):
    """
    Upload a 3D model to Shopify using API 2025-10 staged upload process.

    Args:
        model_url: URL of the model file to upload
        filename: Filename for the model
        cfg: Configuration dictionary
        status_fn: Optional status update function

    Returns:
        Tuple of (cdn_url, file_id) if successful, (None, None) otherwise
    """
    try:
        store_url = cfg.get("SHOPIFY_STORE_URL", "").strip()
        access_token = cfg.get("SHOPIFY_ACCESS_TOKEN", "").strip()

        if not store_url or not access_token:
            if status_fn:
                log_and_status(status_fn, "Shopify credentials not configured for model upload", "error")
            else:
                logging.error("Shopify credentials not configured for model upload")
            return None, None

        store_url = store_url.replace("https://", "").replace("http://", "")

        # API 2025-10 endpoint
        api_url = f"https://{store_url}/admin/api/2025-10/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        # Determine MIME type
        mime_type = "model/gltf-binary" if filename.lower().endswith('.glb') else "model/vnd.usdz+zip"

        # Step 1: Download model from source to get file size
        if status_fn:
            log_and_status(status_fn, f"  Step 1: Downloading model from {model_url}")
        else:
            logging.info(f"Step 1: Downloading model from {model_url}")
        model_response = requests.get(model_url, timeout=120)
        model_response.raise_for_status()
        model_data = model_response.content
        file_size = len(model_data)

        # Step 2: Create staged upload with file size
        if status_fn:
            log_and_status(status_fn, f"  Step 2: Creating staged upload for {filename} ({file_size} bytes)")
        else:
            logging.info(f"Step 2: Creating staged upload for {filename} ({file_size} bytes)")

        staged_upload_mutation = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
          stagedUploadsCreate(input: $input) {
            stagedTargets {
              url
              resourceUrl
              parameters {
                name
                value
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
            "input": [
                {
                    "resource": "MODEL_3D",
                    "filename": filename,
                    "mimeType": mime_type,
                    "fileSize": str(file_size),
                    "httpMethod": "POST"
                }
            ]
        }

        response = requests.post(
            api_url,
            json={"query": staged_upload_mutation, "variables": variables},
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result or result.get("data", {}).get("stagedUploadsCreate", {}).get("userErrors"):
            if status_fn:
                log_and_status(status_fn, f"Failed to create staged upload: {result}", "error")
            else:
                logging.error(f"Failed to create staged upload: {result}")
            return None, None

        staged_target = result.get("data", {}).get("stagedUploadsCreate", {}).get("stagedTargets", [None])[0]
        if not staged_target:
            if status_fn:
                log_and_status(status_fn, "No staged target returned", "error")
            else:
                logging.error("No staged target returned")
            return None, None

        upload_url = staged_target.get("url")
        resource_url = staged_target.get("resourceUrl")
        parameters = {p["name"]: p["value"] for p in staged_target.get("parameters", [])}

        # Step 3: Upload to staged URL
        if status_fn:
            log_and_status(status_fn, f"  Step 3: Uploading model to staged URL")
        else:
            logging.info(f"Step 3: Uploading model to staged URL")
        files = {'file': (filename, model_data, mime_type)}
        upload_response = requests.post(upload_url, data=parameters, files=files, timeout=120)
        upload_response.raise_for_status()

        # Return the resourceUrl - this is what we use in productCreateMedia
        if status_fn:
            log_and_status(status_fn, f"  ✅ Model uploaded to Shopify staging (resourceUrl: {resource_url})")
        else:
            logging.info(f"Model uploaded successfully: {resource_url}")

        return resource_url, None  # Return resourceUrl as cdn_url, no file_id needed

        # OLD APPROACH - NOT NEEDED
        # Step 4: Create file record in Shopify
        if status_fn:
            log_and_status(status_fn, f"  Step 4: Creating file record in Shopify")
        else:
            logging.info(f"Step 4: Creating file record in Shopify")

        file_create_mutation = """
        mutation fileCreate($files: [FileCreateInput!]!) {
          fileCreate(files: $files) {
            files {
              ... on Model3d {
                id
                originalSource {
                  url
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

        file_variables = {
            "files": [
                {
                    "alt": filename,
                    "contentType": "MODEL_3D",
                    "originalSource": resource_url
                }
            ]
        }

        file_response = requests.post(
            api_url,
            json={"query": file_create_mutation, "variables": file_variables},
            headers=headers,
            timeout=60
        )
        file_response.raise_for_status()
        file_result = file_response.json()

        # Log the full response for debugging
        logging.debug(f"fileCreate response: {json.dumps(file_result, indent=2)}")

        if "errors" in file_result or file_result.get("data", {}).get("fileCreate", {}).get("userErrors"):
            user_errors = file_result.get("data", {}).get("fileCreate", {}).get("userErrors", [])
            if status_fn:
                log_and_status(status_fn, f"Failed to create file record. Errors: {file_result.get('errors', user_errors)}", "error")
            else:
                logging.error(f"Failed to create file record: {file_result}")
            return None, None

        files = file_result.get("data", {}).get("fileCreate", {}).get("files", [])
        if not files:
            if status_fn:
                log_and_status(status_fn, "No files returned from fileCreate", "error")
            else:
                logging.error("No files returned from fileCreate")
            return None, None

        file_data = files[0]
        if not file_data:
            if status_fn:
                log_and_status(status_fn, "File data is None/empty in fileCreate response", "error")
            else:
                logging.error("File data is None/empty in fileCreate response")
            return None, None

        file_id = file_data.get("id")
        original_source = file_data.get("originalSource")
        cdn_url = original_source.get("url") if original_source else None

        # Log what we extracted
        logging.debug(f"Extracted from fileCreate: file_id={file_id}, cdn_url={cdn_url}")
        if not cdn_url:
            logging.warning(f"No CDN URL in response. originalSource={original_source}, file_data keys={list(file_data.keys())}")

        if status_fn:
            log_and_status(status_fn, f"  ✅ Successfully uploaded model: {file_id}")
        else:
            logging.info(f"Successfully uploaded model: {file_id}")
        return cdn_url, file_id

    except requests.exceptions.RequestException as e:
        if status_fn:
            log_and_status(status_fn, f"Network error uploading model: {e}", "error")
        else:
            logging.error(f"Network error uploading model: {e}")
        return None, None
    except Exception as e:
        if status_fn:
            log_and_status(status_fn, f"Unexpected error uploading model: {e}", "error")
        else:
            logging.error(f"Unexpected error uploading model: {e}")
        return None, None
