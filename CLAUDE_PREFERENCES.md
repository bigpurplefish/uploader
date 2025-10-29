# CLAUDE_PREFERENCES.md

This template file defines user preferences for Claude Code when working on projects. Copy this file to your project root or keep it in a central location and reference it at the start of conversations.

---

## Git Workflow Preferences

**Commit Strategy:** Proactive (Option 2)

### How It Works

When making changes to a project:
1. ✅ Make the code changes and test them
2. ✅ After completing a significant feature or set of changes, **ASK THE USER**: "Would you like me to commit and push these changes to GitHub?"
3. ⏸️ Wait for user approval before committing
4. ✅ If approved, create a meaningful commit with:
   - Descriptive commit message explaining what was changed and why
   - Group related changes together (don't commit every tiny change separately)
   - Include "🤖 Generated with Claude Code" footer
   - Include "Co-Authored-By: Claude <noreply@anthropic.com>" line
5. ✅ Push to the configured GitHub remote

### What Counts as "Significant"

**DO ask about committing:**
- ✅ New feature added
- ✅ Bug fix completed
- ✅ Documentation updates (major changes)
- ✅ Refactoring completed
- ✅ Multiple related changes that form a cohesive update
- ✅ Configuration changes (when user approves)
- ✅ Dependency updates

**DO NOT auto-commit:**
- ❌ Work in progress
- ❌ Experimental changes
- ❌ Small typo fixes (unless user specifically requests)
- ❌ Incomplete features
- ❌ Failed tests or broken code

---

## Project-Specific Settings

**Update these fields for each project:**

### Repository Information
- **GitHub URL:** `[INSERT YOUR REPO URL HERE]`
  - Example SSH: `git@github.com:username/project.git`
  - Example HTTPS: `https://github.com/username/project.git`
- **Default Branch:** `main` (or `master`, `develop`, etc.)

### Commit Message Format
- **Style:** Descriptive with context
- **Include:** What changed and why
- **Footer:** Always include Claude Code attribution

**Example commit message:**
```
Add Claude AI collection descriptions

- Generate SEO-optimized 100-word descriptions for collections
- Use voice and tone guidelines per department
- Sample 5 products from collection for context
- Add comprehensive logging for troubleshooting

🤖 Generated with Claude Code (https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Code Style Preferences

### Python Projects
- **Formatting:** PEP 8 compliant
- **Type Hints:** Use when helpful for clarity
- **Docstrings:** Google-style docstrings for functions/classes
- **Line Length:** 120 characters max (or 88 for Black)
- **Imports:** Group stdlib, third-party, local (isort style)

### JavaScript/TypeScript Projects
- **Formatting:** Prettier defaults
- **Style:** ESLint recommended
- **Semicolons:** Yes (or specify preference)

### Documentation
- **Format:** Markdown
- **Location:** `/docs` directory for detailed docs
- **README:** Keep concise, link to detailed docs

---

## Communication Preferences

### Status Updates
- ✅ Use TodoWrite tool for multi-step tasks
- ✅ Provide progress updates during long operations
- ✅ Explain what you're doing before doing it (for complex changes)

### Error Handling
- ✅ Show full error messages in logs
- ✅ Provide troubleshooting steps when errors occur
- ✅ Don't hide failures - be transparent

### Explanations
- ✅ Explain complex decisions
- ✅ Document "why" not just "what"
- ✅ Provide context for architectural choices

---

## Testing Preferences

### When to Run Tests
- Before committing (if test suite exists)
- After making changes to critical functions
- When explicitly requested

### Test Philosophy
- Write tests for new features (when appropriate)
- Fix failing tests before committing
- Don't push broken code

---

## File Management

### What to Commit
- ✅ Source code
- ✅ Documentation
- ✅ Configuration templates (e.g., `config_sample.json`)
- ✅ Requirements/dependency files
- ✅ Build scripts

### What NOT to Commit (add to .gitignore)
- ❌ Credentials or API keys
- ❌ Environment-specific config files
- ❌ Log files
- ❌ Cache/state files
- ❌ IDE-specific files (.vscode, .idea)
- ❌ Python: `__pycache__/`, `*.pyc`, `venv/`
- ❌ Node: `node_modules/`, `.env`

---

## AI-Specific Preferences

### Claude AI Integration (if applicable)
- **Default Model:** Sonnet 4.5 (for best reasoning)
- **Fallback Model:** Sonnet 3.5 (for cost savings)
- **API Key Storage:** Environment variables or secure config
- **Cost Tracking:** Log token usage for transparency

---

## Notes for Future AI Assistants

When starting work on a project with this preferences file:
1. Read this file first
2. Follow the Git workflow exactly as specified
3. Use the commit message format consistently
4. Ask clarifying questions if anything is unclear
5. Remember: **Proactive means ASK, not auto-commit**

---

## Customization Instructions

To use this template:
1. Copy to your project root as `CLAUDE_PREFERENCES.md`
2. Update the "Project-Specific Settings" section
3. Customize any preferences to your needs
4. Reference this file at the start of conversations: "Please follow CLAUDE_PREFERENCES.md"
5. Or add a link to this file in your project's CLAUDE.md

---

**Last Updated:** 2025-01-29
**Template Version:** 1.0
