# Implement Feature Command

Implement a new feature using requirements-driven development.

## Usage
```
/implement-feature <feature description>
```

## Process

### Step 1: Requirements Analysis
First, consult the requirements-analyst agent to understand:
1. What documentation exists for this feature
2. What acceptance criteria apply
3. What patterns and standards must be followed

Review these documents based on the feature domain:
- `@CLAUDE.md` - Overall project standards
- `@requirements/SHOPIFY_API_2025-10_REQUIREMENTS.md` - If Shopify API work
- `@requirements/OPENAI_API_REQUIREMENTS.md` - If AI integration work
- `@docs/GUI_DESIGN_REQUIREMENTS.md` - If GUI work
- `@docs/PRODUCT_TAXONOMY.md` - If taxonomy work

### Step 2: Plan Implementation
Create a todo list with specific implementation steps:
1. Identify files to modify or create
2. List specific changes needed in each file
3. Note any new tests required
4. Identify any configuration changes

### Step 3: Implement Changes
For each step in the plan:
1. Read the existing code first
2. Make minimal, focused changes
3. Follow existing patterns in the codebase
4. Add proper error handling and logging

### Step 4: Write Tests
After implementation:
1. Create or update tests for new functionality
2. Ensure mocks are used for external APIs
3. Cover both success and error paths

### Step 5: Code Review
Run the code-reviewer agent to verify:
1. Code follows project standards
2. Error handling is complete
3. No security issues
4. Tests are adequate

### Step 6: Summary
Provide a summary of:
- Files modified
- Key changes made
- Tests added
- Any follow-up actions needed

## Example
```
/implement-feature Add support for bulk product deletion
```
