# Shopify Product Uploader

**Version 2.6.0** - A comprehensive GUI application for uploading products to Shopify with AI-powered product enhancement, audience-based descriptions, and full variant support.

## Overview

This script uploads product data from JSON files to Shopify using the Shopify GraphQL Admin API. It handles:
- Single products and products with variants
- Product images (already uploaded to Shopify CDN)
- 3D model files (GLB/USDZ) - uploaded automatically
- Product and variant metafields
- **AI-powered product enhancement** with Claude or OpenAI
- **Audience-based product descriptions** with tabbed display
- Resume capability after interruptions
- Comprehensive logging and status tracking

## Features

### ✅ Core Functionality

1. **URL Validation**: Scans input file for non-Shopify CDN URLs and stops processing if found (except media sources which are uploaded)

2. **Product Upload**: Creates products in Shopify with:
   - Product title, description, vendor, type, category
   - Product options (e.g., Color, Size, Texture)
   - Product tags
   - Product-level metafields
   - Published status

3. **Variant Creation**: Creates all product variants with:
   - SKU, price, compare at price
   - Barcode, weight, inventory settings
   - Option values (option1, option2, option3)
   - Variant-level metafields (color swatches, size info, etc.)

4. **Media Upload**:
   - Images: Uses existing Shopify CDN URLs (already uploaded by upscaler.py)
   - 3D Models: Downloads and uploads GLB/USDZ files to Shopify CDN
   - Associates media with products

5. **State Management**:
   - Tracks processing progress in `upload_state.json`
   - Resumes from last processed product if interrupted
   - Prevents duplicate uploads on retry

6. **Output Generation**:
   - Creates output JSON with original data
   - Adds processing status to each product
   - Includes success/failure information and Shopify product IDs

### 🤖 AI Enhancement Features (NEW in v2.6.0)

**Audience-Based Product Descriptions:**
- Generate different description variants for different customer audiences
- **Single Audience Mode:** One optimized description per product
- **Multiple Audience Mode:** Two descriptions with tabbed display on storefront
- Example: "Homeowners" vs "Contractors" descriptions for same product

**AI Providers:**
- **OpenAI** (GPT-5, GPT-4o, GPT-4) - ✅ Full support with audience feature
- **Claude** (Sonnet 4.5, Opus 3.5, Haiku 3.5) - ✅ Full support with audience feature

**Features:**
- Automatic taxonomy assignment (Department → Category → Subcategory)
- Mobile-optimized description rewriting following voice/tone guidelines
- Shopify category matching using AI
- Caching to avoid re-processing unchanged products
- Cost tracking and logging

**Shopify Theme Integration:**
- Liquid snippet for tabbed product descriptions
- Mobile-responsive design (vertical tabs on small screens)
- Keyboard navigation support
- Polaris-style icons

**See:** `docs/AUDIENCE_DESCRIPTIONS_FEATURE.md` for complete documentation

### 🎨 GUI Features (Following Design Standards)

- **Modern Dark Theme**: Uses ttkbootstrap 'darkly' theme
- **Tooltips**: Every input field has helpful tooltips
- **Auto-save Configuration**: All settings saved to `config.json`
- **Settings Dialog**: Secure credential storage
- **Status Log**: 100-line status field with auto-scroll
- **Threading**: Non-blocking UI during processing
- **Validation**: Validates all inputs before processing
- **Audience Configuration:** Radio buttons + 4 input fields for audience settings
- **Smart Field Management:** Fields remain visible but disable when not needed

## Requirements

### Python Packages

```bash
pip install ttkbootstrap requests
```

### Files Needed

1. **config.json** - Auto-created on first run with default settings
2. **upload_state.json** - Auto-created during processing to track progress
3. **Input JSON file** - Your product data (e.g., techo_bloc_products.json)

## Setup

### 1. Install Dependencies

```bash
pip install ttkbootstrap requests
```

### 2. Get Shopify Credentials

You need:
- **Store URL**: Your Shopify store URL (e.g., `mystore.myshopify.com`)
- **Access Token**: A Shopify Admin API access token

To get an access token:
1. Go to Shopify Admin → Apps → Develop apps
2. Create a new app
3. Configure Admin API scopes (needs: `write_products`, `write_files`)
4. Install the app to your store
5. Copy the Admin API access token

### 3. Configure Settings

Run the script and click **⚙️ Settings** (or Settings → System Settings):
- Enter your **Store URL**
- Enter your **Access Token**
- Click **Save**

## Usage

### Basic Workflow

1. **Launch the application**:
   ```bash
   python shopify_product_uploader.py
   ```

2. **Configure file paths**:
   - **Input File**: Select your product JSON file
   - **Output File**: Choose where to save results
   - **Log File**: Choose where to save logs

3. **Validate Settings**:
   - Click **Validate Settings** to check all required fields
   - Fix any errors shown

4. **Start Processing**:
   - Click **Start Processing** to begin upload
   - Monitor progress in the Status Log
   - Processing runs in background thread (UI stays responsive)

5. **Review Results**:
   - Check the output JSON file for processing status
   - Review log file for detailed information
   - Successfully uploaded products have Shopify product IDs

### Resume After Interruption

If processing is interrupted:
1. Simply run the script again with the same input file
2. The script automatically detects the `upload_state.json` file
3. Processing resumes from the last successfully processed product
4. No duplicate uploads occur

After successful completion, the state file is automatically deleted.

## Input File Format

The input file should be a JSON file with this structure:

```json
{
  "products": [
    {
      "title": "Product Name",
      "body_html": "<p>Product description</p>",
      "vendor": "Vendor Name",
      "product_type": "Product Type",
      "product_category": "Home & Garden > ...",
      "tags": "tag1, tag2, tag3",
      "published": true,
      "options": [
        {
          "name": "Color",
          "position": 1,
          "values": ["Red", "Blue", "Green"]
        }
      ],
      "variants": [
        {
          "sku": "SKU123",
          "price": "29.99",
          "position": 1,
          "option1": "Red",
          "barcode": "123456789",
          "weight": 1.5,
          "weight_unit": "lb",
          "metafields": [
            {
              "namespace": "custom",
              "key": "color_swatch_image",
              "value": "https://cdn.shopify.com/...",
              "type": "single_line_text_field"
            }
          ]
        }
      ],
      "images": [
        {
          "position": 1,
          "src": "https://cdn.shopify.com/...",
          "alt": "Product image"
        }
      ],
      "media": [
        {
          "position": 1,
          "media_content_type": "MODEL_3D",
          "alt": "3D Model",
          "sources": [
            {
              "url": "https://example.com/model.glb",
              "format": "glb",
              "mime_type": "model/gltf-binary"
            },
            {
              "url": "https://example.com/model.usdz",
              "format": "usdz",
              "mime_type": "model/vnd.usdz+zip"
            }
          ]
        }
      ],
      "metafields": [
        {
          "namespace": "custom",
          "key": "applications",
          "value": "<ul><li>Application 1</li></ul>",
          "type": "multi_line_text_field"
        }
      ]
    }
  ]
}
```

### Important Notes About URLs

- **Images**: Must already be uploaded to Shopify CDN
  - Format: `https://cdn.shopify.com/s/files/...`
  - Use upscaler.py or similar to upload images first

- **3D Models**: Can be external URLs
  - The script downloads and uploads them to Shopify CDN
  - Supports GLB and USDZ formats

- **Metafield URLs**: Must be Shopify CDN URLs
  - Includes color swatches, size diagrams, documentation PDFs
  - The script validates all URLs before processing

## Output File Format

The output file contains:

```json
{
  "processed_at": "2025-10-25T14:30:00",
  "total_products": 10,
  "successful": 9,
  "failed": 1,
  "products": [
    {
      "title": "Product Name",
      "...": "original product data...",
      "_processing_status": {
        "success": true,
        "shopify_product_id": "gid://shopify/Product/123456",
        "error": null,
        "processed_at": "2025-10-25T14:30:15"
      }
    }
  ]
}
```

## Error Handling

### Common Errors and Solutions

1. **"Shopify credentials not configured"**
   - Solution: Configure Store URL and Access Token in Settings

2. **"Found N non-Shopify CDN URLs"**
   - Solution: All image and metafield URLs must be Shopify CDN URLs
   - Exception: 3D model URLs in media array (uploaded automatically)

3. **"Input File does not exist"**
   - Solution: Check the file path and ensure the file exists

4. **API rate limits**
   - The script includes small delays between products
   - If you hit rate limits, wait a few minutes and resume

5. **"Failed to create variant"**
   - Check variant data in log file
   - Ensure SKUs are unique
   - Verify option values match product options

## Files Created

- **config.json**: Application configuration (includes credentials)
- **upload_state.json**: Processing state (deleted after completion)
- **[your-output-file].json**: Results with processing status
- **[your-log-file].txt**: Detailed processing logs

## Logging

The script uses three-level logging:

1. **Log File** (DEBUG level):
   - Complete API requests/responses
   - Detailed processing steps
   - Full error traces

2. **Console** (INFO level):
   - Important processing events
   - Warnings and errors
   - Progress updates

3. **UI Status Field**:
   - User-friendly messages
   - Progress indicators
   - Success/failure notifications

## API Usage

The script uses Shopify's GraphQL Admin API (2024-01):

- **Staged Uploads**: For 3D model files
- **productCreate**: Creates products with images
- **productVariantCreate**: Creates variants with metafields

Required API Scopes:
- `write_products`
- `write_files`

## Best Practices

1. **Test with small batches first**
   - Start with 5-10 products to verify everything works
   - Check output file and Shopify admin

2. **Backup your data**
   - Keep backups of input files
   - Save output files for reference

3. **Monitor the logs**
   - Watch for warnings during processing
   - Review log file after completion

4. **Validate URLs before upload**
   - Ensure all images are on Shopify CDN
   - The script will stop if it finds non-CDN URLs

5. **Use descriptive filenames**
   - Include dates in output/log filenames
   - Example: `results_2025-10-25.json`

## Troubleshooting

### Script won't start
- Check Python version (3.7+)
- Verify all packages installed: `pip install ttkbootstrap requests`

### Can't connect to Shopify
- Verify Store URL format (no https://, just `store.myshopify.com`)
- Check Access Token is correct
- Ensure API scopes include `write_products` and `write_files`

### Products created but variants missing
- Check variant data in log file
- Verify option values match product options exactly
- Ensure metafield types are correct

### Processing is slow
- Normal - Each product requires multiple API calls
- 3D model uploads take extra time
- Be patient, monitor status log

## Support

For issues related to:
- **Script functionality**: Check log file for detailed errors
- **Shopify API**: Refer to [Shopify GraphQL Admin API docs](https://shopify.dev/docs/api/admin-graphql)
- **Product data format**: Review the input file format section above

## Version History

### Version 1.0 (2025-10-25)
- Initial release
- Product and variant creation
- 3D model upload support
- Resume capability
- Comprehensive GUI following design standards

## License

This script is provided as-is for use with Shopify stores.
