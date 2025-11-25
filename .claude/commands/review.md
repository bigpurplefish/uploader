# Code Review Command

Review code changes against project requirements and standards.

## Usage
```
/review [file or module name]
```

If no file is specified, review all uncommitted changes.

## Process

### Step 1: Identify Changes
Check git status for:
- Modified files
- New files
- Deleted files

### Step 2: Requirements Check
For each changed file, verify against relevant requirements:

**For shopify_api.py:**
- Uses correct API 2025-10 patterns
- ProductCreateInput (not ProductInput)
- max_completion_tokens for GPT-5/o-series
- Proper userErrors handling

**For gui.py:**
- Thread-safe updates via queues
- Auto-save configuration
- Tooltips on all inputs
- Button state management

**For AI integration:**
- Correct parameter handling for model type
- Fallback for empty responses
- Proper caching

**For tests:**
- External APIs mocked
- Success and error paths covered
- Fixtures used appropriately

### Step 3: Standards Check
Verify against:
- `@CLAUDE.md` standards
- `/Users/moosemarketer/Code/shared-docs/python/COMPLIANCE_CHECKLIST.md`

### Step 4: Generate Report
Provide structured output:

```
## Code Review Report

### Files Reviewed
- [List of files]

### Critical Issues (Must Fix)
1. [Issue with file:line reference]

### Warnings (Should Fix)
1. [Issue with file:line reference]

### Suggestions (Nice to Have)
1. [Suggestion]

### Passed Checks
- [List of passed checks]

### Recommendation
[Ready to commit / Needs changes]
```

## Example
```
/review uploader_modules/shopify_api.py
```
