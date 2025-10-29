# Audience-Based Product Descriptions Feature

## Overview

The Audience-Based Product Descriptions feature allows you to generate and display different product description variants optimized for specific customer audiences. This feature is integrated into the AI enhancement system and supports both single and multiple audience configurations.

**Version:** 2.6.0+
**AI Providers:** OpenAI (GPT-5), Claude (Sonnet 4.5, Opus 3.5, Haiku 3.5) - Both fully supported ✅
**Shopify API:** 2025-10

## Use Cases

### Example 1: Homeowners vs. Contractors (Hardscaping Products)

**Scenario:** Techo-Bloc sells pavers and hardscaping products to both residential homeowners and professional contractors.

**Audience 1 - Homeowners:**
- Emphasize aesthetics, curb appeal, and DIY installation
- Use accessible language
- Focus on lifestyle benefits ("Create your dream patio")
- Highlight ease of maintenance

**Audience 2 - Contractors:**
- Emphasize durability, installation efficiency, and technical specifications
- Use industry terminology
- Focus on project outcomes and client satisfaction
- Highlight warranty and support for commercial installations

### Example 2: Beginners vs. Professionals (Tools/Equipment)

**Audience 1 - Beginners:**
- Explain basic features and safety considerations
- Use simple, educational language
- Focus on ease of use and learning resources

**Audience 2 - Professionals:**
- Highlight advanced features and precision specs
- Use technical language
- Focus on efficiency and professional-grade performance

## How It Works

### 1. Configuration (Python GUI)

In the main uploader window, configure audience settings.

**GUI Layout:**
```
┌────────────────────────────────────────────────────┐
│ Input File:              [________________] Browse │
│ Product Output File:     [________________] Browse │
│ Collections Output File: [________________] Browse │
│ Log File:                [________________] Browse │
│                                                    │
│ AI Enhancement:   ☑ Use AI for taxonomy...        │
│ AI Provider:      [ChatGPT (OpenAI)     ▼]        │
│ AI Model:         [GPT-5 (Latest)       ▼]        │
│                                                    │
│ Audience Configuration:                            │
│   ○ Single Audience  ● Multiple Audiences (2)     │
│                                                    │
│ Audience 1 Name:  [Homeowners______________]      │
│ Tab 1 Label:      [For Your Home___________]      │
│ Audience 2 Name:  [Contractors_____________]      │
│ Tab 2 Label:      [For Professionals_______]      │
│                                                    │
│ Execution Mode:                                    │
│   ○ Resume from Last Run  ● Overwrite & Continue  │
│                                                    │
│     [Process Products]  [Process Collections]     │
└────────────────────────────────────────────────────┘
```

**Configuration Examples:**

**Single Audience Mode:**
```
Audience Configuration: ● Single Audience  ○ Multiple Audiences (2)
Audience 1 Name: Homeowners
```

**Multiple Audience Mode:**
```
Audience Configuration: ○ Single Audience  ● Multiple Audiences (2)
Audience 1 Name: Homeowners
Audience 2 Name: Contractors
Tab 1 Label: For Your Home
Tab 2 Label: For Professionals
```

### 2. AI Generation (OpenAI API)

When AI Enhancement is enabled, the system:

1. **Single Audience:**
   - Generates one description tailored to specified audience
   - Stores in product `body_html` field

2. **Multiple Audiences:**
   - Generates TWO separate descriptions, each optimized for its audience
   - Stores Audience 1 description in `body_html` (primary)
   - Stores Audience 1 description in `custom.description_audience_1` metafield
   - Stores Audience 2 description in `custom.description_audience_2` metafield
   - Stores configuration in `custom.audience_config` metafield (JSON)

### 3. Shopify Display (Liquid Template)

The `product-description-tabs.liquid` snippet:

1. **Checks audience configuration** from metafield
2. **Single Audience:** Displays standard description
3. **Multiple Audiences:** Displays tabbed interface with custom labels and icons

## Technical Implementation

### Data Flow

```
User Config (GUI)
    ↓
config.json (auto-saved)
    ↓
ai_provider.py (extracts audience_config)
    ↓
openai_api.py (generates descriptions)
    ↓
Product JSON (with metafields)
    ↓
Shopify GraphQL API (productCreate)
    ↓
Shopify Store (metafields stored)
    ↓
product-description-tabs.liquid (renders tabs)
    ↓
Customer sees tabbed descriptions
```

### Configuration Fields

**GUI Fields:**
- `AUDIENCE_COUNT` (int): 1 or 2
- `AUDIENCE_1_NAME` (str): Name of primary audience
- `AUDIENCE_2_NAME` (str): Name of second audience (if count=2)
- `AUDIENCE_TAB_1_LABEL` (str): Display label for first tab (if count=2)
- `AUDIENCE_TAB_2_LABEL` (str): Display label for second tab (if count=2)

**Saved in:** `config.json`

### Metafields Structure

#### 1. audience_config (JSON)

```json
{
  "count": 2,
  "audience_1_name": "Homeowners",
  "audience_2_name": "Contractors",
  "tab_1_label": "For Your Home",
  "tab_2_label": "For Professionals"
}
```

**Shopify Type:** `json`
**Namespace:** `custom`
**Key:** `audience_config`

#### 2. description_audience_1 (Multi-line text)

Contains full HTML description for Audience 1.

**Shopify Type:** `multi_line_text_field`
**Namespace:** `custom`
**Key:** `description_audience_1`

#### 3. description_audience_2 (Multi-line text)

Contains full HTML description for Audience 2.

**Shopify Type:** `multi_line_text_field`
**Namespace:** `custom`
**Key:** `description_audience_2`

### AI Prompt Modifications

The description generation prompt is enhanced with audience context:

**Before (no audience):**
```
Product information:
- Title: {title}
- Department: {department}
- Current Description: {body_html}

CRITICAL: Write for MOBILE-FIRST experience...
```

**After (with audience):**
```
Product information:
- Title: {title}
- Department: {department}
- Current Description: {body_html}
- Target Audience: Homeowners

CRITICAL: Write for MOBILE-FIRST experience...
AUDIENCE: Tailor this description specifically for Homeowners. Use language, benefits, and examples that resonate with this audience.
```

### Code Changes

**Files Modified:**

1. **uploader_modules/gui.py** (lines 679-928)
   - Added audience configuration section with radio buttons
   - Added 4 audience text input fields (always visible, conditionally enabled)
   - Field order: Audience 1 Name → Tab 1 Label → Audience 2 Name → Tab 2 Label
   - Implemented enable/disable logic based on selection
   - Moved Execution Mode section to just above action buttons
   - Added auto-save for all fields

2. **uploader_modules/openai_api.py**
   - Updated `enhance_product_with_openai()` signature to accept `audience_config`
   - Modified `_build_description_prompt()` to accept `audience_name` parameter
   - Added logic to generate 2 descriptions when `audience_count == 2`
   - Added metafields to enhanced product for audience descriptions

3. **uploader_modules/ai_provider.py** (lines 93-111)
   - Extracts audience configuration from `cfg`
   - Builds `audience_config` dict
   - Passes to OpenAI and Claude enhancement functions

4. **shopify_theme_code/product-description-tabs.liquid** (NEW)
   - Liquid snippet for rendering tabbed interface
   - Parses metafields and conditionally renders tabs
   - Includes CSS for desktop and mobile layouts
   - Includes JavaScript for tab switching and keyboard navigation

5. **shopify_theme_code/INSTALLATION_GUIDE.md** (NEW)
   - Complete installation instructions for Shopify theme
   - Metafield creation steps
   - Template integration guide
   - Troubleshooting section

## API Costs

**OpenAI GPT-5 Pricing (as of 2025):**
- Input tokens: ~$0.003 per 1K tokens
- Output tokens: ~$0.015 per 1K tokens

**Single Audience Mode:**
- 2 API calls per product (taxonomy + description)
- Estimated cost: $0.01 - $0.03 per product

**Multiple Audience Mode:**
- 3 API calls per product (taxonomy + description 1 + description 2)
- Estimated cost: $0.015 - $0.045 per product
- ~50% more expensive than single audience mode

## Performance Considerations

### Processing Time

**Single Audience:**
- ~10-15 seconds per product (API call + processing)

**Multiple Audiences:**
- ~15-25 seconds per product (2x description generation)
- Rate limiting: 6-second pause every 5 products

### Batch Processing

For 100 products:
- **Single Audience:** ~20-30 minutes
- **Multiple Audiences:** ~30-45 minutes

### Caching

The system caches enhanced products in `claude_enhanced_cache.json`:
- Cache key: product ID or handle
- Cache invalidation: when product title or description changes
- **Important:** Cache stores audience metafields, so configuration changes require cache deletion

## Usage Instructions

### Step 1: Configure Audiences in GUI

1. Launch the uploader: `python3 uploader.py`
2. Ensure **AI Enhancement** toggle is enabled
3. Select **AI Provider** (OpenAI recommended for audience feature)
4. Choose audience configuration:
   - **Single Audience:** For one description variant
   - **Multiple Audiences (2):** For tabbed descriptions

### Step 2: Fill in Audience Details

The GUI displays four audience fields in this order:
1. **Audience 1 Name** - Name of primary audience
2. **Tab 1 Label** - Display label for first tab
3. **Audience 2 Name** - Name of secondary audience
4. **Tab 2 Label** - Display label for second tab

**Field Behavior:**
- All fields are always visible
- Fields are **disabled** when not needed (grayed out)
- Fields are **enabled** based on AI Enhancement toggle and Audience Configuration selection

**Single Audience Example:**
```
Audience Configuration: ● Single Audience  ○ Multiple Audiences (2)

Audience 1 Name: Homeowners          (enabled)
Tab 1 Label:     [grayed out]        (disabled)
Audience 2 Name: [grayed out]        (disabled)
Tab 2 Label:     [grayed out]        (disabled)
```

**Multiple Audiences Example:**
```
Audience Configuration: ○ Single Audience  ● Multiple Audiences (2)

Audience 1 Name: Homeowners          (enabled)
Tab 1 Label:     For Your Home       (enabled)
Audience 2 Name: Contractors         (enabled)
Tab 2 Label:     For Professionals   (enabled)
```

**Tips:**
- Use clear, descriptive audience names (AI uses these for context)
- Keep tab labels short (2-4 words) for best mobile display
- Tab labels are customer-facing, audience names are internal
- Disabled fields will be grayed out but remain visible for context

### Step 3: Process Products

Click **Process Products** button. The system will:
1. Validate configuration
2. Generate audience-specific descriptions
3. Store descriptions in metafields
4. Upload products to Shopify

### Step 4: Install Shopify Theme Code

Follow instructions in `shopify_theme_code/INSTALLATION_GUIDE.md`:
1. Create metafield definitions in Shopify Admin
2. Upload `product-description-tabs.liquid` snippet
3. Render snippet in product template
4. Test on product pages

## Best Practices

### 1. Audience Selection

**Good Audience Pairs:**
- Homeowners / Contractors
- Beginners / Experts
- Residential / Commercial
- DIY Enthusiasts / Professionals
- Retail Customers / Wholesale Buyers

**Avoid:**
- Overlapping audiences (e.g., "Homeowners" and "Residential")
- Too similar audiences (e.g., "Beginners" and "Novices")
- Vague audiences (e.g., "Everyone" and "All Users")

### 2. Tab Labels

**Good Tab Labels:**
- "For Your Home" / "For Pros"
- "DIY Guide" / "Pro Specs"
- "Residential" / "Commercial"
- "Getting Started" / "Advanced"

**Avoid:**
- Long labels (>4 words)
- Generic labels ("Option 1", "Option 2")
- Redundant labels ("For Homeowners" when audience name is "Homeowners")

### 3. Voice and Tone Guidelines

Update your `docs/VOICE_AND_TONE_GUIDELINES.md` to include audience-specific guidance:

```markdown
## Audience: Homeowners
- Use warm, inviting language
- Focus on lifestyle benefits and aesthetics
- Avoid technical jargon
- Emphasize ease of installation and maintenance

## Audience: Contractors
- Use professional, direct language
- Focus on efficiency, durability, and ROI
- Include technical specifications
- Emphasize commercial warranty and support
```

### 4. Testing

**Before Full Batch:**
1. Test with 2-3 products in each mode
2. Verify descriptions are audience-appropriate
3. Check metafields in Shopify Admin
4. Test tab functionality on live storefront
5. Test mobile responsiveness (<480px width)

**Quality Checks:**
- Audience 1 description focuses on correct audience
- Audience 2 description focuses on correct audience
- Descriptions are substantively different (not just reworded)
- HTML formatting is clean and consistent
- Tab labels display correctly
- Tabs switch smoothly

## Troubleshooting

### Issue: Descriptions Not Different Enough

**Solution:**
- Use more distinct audience names (e.g., "DIY Homeowners" vs "Professional Contractors")
- Update voice and tone guidelines with clear audience differentiation
- Review generated descriptions and provide feedback in taxonomy document

### Issue: Tabs Not Appearing

**Check:**
1. Metafields created in Shopify Admin
2. Product has `audience_config` metafield with `count: 2`
3. Liquid snippet installed correctly
4. Snippet rendered in product template

**Debug:**
View metafield values in Shopify Admin → Products → [Product] → Metafields

### Issue: Empty or Blank Descriptions

**Check:**
1. AI API key configured correctly
2. No API errors in logs (`logs/` folder)
3. Cache not causing issues (delete `claude_enhanced_cache.json`)

### Issue: High API Costs

**Solutions:**
- Use caching (automatic) - only processes changed products
- Use single audience mode when multiple audiences not needed
- Batch process during off-peak hours to avoid rate limit delays
- Consider using cheaper model (GPT-5 Mini) for less critical products

## Limitations

### Current Limitations

1. **Maximum 2 audiences** - UI and Liquid template support only 2 audiences
2. **OpenAI only** - Claude API support not yet implemented
3. **No A/B testing** - Cannot track which audience description performs better
4. **No analytics** - No built-in tracking of tab usage
5. **Manual metafield creation** - Metafields must be created manually in Shopify Admin

### Future Enhancements

Planned features:
- Support for 3+ audiences
- Claude API integration
- Built-in A/B testing
- Analytics integration (Google Analytics events)
- Automatic metafield creation via API
- Audience presets (e.g., "Homeowners/Contractors" template)

## Related Documentation

- **Installation Guide:** `shopify_theme_code/INSTALLATION_GUIDE.md`
- **OpenAI API Requirements:** `requirements/OPENAI_API_REQUIREMENTS.md`
- **GUI Design Patterns:** `docs/GUI_DESIGN_REQUIREMENTS.md`
- **Voice and Tone Guidelines:** `docs/VOICE_AND_TONE_GUIDELINES.md`
- **Technical Documentation:** `docs/TECHNICAL_DOCS.md`

## Support

For issues or questions:
1. Check logs in `logs/` folder for detailed error information
2. Review this documentation and installation guide
3. Test with single product first to isolate issues
4. Verify Shopify metafields are correctly configured

## Changelog

**Version 2.6.0** (2025-10-29)
- Initial release of audience-based descriptions feature
- OpenAI integration with audience-specific prompts
- GUI configuration for single/multiple audiences
- Metafield storage for multiple descriptions
- Liquid template with tabbed interface
- Mobile-responsive design with keyboard navigation

**GUI Updates** (2025-10-29):
- Fixed field ordering: Audience 1 Name → Tab 1 Label → Audience 2 Name → Tab 2 Label
- Changed fields to remain visible but disabled (instead of hidden) for better UX
- Moved Execution Mode section to just above action buttons for logical flow
- All audience fields now properly display and enable/disable based on configuration
