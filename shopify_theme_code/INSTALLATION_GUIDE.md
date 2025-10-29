# Audience-Based Product Description Tabs - Installation Guide

This guide explains how to install the tabbed product description feature in your Shopify theme.

## Overview

This feature allows you to display different product descriptions for different audiences (e.g., Homeowners vs. Contractors) using a tabbed interface on product pages.

**Features:**
- Conditional rendering based on audience configuration
- Two-tab interface for multiple audiences
- Single description fallback for single audience products
- Mobile-optimized with vertical stacking on small screens
- Polaris-style icons (Home and Tools)
- Keyboard navigation support (Arrow keys, Home, End)
- ARIA labels for accessibility
- Smooth animations between tabs

## Prerequisites

1. Access to your Shopify theme code editor:
   - Shopify Admin → Online Store → Themes → Actions → Edit Code

2. Three custom metafields created in your store:
   - `product.metafields.custom.audience_config` (JSON)
   - `product.metafields.custom.description_audience_1` (Multi-line text)
   - `product.metafields.custom.description_audience_2` (Multi-line text)

## Installation Steps

### Step 1: Create Metafield Definitions

1. Go to **Shopify Admin → Settings → Custom Data → Products**

2. Click **Add definition** and create these metafields:

   **Metafield 1: Audience Configuration**
   - Namespace: `custom`
   - Key: `audience_config`
   - Name: `Audience Configuration`
   - Type: `JSON`
   - Description: `Configuration for audience-based descriptions`

   **Metafield 2: Description for Audience 1**
   - Namespace: `custom`
   - Key: `description_audience_1`
   - Name: `Description (Audience 1)`
   - Type: `Multi-line text`
   - Description: `Product description for first audience`

   **Metafield 3: Description for Audience 2**
   - Namespace: `custom`
   - Key: `description_audience_2`
   - Name: `Description (Audience 2)`
   - Type: `Multi-line text`
   - Description: `Product description for second audience`

### Step 2: Upload Liquid Snippet

1. Go to **Shopify Admin → Online Store → Themes → Actions → Edit Code**

2. In the left sidebar, find the **Snippets** folder

3. Click **Add a new snippet**

4. Name it: `product-description-tabs`

5. Copy the entire contents of `product-description-tabs.liquid` and paste into the editor

6. Click **Save**

### Step 3: Add Snippet to Product Template

Now you need to render the snippet in your product page template. The exact location depends on your theme, but typically:

**Option A: Liquid Themes (older themes)**

1. Open `sections/product-template.liquid` or `templates/product.liquid`

2. Find where the product description is rendered (look for `{{ product.description }}`)

3. Replace that line with:
   ```liquid
   {% render 'product-description-tabs', product: product %}
   ```

**Option B: JSON Templates (newer themes like Dawn)**

1. Open `sections/main-product.liquid`

2. Find the description block (search for `product.description` or look for a `<div class="product__description">`)

3. Replace the description rendering with:
   ```liquid
   {% render 'product-description-tabs', product: product %}
   ```

**Example - Before:**
```liquid
<div class="product__description rte">
  {{ product.description }}
</div>
```

**Example - After:**
```liquid
{% render 'product-description-tabs', product: product %}
```

4. Click **Save**

### Step 4: Test the Installation

1. **Test Single Audience Mode:**
   - Upload a product using the Python uploader with **Single Audience** selected
   - The product should display a standard description (no tabs)

2. **Test Multiple Audience Mode:**
   - Upload a product using the Python uploader with **Multiple Audiences (2)** selected
   - The product page should show two tabs with custom labels
   - Click each tab to verify descriptions switch properly
   - Test on mobile (<480px) to verify tabs stack vertically

3. **Test Keyboard Navigation:**
   - Focus on the first tab (click or press Tab)
   - Press Arrow Right → second tab should activate
   - Press Arrow Left → first tab should activate
   - Press Home → first tab
   - Press End → last tab

## Customization

### Changing Colors

Edit the CSS in `product-description-tabs.liquid`:

```css
/* Desktop active tab border */
.audience-tabs__button--active {
  border-color: #e5e7eb;  /* Change border color */
}

/* Mobile active tab background */
@media (max-width: 480px) {
  .audience-tabs__button--active {
    background: #3b82f6;  /* Change background color */
    color: white;         /* Change text color */
    border-color: #3b82f6;
  }
}
```

### Changing Tab Icons

Replace the SVG paths with different Polaris icons from: https://polaris.shopify.com/icons

### Adjusting Mobile Breakpoint

Change `@media (max-width: 480px)` to your preferred breakpoint (e.g., `768px` for tablet).

### Adding Animation

Current animation: `fadeIn` (fade + slide up). To customize:

```css
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);  /* Adjust slide distance */
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

## Troubleshooting

### Tabs Not Appearing

**Check:**
1. Metafields are correctly defined in Shopify Admin
2. Product has `audience_config` metafield with `count: 2`
3. Product has both `description_audience_1` and `description_audience_2` metafields
4. Snippet is correctly named `product-description-tabs.liquid`
5. Snippet is rendered in product template with correct syntax

**Debug:**
Add this to your product template temporarily to see metafield values:
```liquid
<div>
  <p>Audience Config: {{ product.metafields.custom.audience_config }}</p>
  <p>Desc 1 Length: {{ product.metafields.custom.description_audience_1 | size }}</p>
  <p>Desc 2 Length: {{ product.metafields.custom.description_audience_2 | size }}</p>
</div>
```

### Tabs Not Switching

**Check:**
1. JavaScript is not being blocked by theme or app conflicts
2. Console has no errors (Right-click → Inspect → Console tab)
3. `data-audience-tabs` attribute exists on container

**Debug:**
Open browser console and type:
```javascript
document.querySelector('[data-audience-tabs]')
```
Should return the tabs container element (not `null`).

### Styling Conflicts

If tabs look broken:

1. **Check for conflicting CSS** - Other stylesheets may override tab styles
2. **Increase specificity** - Add `.product-description-container` prefix to all CSS rules
3. **Use `!important`** sparingly - Last resort for critical styles

### Mobile Layout Not Stacking

Verify the media query:
```css
@media (max-width: 480px) {
  .audience-tabs__buttons {
    flex-direction: column;  /* Should stack vertically */
  }
}
```

Test at exactly 480px width using browser dev tools.

## Theme Compatibility

**Tested with:**
- Dawn (Shopify's reference theme)
- Debut
- Brooklyn
- Narrative

**Should work with:**
- Any Shopify 2.0 theme (JSON templates)
- Most legacy Liquid themes

**May require adjustments for:**
- Heavily customized themes
- Themes with custom product page builders
- Themes that modify the RTE (rich text editor) class

## Support

If you encounter issues:

1. Check Shopify theme documentation for your specific theme
2. Review browser console for JavaScript errors
3. Verify metafields are correctly populated in Shopify Admin
4. Test with Shopify's default Dawn theme to isolate theme-specific issues

## Technical Details

**Browser Support:**
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support (iOS 12+)
- IE11: ❌ Not supported (uses modern JS)

**Performance:**
- No external dependencies
- Inline CSS and JavaScript
- Minimal DOM manipulation
- ~100 lines of CSS, ~80 lines of JavaScript

**Accessibility:**
- ARIA roles and labels
- Keyboard navigation
- Focus management
- Screen reader compatible

## Future Enhancements

Potential improvements:
- Support for 3+ audiences
- Persistent tab selection (localStorage)
- Analytics tracking for tab usage
- A/B testing integration
- Animation options (slide, fade, etc.)
