Analyze this project and create a comprehensive Claude Code agent and command system with automatic agent delegation.

## Step 1: Project Analysis

First, explore my project structure:

- Find and read all requirements documents, specs, and design docs
- Identify the key domains and features of this project
- Understand the tech stack by examining package.json, requirements.txt, or similar
- Note any existing conventions in the codebase

## Step 2: Create Directory Structure

Create the following directories if they don't exist:

- .claude/agents/
- .claude/commands/

## Step 3: Generate Agents

Based on the requirements and domains you discovered, create specialized agents in .claude/agents/. For each agent:

- Give it a clear, descriptive name
- Write a description with **trigger keywords** that enable automatic delegation:
  - Include specific tasks: "Use for authentication", "Use for database migrations"
  - Include file types: "Use when working with .py files", "Use for React components"
  - Include domain terms: "payment processing", "image optimization", "API endpoints"
  - Be explicit about when to invoke: "MUST BE USED for...", "Always use when..."
- Assign appropriate tools (Read, Write, Edit, Bash, Grep, Glob)
- Write a detailed system prompt with:
  - Role and expertise
  - Key responsibilities
  - How to approach tasks
  - References to relevant requirements docs
  - Quality standards to maintain

At minimum, create agents for:

1. A requirements-analyst that reads and interprets requirements docs
2. Domain-specific agents for each major feature area
3. A code-reviewer agent
4. A test-writer agent
5. Any other specialists the project needs

## Step 4: Generate Commands

Create custom slash commands in .claude/commands/ for common workflows:

- /implement-feature - requirements-driven feature implementation
- /review - code review against requirements and standards
- /test - generate tests based on acceptance criteria
- /document - update documentation
- Any domain-specific commands that would help this project

## Step 5: Create/Update CLAUDE.md

Create or update CLAUDE.md in the project root with:

### Project Context Section

- Project overview
- References to key requirements docs using @path/to/doc syntax
- Architecture summary
- Coding conventions
- Testing approach
- Instructions to always verify against requirements

### Agent Delegation Section

Add this critical section:

```markdown
## Agent Delegation Strategy

You have access to specialized agents in .claude/agents/. **Automatically analyze each request and delegate to the appropriate specialist(s) without asking permission.**

### Delegation Rules

1. **Analyze the request** - Identify the domain, file types, and technical areas involved
2. **Match to specialists** - Check which agent descriptions match the task
3. **Delegate proactively** - Invoke the specialist automatically, don't ask first
4. **Coordinate multiple agents** - For complex tasks, orchestrate multiple specialists in sequence or parallel

### When to Delegate

- Requirements analysis → use requirements-analyst
- Domain-specific features → use the domain specialist (e.g., ecommerce-expert, media-specialist)
- Code review → use code-reviewer after implementation
- Testing → use test-automator for test generation
- Security concerns → use security-auditor

### Orchestration Pattern

For complex features:

1. Requirements-analyst reads and clarifies requirements
2. Domain specialist(s) implement the feature
3. Test-automator creates tests
4. Code-reviewer validates quality
5. Security-auditor checks for vulnerabilities (if applicable)

**Never implement features without first consulting the requirements-analyst if requirements docs exist.**
```

## Step 6: Summary Report

After creating everything, provide:

- List of agents created with their trigger keywords
- List of commands created and when to use them
- Example scenarios showing automatic delegation
- Recommendations for how to use this system effectively
- Any gaps in the requirements that I should address

## Important Guidelines

- Make agents focused and single-purpose
- Write descriptions with **clear trigger keywords** for automatic delegation
- Reference my actual requirements docs in agent prompts
- Keep CLAUDE.md concise - link to docs rather than duplicating content
- Use the actual tech stack and conventions you find in my project
- If you find ambiguities in requirements, note them in the summary
- Test automatic delegation by showing example scenarios

Begin by exploring the project structure and requirements documents.
