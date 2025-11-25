# Document Command

Update documentation for the specified feature or module.

## Usage
```
/document <topic>
```

Topics:
- `api` - Update API requirements documentation
- `gui` - Update GUI design documentation
- `feature <name>` - Document a specific feature
- `changelog` - Update changelog with recent changes
- `readme` - Update main README

## Process

### Step 1: Identify Documentation Needs
Based on the topic, determine which files need updates:

| Topic | Primary Document | Related Documents |
|-------|------------------|-------------------|
| api | `requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md` | `docs/TECHNICAL_DOCS.md` |
| gui | `docs/GUI_DESIGN_REQUIREMENTS.md` | `docs/README.md` |
| feature | `docs/<feature>.md` | `CLAUDE.md`, `docs/README.md` |
| changelog | `docs/CHANGELOG.md` | - |
| readme | `README.md` | `docs/QUICK_START.md` |

### Step 2: Gather Information
- Read current implementation code
- Check git history for recent changes
- Review related test files for behavior examples

### Step 3: Update Documentation
Follow these documentation standards:

1. **Use clear headings** (H1 for title, H2 for sections, H3 for subsections)
2. **Include code examples** for technical documentation
3. **Add "Last Updated" date** at top of document
4. **Cross-reference** related documents with @path links
5. **Include version numbers** for API-specific docs

### Step 4: Verify Consistency
Ensure documentation matches:
- Current code implementation
- CLAUDE.md project overview
- Other related documentation

### Documentation Format Template
```markdown
# Feature/Topic Name

**Version:** X.X.X
**Last Updated:** YYYY-MM-DD

## Overview
[Brief description of the feature/topic]

## Key Concepts
- Concept 1
- Concept 2

## Implementation Details
[Technical details with code examples]

## Examples
[Usage examples]

## Related Documentation
- @docs/related-doc.md
- @requirements/related-requirements.md
```

## Examples
```
/document api              # Update Shopify API docs
/document feature audience # Document audience feature
/document changelog        # Update changelog
```
