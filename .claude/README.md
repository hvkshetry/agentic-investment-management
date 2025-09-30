# Claude Code Configuration

This directory contains Claude Code CLI configuration files.

## Files

### `CLAUDE.md`
Main orchestrator prompt for **Obsidian-based workflows**.

**Use case**: Interactive portfolio management with knowledge graph
- Manages portfolio state in Obsidian vault
- Uses Obsidian MCP tools for persistent knowledge
- Smart Connections for semantic linking
- Template-based position tracking

**Invoke**: This is loaded automatically when using Claude Code with this directory

### `agents/`
Custom agent definitions for @-mention invocation.

**Use case**: Specialized analysis and ad-hoc queries
- @portfolio-manager for optimization analysis
- @risk-analyst for risk assessment
- @tax-advisor for tax implications
- 12 total specialized agents

**Invoke**: Use `@agent-name` in Claude Code CLI

### `settings.local.json`
Local Claude Code settings (user-specific, gitignored by default)

## Relationship to Other Systems

### vs. `agent-prompts/`
- **`.claude/`**: Interactive, Obsidian-based, knowledge management
- **`agent-prompts/`**: Automated workflows, file-based, session artifacts

### vs. `.mcp.json`
- **`.claude/`**: Claude Code CLI configuration (agents, orchestrator)
- **`.mcp.json`**: MCP server connections (portfolio-state, risk, tax, etc.)

Both systems complement each other:
- Use `.claude/` agents for conversational analysis
- Use `agent-prompts/` workflows for automated processes

## Example Usage

**Interactive (Claude Code CLI)**:
```
@risk-analyst what's our current ES at 97.5% confidence?
```

**Automated (Workflow)**:
```bash
# Execute rebalance_tlh.yaml workflow
# Uses agent-prompts/sub-agents/ with file-based tools
```