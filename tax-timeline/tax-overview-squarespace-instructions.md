# Squarespace Setup Instructions for Tax Overview Page

## Overview
The tax-overview.html file has been split into three separate files for Squarespace compatibility:

1. **tax-overview-squarespace-html.html** - HTML content only
2. **tax-overview-squarespace-css.css** - All CSS styles
3. **tax-overview-squarespace-js.txt** - JavaScript code (see below for full content)

## Setup Steps

### Step 1: Add External Libraries
Go to **Settings > Advanced > Code Injection > Header** and add:

```html
<!-- Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700;900&family=Public+Sans:wght@400;700;800;900&display=swap" rel="stylesheet">

<!-- Chart.js Library -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

### Step 2: Add CSS
Go to **Design > Custom CSS** and paste the entire contents of `tax-overview-squarespace-css.css`

### Step 3: Add HTML Content
1. Create a new page or edit an existing one
2. Add a **Code Block**
3. Paste the contents of `tax-overview-squarespace-html.html`
4. Make sure the Code Block is set to display as HTML (not text)

### Step 4: Add JavaScript
1. Below the HTML Code Block, add another **Code Block**
2. Paste the JavaScript code (see tax-overview-squarespace-js.txt)
3. Wrap it in `<script>` tags:
```html
<script>
// Paste JavaScript here
</script>
```

## Important Notes

### Why the formatting looked off:
- Squarespace Code Blocks need proper structure
- External fonts must be loaded in the Header
- Chart.js library must be loaded before the page JavaScript runs
- CSS should be in Custom CSS panel, not inline

### Troubleshooting:
- **Fonts not loading**: Check that the Google Fonts link is in Code Injection > Header
- **Chart not appearing**: Verify Chart.js script is loaded in Header
- **Styles not applying**: Make sure CSS is in Design > Custom CSS
- **JavaScript errors**: Check browser console for specific errors

### Mobile Responsiveness:
The CSS includes media queries for mobile devices. Test on different screen sizes.

### Performance:
- The page uses Chart.js for interactive charts
- All animations are CSS-based for smooth performance
- Images are loaded from external CDN (Squarespace CDN)

## File Structure
```
tax-overview-squarespace-html.html    → Code Block #1 (HTML)
tax-overview-squarespace-css.css      → Design > Custom CSS
tax-overview-squarespace-js.txt       → Code Block #2 (wrapped in <script> tags)
```

## Need Help?
If you encounter issues:
1. Check browser console for JavaScript errors
2. Verify all external resources are loading (Network tab)
3. Ensure Code Blocks are set to "Display Source" mode
4. Clear Squarespace cache and refresh
