# Shopify Product Uploader - Quick Start Guide

## Installation (One-Time Setup)

1. Install required packages:
   ```bash
   pip install ttkbootstrap requests
   ```

2. Get Shopify credentials:
   - Store URL: `yourstore.myshopify.com`
   - Access Token: From Shopify Admin → Apps → Develop apps
   - Required API scopes: `write_products`, `write_files`

## Usage (Every Time)

### Step 1: Launch
```bash
python shopify_product_uploader.py
```

### Step 2: Configure Credentials (First Time Only)
1. Click **⚙️ Settings** button
2. Enter Store URL (e.g., `mystore.myshopify.com`)
3. Enter Access Token
4. Click **Save**

### Step 3: Select Files
- **Input File**: Your product JSON (e.g., `techo_bloc_products.json`)
- **Output File**: Where to save results (e.g., `upload_results.json`)
- **Log File**: Where to save logs (e.g., `upload_log.txt`)

### Step 4: Validate & Run
1. Click **Validate Settings** - fixes any issues
2. Click **Start Processing** - begins upload
3. Monitor progress in Status Log
4. Wait for completion message

### Step 5: Review Results
- Check output JSON for processing status
- Review log file for details
- Verify products in Shopify Admin

## Key Features

✅ **URL Validation**: Stops if non-Shopify CDN URLs found (except media)
✅ **3D Model Upload**: Automatically uploads GLB/USDZ files
✅ **Resume Support**: Continues from last product if interrupted
✅ **State Tracking**: Creates `upload_state.json` during processing
✅ **Comprehensive Logging**: File, console, and UI status updates

## Important Notes

⚠️ **All image URLs must be Shopify CDN URLs**
   - Format: `https://cdn.shopify.com/s/files/...`
   - Use upscaler.py first to upload images

⚠️ **3D models can be external URLs**
   - Script downloads and uploads them automatically
   - Supports: GLB, USDZ formats

⚠️ **Processing takes time**
   - Multiple API calls per product
   - 3D models add extra time
   - Be patient, watch status log

## If Processing Is Interrupted

1. Don't panic! State is saved.
2. Simply run the script again
3. Select the same input file
4. Script automatically resumes from last processed product
5. No duplicates are created

## Troubleshooting

**Can't start script?**
- Check: `pip install ttkbootstrap requests`

**Validation fails?**
- Verify all file paths exist
- Check credentials in Settings

**URL validation error?**
- All images must be on Shopify CDN
- Exception: 3D models in media array

**API errors?**
- Verify Store URL (no `https://`)
- Check Access Token
- Ensure API scopes: `write_products`, `write_files`

## Files Created

- `config.json` - Your settings (includes credentials)
- `upload_state.json` - Processing state (deleted when complete)
- `[output-file].json` - Results with status
- `[log-file].txt` - Detailed logs

## Need Help?

1. Check the full README.md for detailed documentation
2. Review log file for specific errors
3. Verify input JSON format matches requirements
4. Consult Shopify GraphQL Admin API docs

## Quick Example

```bash
# 1. Install
pip install ttkbootstrap requests

# 2. Run
python shopify_product_uploader.py

# 3. In GUI:
#    - Settings → Enter credentials
#    - Input: techo_bloc_products.json
#    - Output: results.json
#    - Log: upload.log
#    - Validate Settings
#    - Start Processing

# 4. Wait for completion
# 5. Check results.json
```

That's it! 🎉
